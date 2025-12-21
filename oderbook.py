import streamlit as st
import requests
import pandas as pd
import re

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(
    page_title="NSE Order Intelligence",
    layout="wide",
    page_icon="📦"
)

st.title("📦 NSE Big Order Intelligence (Cloud Safe)")

SYMBOLS = ["LT", "HAL", "RVNL"]

# ============================================================
# SAFE NSE SESSION (CREATED ONLY WHEN CALLED)
# ============================================================
def nse_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/"
    })
    return s

# ============================================================
# FETCH NSE ORDERS (ON-DEMAND ONLY)
# ============================================================
def fetch_nse_orders():
    s = nse_session()
    s.get("https://www.nseindia.com", timeout=5)

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

# ============================================================
# FETCH NSE EQUITY (ON-DEMAND ONLY)
# ============================================================
def fetch_nse_equity(symbol):
    s = nse_session()
    s.get("https://www.nseindia.com", timeout=5)

    url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
    r = s.get(url, timeout=5)
    data = r.json()

    price = data["priceInfo"]
    meta = data["metadata"]

    return {
        "symbol": symbol,
        "marketCap": meta.get("marketCap"),
        "volume": price.get("totalTradedVolume"),
        "sector": meta.get("industry", "NA")
    }

# ============================================================
# EXTRACT ORDER VALUE
# ============================================================
def extract_order_value(text):
    m = re.search(r"(₹|Rs\.?)\s?([\d,]+)\s?crore", text, re.I)
    return float(m.group(2).replace(",", "")) if m else None

# ============================================================
# UI – NOTHING BLOCKING ABOVE THIS LINE
# ============================================================

st.info("⚠ NSE APIs are called **only after clicking the button**")

if st.button("🚀 Fetch NSE Orders & Rank Impact"):
    with st.spinner("Fetching data from NSE…"):

        try:
            orders = fetch_nse_orders()
            st.subheader("🔁 NSE Order Announcements")
            st.dataframe(orders, use_container_width=True)

            results = []

            for sym in SYMBOLS:
                eq = fetch_nse_equity(sym)
                if not eq or not eq["marketCap"]:
                    continue

                for _, r in orders[orders.symbol == sym].iterrows():
                    order_val = extract_order_value(r.desc)
                    if not order_val:
                        continue

                    impact = min((order_val / (eq["marketCap"] / 1e7)) * 5, 100)

                    results.append({
                        "Stock": sym,
                        "Order ₹Cr": order_val,
                        "Market Cap ₹Cr": round(eq["marketCap"] / 1e7, 0),
                        "Order % MCap": round((order_val / (eq["marketCap"] / 1e7)) * 100, 2),
                        "Sector": eq["sector"],
                        "Impact Score": round(impact, 1)
                    })

            if results:
                df = pd.DataFrame(results).sort_values(
                    "Impact Score", ascending=False
                )

                st.subheader("🧠 Order Impact Ranking")
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("No matching NSE orders for predefined symbols.")

        except Exception as e:
            st.error("NSE blocked the request. Please retry later.")
            st.code(str(e))

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown("""
**Designed by – Gaurav Singh Yadav**  
📦 NSE Order Flow | 🧠 Institutional Tracking  
""")
