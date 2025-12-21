# ============================================================
# NSE ORDER + VOLUME + BREAKOUT + IMPACT SCORE DASHBOARD
# ============================================================

import streamlit as st
import requests
import pandas as pd
import re
import numpy as np
import pandas_ta as ta

# ============================================================
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(
    page_title="NSE Order Intelligence",
    layout="wide",
    page_icon="📦"
)

st.title("📦 NSE Big Order Intelligence Dashboard")

# ============================================================
# NSE ANNOUNCEMENT FETCHER (SAFE)
# ============================================================
@st.cache_data(ttl=300)
def fetch_nse_orders_safe():
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        })

        session.get("https://www.nseindia.com", timeout=5)

        url = "https://www.nseindia.com/api/corporate-announcements?index=equities"
        r = session.get(url, timeout=5)

        df = pd.DataFrame(r.json())

        df = df[df["desc"].str.contains(
            "order|contract|award|project|loa",
            case=False,
            na=False
        )]

        df["Date"] = pd.to_datetime(df["an_dt"]).dt.date
        return df[["symbol", "desc", "Date"]]

    except Exception:
        return pd.DataFrame(columns=["symbol", "desc", "Date"])

# ============================================================
# ORDER VALUE EXTRACTION
# ============================================================
def extract_order_value(text):
    patterns = [
        r"₹\s?([\d,]+)\s?crore",
        r"Rs\.?\s?([\d,]+)\s?crore"
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))
    return None

# ============================================================
# MOCK FINANCIAL DATA
# ============================================================
FIN_DATA = {
    "LT": {"mcap": 450000, "revenue": 210000, "roce": 18, "de": 0.9},
    "HAL": {"mcap": 310000, "revenue": 56000, "roce": 26, "de": 0.0},
    "RVNL": {"mcap": 18000, "revenue": 19000, "roce": 14, "de": 1.1},
}

# ============================================================
# MOCK PRICE DATA
# ============================================================
def get_mock_price_data():
    np.random.seed(0)
    return pd.DataFrame({
        "Close": np.cumsum(np.random.randn(120)) + 100,
        "High": np.cumsum(np.random.randn(120)) + 102,
        "Volume": np.random.randint(1e5, 5e5, 120)
    })

# ============================================================
# BREAKOUT + VOLUME LOGIC (NO TALIB)
# ============================================================
def check_breakout(df):
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)
    df["HH20"] = df["High"].rolling(20).max()
    df["VolAvg"] = df["Volume"].rolling(20).mean()

    last = df.iloc[-1]

    return (
        last.Close > last.HH20 and
        last.Volume > 2 * last.VolAvg and
        last.EMA20 > last.EMA50
    )

# ============================================================
# IMPACT SCORE
# ============================================================
def impact_score(order, mcap, revenue, roce, breakout):
    score = 0
    score += min((order / mcap) * 100 * 4, 40)
    score += min((order / revenue) * 100 * 0.5, 25)
    score += min(roce, 30) * 0.66
    score += 15 if breakout else 0
    return round(min(score, 100), 1)

# ============================================================
# UI – FETCH NSE DATA
# ============================================================
orders = pd.DataFrame(columns=["symbol", "desc", "Date"])

st.subheader("🔁 NSE Order Announcements")

if st.button("🔄 Fetch Latest NSE Orders"):
    orders = fetch_nse_orders_safe()

st.dataframe(orders, use_container_width=True)

# ============================================================
# PROCESS & RANK
# ============================================================
results = []

for _, r in orders.iterrows():
    sym = r.symbol
    order_val = extract_order_value(r.desc)

    if sym not in FIN_DATA or not order_val:
        continue

    fin = FIN_DATA[sym]
    price_df = get_mock_price_data()
    breakout = check_breakout(price_df)

    score = impact_score(
        order_val,
        fin["mcap"],
        fin["revenue"],
        fin["roce"],
        breakout
    )

    results.append({
        "Stock": sym,
        "Order ₹Cr": order_val,
        "Order % MCap": round(order_val / fin["mcap"] * 100, 2),
        "ROCE %": fin["roce"],
        "Debt/Equity": fin["de"],
        "Breakout": "YES" if breakout else "NO",
        "Impact Score": score
    })

if results:
    df_rank = pd.DataFrame(results).sort_values("Impact Score", ascending=False)
    st.subheader("🧠 Order Impact Ranking")
    st.dataframe(df_rank, use_container_width=True)
else:
    st.warning("No high-quality order announcements detected yet.")

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown("""
**Designed by – Gaurav Singh Yadav**  
📦 Order Flow | 📊 Breakout | 🧠 Quant Intelligence  
""")
