import requests
import pandas as pd
import numpy as np
from functools import lru_cache

API_BASE = "https://api.coingecko.com/api/v3"

class CoinGeckoError(Exception):
    pass

def _get(url, params=None):
    r = requests.get(url, params=params, timeout=30)
    if not r.ok:
        raise CoinGeckoError(f"{r.status_code} error from CoinGecko")
    return r

@lru_cache(maxsize=16)
def get_markets(vs_currency="usd", page=1):
    url = f"{API_BASE}/coins/markets"
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": 250,
        "page": page,
        "sparkline": False,
        "price_change_percentage": "24h,7d,30d",
    }
    return _get(url, params=params).json()

@lru_cache(maxsize=4)
def get_market_chart(coin_id, days=90, vs_currency="usd"):
    url = f"{API_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": vs_currency, "days": days, "interval": "daily"}
    return _get(url, params=params).json()

def fetch_all_markets(vs_currency="usd", max_pages=8):
    rows = []
    for page in range(1, max_pages + 1):
        batch = get_markets(vs_currency=vs_currency, page=page)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 250:
            break
    return pd.DataFrame(rows)

def safe_pct_change(a, b):
    if a is None or b is None or b == 0:
        return np.nan
    return (a - b) / b * 100

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
        f"Momentum: {row['momentum_30d_pct']:.1f}% over 30 days. "
        f"Relative strength: {row['rel_strength_7d_pct']:.1f}% over 7 days. "
        f"Market cap: {row['market_cap']:,}. "
        f"Distance from 90-day high: {row['dist_90d_high_pct']:.1f}% below the peak."
    )
