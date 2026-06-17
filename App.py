import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from utils import fetch_all_markets, get_market_chart, safe_pct_change, normalize_series, explain_row

st.set_page_config(
    page_title="Crypto Screener",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("🪙 Live Crypto Screener")
st.caption("Mobile-first Streamlit app for CoinGecko coins with editable weights and simple explanations.")

with st.sidebar:
    st.header("Settings")
    vs_currency = st.selectbox("Currency", ["usd", "gbp", "eur"], index=0)
    max_pages = st.slider("Max pages to fetch", 1, 4, 2)
    top_n = st.slider("Show top N coins", 10, 100, 30)
    min_market_cap = st.number_input("Minimum market cap", min_value=0, value=0, step=1000000)
    search_term = st.text_input("Search coin name or symbol", value="")
    compact_view = st.toggle("Compact mobile view", value=True)

    st.subheader("Weights")
    w_momentum = st.slider("Momentum", 0.0, 5.0, 2.0, 0.1)
    w_rel_strength = st.slider("Relative strength", 0.0, 5.0, 2.0, 0.1)
    w_market_cap = st.slider("Market cap", 0.0, 5.0, 1.0, 0.1)
    w_dist_high = st.slider("Distance from 90-day high", 0.0, 5.0, 1.5, 0.1)
    refresh = st.button("Refresh data")

if refresh:
    st.cache_data.clear()

@st.cache_data(ttl=900)
def build_table(vs_currency, max_pages, min_market_cap):
    try:
        df = fetch_all_markets(vs_currency=vs_currency, max_pages=max_pages)
        if df.empty:
            return df, None

        df = df.rename(columns={"id": "coin_id"})
        df = df[df["market_cap"].fillna(0) >= min_market_cap].copy()

        momentum_30d = []
        rel_strength_7d = []
        dist_90d_high = []

        for coin_id in df["coin_id"].head(25):
            try:
                chart = get_market_chart(coin_id, days=90, vs_currency=vs_currency)
                prices = chart.get("prices", [])
                if len(prices) < 2:
                    momentum_30d.append(pd.NA)
                    rel_strength_7d.append(pd.NA)
                    dist_90d_high.append(pd.NA)
                    continue

                p = pd.DataFrame(prices, columns=["ts", "price"])
                latest = p["price"].iloc[-1]
                price_30d = p["price"].iloc[max(0, len(p) - 31)]
                price_7d = p["price"].iloc[max(0, len(p) - 8)]
                high_90d = p["price"].max()

                momentum_30d.append(safe_pct_change(latest, price_30d))
                rel_strength_7d.append(safe_pct_change(latest, price_7d))
                dist_90d_high.append(safe_pct_change(high_90d, latest))
            except Exception:
                momentum_30d.append(pd.NA)
                rel_strength_7d.append(pd.NA)
                dist_90d_high.append(pd.NA)

        df = df.head(25).copy()
        df["momentum_30d_pct"] = momentum_30d[:len(df)]
        df["rel_strength_7d_pct"] = rel_strength_7d[:len(df)]
        df["dist_90d_high_pct"] = dist_90d_high[:len(df)]
        df["momentum_score"] = normalize_series(df["momentum_30d_pct"])
        df["strength_score"] = normalize_series(df["rel_strength_7d_pct"])
        df["cap_score"] = normalize_series(
            (df["market_cap"].replace(0, pd.NA)).astype(float).apply(
                lambda x: None if pd.isna(x) else __import__("numpy").log10(x)
            )
        )
        df["high_score"] = normalize_series(df["dist_90d_high_pct"], invert=True)
        df["final_score"] = (
            w_momentum * df["momentum_score"]
            + w_rel_strength * df["strength_score"]
            + w_market_cap * df["cap_score"]
            + w_dist_high * df["high_score"]
        )
        df["explanation"] = df.apply(explain_row, axis=1)
        df = df.sort_values("final_score", ascending=False)
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

@st.cache_data(ttl=900)
def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

with st.spinner("Loading and scoring coins..."):
    df, err = build_table(vs_currency, max_pages, min_market_cap)

if err:
    st.error(f"Could not load data right now: {err}")
    st.info("This may be a temporary CoinGecko rate limit or network issue. Try again in a minute and press Refresh data.")
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

if compact_view:
    st.write(f"Showing {min(top_n, len(df))} coins in compact mode.")

download_df = df.head(top_n).copy()
download_df.columns = [
    "Name", "Symbol", "Price", "Market Cap",
    "30D Momentum %", "7D Relative Strength %",
    "Distance from 90D High %", "Final Score", "Simple Explanation"
]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Coins scored", len(df))
c2.metric("Top final score", f"{df['final_score'].iloc[0]:.1f}")
c3.metric("Median market cap", f"{df['market_cap'].median():,.0f}")
c4.metric("Last updated", datetime.now().strftime("%Y-%m-%d %H:%M"))

st.download_button(
    label="📥 Download CSV",
    data=csv_bytes(download_df),
    file_name="crypto_screener_results.csv",
    mime="text/csv",
)

st.subheader("Top coins")
cols = [
    "name", "symbol", "current_price", "market_cap",
    "momentum_30d_pct", "rel_strength_7d_pct",
    "dist_90d_high_pct", "final_score", "explanation"
]
display_df = df[cols].head(top_n).copy()
display_df.columns = [
    "Name", "Symbol", "Price", "Market Cap",
    "30D Momentum %", "7D Relative Strength %",
    "Distance from 90D High %", "Final Score", "Simple Explanation"
]
st.dataframe(display_df, use_container_width=True, height=540 if compact_view else 700)

st.subheader("Score chart")
fig = px.bar(df.head(top_n), x="name", y="final_score", color="final_score", title="Top Scored Coins")
fig.update_layout(xaxis_title="", yaxis_title="Final Score")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Methodology"):
    st.write(
        "Momentum, relative strength, market cap, and distance from 90-day high are normalized to 0–100 and combined using your chosen weights."
    )
