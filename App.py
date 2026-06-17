import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from utils import fetch_top_markets, normalize_series, explain_row

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
        df["momentum_score"] = normalize_series(df["price_change_percentage_30d_in_currency"])
        df["strength_score"] = normalize_series(df["price_change_percentage_7d_in_currency"])
        df["cap_score"] = normalize_series(
            (df["market_cap"].replace(0, pd.NA)).astype(float).apply(
                lambda x: None if pd.isna(x) else __import__("numpy").log10(x)
            )
        )
        df["final_score"] = (
            0.5 * df["momentum_score"] +
            0.3 * df["strength_score"] +
            0.2 * df["cap_score"]
        )
        df["explanation"] = df.apply(explain_row, axis=1)
        df = df.sort_values("final_score", ascending=False)
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

with st.spinner("Loading market data..."):
    df, err = build_table(vs_currency)

if err:
    st.error(f"Could not load data right now: {err}")
    st.info("Try again in a minute. This super-light version uses fewer API calls.")
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

st.subheader("Top coins")

download_df = df.head(top_n).copy()
download_df.columns = [
    "Coin", "Symbol", "Price", "Market Cap",
    "24H %", "7D %", "30D %",
    "Momentum Score", "Strength Score", "Cap Score",
    "Final Score", "Simple Explanation"
]

st.download_button(
    label="📥 Download CSV",
    data=download_df.to_csv(index=False).encode("utf-8"),
    file_name="crypto_screener_results.csv",
    mime="text/csv",
)

show_cols = [
    "name", "symbol", "current_price", "market_cap",
    "price_change_percentage_24h_in_currency",
    "price_change_percentage_7d_in_currency",
    "price_change_percentage_30d_in_currency",
    "final_score", "explanation"
]
display_df = df[show_cols].head(top_n).copy()
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
        "This version only uses CoinGecko market data from one page and avoids extra chart requests, which makes it much more stable."
    )
