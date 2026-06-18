import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime
from utils import fetch_top_markets, normalize_series

st.set_page_config(
    page_title="Crypto Screener",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @media (max-width: 768px) {
      .block-container { padding-left: 0.7rem; padding-right: 0.7rem; }
      .stDataFrame { font-size: 12px; }
      h1 { font-size: 1.7rem !important; }
      h2 { font-size: 1.3rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🪙 Live Crypto Screener")
st.caption("Super-light version for better stability on Streamlit Cloud.")

with st.sidebar:
    st.header("Settings")
    vs_currency = st.selectbox("Currency", ["usd", "gbp", "eur"], index=0)
    top_n = st.slider("Show top N coins", 5, 25, 10)
    search_term = st.text_input("Search coin name or symbol", value="")
    refresh = st.button("Refresh data")

if refresh:
    st.cache_data.clear()

@st.cache_data(ttl=900)
def build_table(vs_currency):
    try:
        df = fetch_top_markets(vs_currency=vs_currency, page=1)
        if df.empty:
            return df, None

        df = df.head(10).copy()

        rows = []
        for _, r in df.iterrows():
            rows.append({
                "name": r.get("name"),
                "symbol": r.get("symbol"),
                "current_price": r.get("current_price"),
                "market_cap": r.get("market_cap"),
                "price_change_percentage_24h_in_currency": r.get("price_change_percentage_24h_in_currency"),
                "price_change_percentage_7d_in_currency": r.get("price_change_percentage_7d_in_currency"),
                "price_change_percentage_30d_in_currency": r.get("price_change_percentage_30d_in_currency"),
            })

        out = pd.DataFrame(rows)

        out["momentum_score"] = normalize_series(out["price_change_percentage_30d_in_currency"])
        out["strength_score"] = normalize_series(out["price_change_percentage_7d_in_currency"])
        out["cap_score"] = normalize_series(np.log10(out["market_cap"].replace(0, np.nan)))

        out["final_score"] = (
            0.5 * out["momentum_score"] +
            0.3 * out["strength_score"] +
            0.2 * out["cap_score"]
        )

        out["explanation"] = out.apply(
            lambda row: (
                f"Momentum: {row['price_change_percentage_30d_in_currency']:.1f}% over 30 days. "
                f"7D move: {row['price_change_percentage_7d_in_currency']:.1f}%. "
                f"24H move: {row['price_change_percentage_24h_in_currency']:.1f}%. "
                f"Market cap: {row['market_cap']:,}."
            ),
            axis=1
        )

        out = out.sort_values("final_score", ascending=False)
        return out, None

    except Exception as e:
        return pd.DataFrame(), str(e)

@st.cache_data(ttl=900)
def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

with st.spinner("Loading market data..."):
    df, err = build_table(vs_currency)

if err:
    st.error(f"Could not load data right now: {err}")
    st.info("Try again in a minute. This version uses fewer API calls and safer DataFrame building.")
    st.stop()

if df.empty:
    st.warning("No data returned from CoinGecko.")
    st.stop()

if search_term.strip():
    term = search_term.strip().lower()
    df = df[
        df["name"].str.lower().str.contains(term, na=False)
        | df["symbol"].str.lower().str.contains(term, na=False)
    ].copy()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Coins shown", len(df))
c2.metric("Top score", f"{df['final_score'].iloc[0]:.1f}")
c3.metric("Median market cap", f"{df['market_cap'].median():,.0f}")
c4.metric("Last updated", datetime.now().strftime("%Y-%m-%d %H:%M"))

st.download_button(
    label="📥 Download CSV",
    data=csv_bytes(df.head(top_n)),
    file_name="crypto_screener_results.csv",
    mime="text/csv",
)

st.subheader("Top coins")
display_df = df.head(top_n).copy()
display_df = display_df[
    [
        "name", "symbol", "current_price", "market_cap",
        "price_change_percentage_24h_in_currency",
        "price_change_percentage_7d_in_currency",
        "price_change_percentage_30d_in_currency",
        "final_score", "explanation"
    ]
]
display_df.columns = [
    "Name", "Symbol", "Price", "Market Cap",
    "24H %", "7D %", "30D %",
    "Final Score", "Simple Explanation"
]
st.dataframe(display_df, use_container_width=True, height=520)

st.subheader("Score chart")
fig = px.bar(df.head(top_n), x="name", y="final_score", color="final_score", title="Top Scored Coins")
fig.update_layout(xaxis_title="", yaxis_title="Final Score")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Methodology"):
    st.write(
        "This version only uses one CoinGecko market page and builds rows safely before converting to a DataFrame."
)
