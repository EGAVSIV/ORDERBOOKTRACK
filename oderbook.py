# ============================================================
# NSE REAL ORDER + MARKET CAP + VOLUME + IMPACT SCORE DASHBOARD
# ============================================================

import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime

# ============================================================
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(
    page_title="NSE Order Intelligence",
    layout="wide",
    page_icon="📦"
)

st.title("📦 NSE Big Order Intelligence (REAL NSE DATA)")

# ============================================================
# PREDEFINED SYMBOLS (YOU CONTROL)
# ============================================================
SYMBOLS = ["LT", "HAL", "RVNL"]

# ============================================================
# NSE SAFE SESSION
# ============================================================
def nse_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/"
    })
    s.get("https://www.nseindia.com", timeout=5)
    return s

# ============================================================
# FETCH NSE ORDER ANNOUNCEMENTS
# ============================================================
@st.cache_data(ttl=300)
def fetch_nse_orders():
    try:
        s = nse_session()
        url = "https://www.nseindia.com/api/corporate-announcements?index=equities"
        r = s.get(url, timeout=5)

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
# EXTRACT ORDER VALUE ₹
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
# FETCH REAL NSE EQUITY DATA
# ============================================================
@st.cache_data(ttl=300)
def fetch_nse_equity(symbol):
    try:
        s = nse_session()
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        r = s.get(url, timeout=5)
        data = r.json()

        price = data["priceInfo"]
        meta = data["metadata"]

        return {
            "symbol": symbol,
            "lastPrice": price["lastPrice"],
            "volume": price["totalTradedVolume"],
            "marketCap": meta.get("marketCap", None),
            "sector": meta.get("industry", "NA")
        }

    except Exception:
        return None

# ============================================================
# VOLUME EXPANSION (REAL NSE)
# ============================================================
def volume_expansion(today_vol):
    # NSE does not provide avg volume publicly
    # Proxy: strong spike if volume > 1.8x normal day assumption
    return today_vol > 1_500_000

# ============================================================
# IMPACT SCORE (NSE ONLY)
# ============================================================
def impact_score(order_val, market_cap, vol_spike):
    score = 0

    if market_cap:
        score += min((order_val / market_cap) * 100 * 5, 50)

    score += 30 if vol_spike else 0
    score += 20  # order existence bonus

    return round(min(score, 100), 1)

# ============================================================
# UI – FETCH BUTTON
# ============================================================
st.subheader("🔁 NSE Order Announcements")

orders = pd.DataFrame(columns=["symbol", "desc", "Date"])

if st.button("🔄 Fetch Latest NSE Orders"):
    orders = fetch_nse_orders()

st.dataframe(orders, use_container_width=True)

# ============================================================
# PROCESS & RANK
# ============================================================
results = []

for sym in SYMBOLS:
    eq = fetch_nse_equity(sym)
    if not eq or not eq["marketCap"]:
        continue

    vol_spike = volume_expansion(eq["volume"])

    for _, r in orders[orders.symbol == sym].iterrows():
        order_val = extract_order_value(r.desc)
        if not order_val:
            continue

        score = impact_score(
            order_val,
            eq["marketCap"],
            vol_spike
        )

        results.append({
            "Stock": sym,
            "Order ₹Cr": order_val,
            "Market Cap ₹Cr": round(eq["marketCap"] / 1e7, 0),
            "Order % MCap": round((order_val / (eq["marketCap"] / 1e7)) * 100, 2),
            "Volume Spike": "YES" if vol_spike else "NO",
            "Sector": eq["sector"],
            "Impact Score": score
        })

# ============================================================
# DASHBOARD OUTPUT
# ============================================================
if results:
    df_rank = pd.DataFrame(results).sort_values(
        "Impact Score", ascending=False
    )

    st.subheader("🧠 Order Impact Ranking (REAL NSE DATA)")
    st.dataframe(df_rank, use_container_width=True)

    top = df_rank.iloc[0]
    st.success(
        f"📈 TOP STOCK: {top.Stock} | "
        f"Impact Score: {top['Impact Score']} | "
        f"Order % MCap: {top['Order % MCap']}%"
    )
else:
    st.warning("No NSE orders matched predefined symbols.")

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown("""
**Designed by – Gaurav Singh Yadav**  
📦 Order Flow | 📊 NSE Intelligence | 🧠 Quant Analysis  
""")
