import requests
import pandas as pd
import numpy as np
from functools import lru_cache

API_BASE = "https://api.coingecko.com/api/v3"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CryptoScreener/1.0)",
    "Accept": "application/json",
}

class CoinGeckoError(Exception):
    pass

def _get(url, params=None):
    r = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=30)
    if not r.ok:
        raise CoinGeckoError(f"{r.status_code} error from CoinGecko")
    return r

@lru_cache(maxsize=8)
def get_markets(vs_currency="usd", page=1):
    url = f"{API_BASE}/coins/markets"
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": 100,
        "page": page,
        "sparkline": False,
        "price_change_percentage": "24h,7d,30d",
    }
    return _get(url, params=params).json()

def fetch_top_markets(vs_currency="usd", page=1):
    return pd.DataFrame(get_markets(vs_currency=vs_currency, page=page))

def normalize_series(s, invert=False):
    s = s.replace([np.inf, -np.inf], np.nan)
    if s.dropna().empty:
        return pd.Series([50] * len(s), index=s.index)
    mn = s.min()
    mx = s.max()
    out = pd.Series([50] * len(s), index=s.index) if mn == mx else (s - mn) / (mx - mn) * 100
    if invert:
        out = 100 - out
    return out.fillna(out.median() if not out.dropna().empty else 50)

def explain_row(row):
    return (
        f"Momentum: {row['price_change_percentage_30d_in_currency']:.1f}% over 30 days. "
        f"7D move: {row['price_change_percentage_7d_in_currency']:.1f}%. "
        f"24H move: {row['price_change_percentage_24h_in_currency']:.1f}%. "
        f"Market cap: {row['market_cap']:,}."
    )
