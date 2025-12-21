import streamlit as st
import requests
import pandas as pd
import re
from datetime import date

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(
    page_title="NSE Order Intelligence",
    layout="wide",
    page_icon="📦"
)

st.title("📦 NSE Big Order Intelligence (All Orders)")

# ============================================================
# SAFE NSE SESSION
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
# FETCH ALL NSE ORDERS (JSON)
# ============================================================
@st.cache_data(ttl=900)
def fetch_nse_orders():
    s = nse_session()
    s.get("https://www.nseindia.com", timeout=5)

    url = "https://www.nseindia.com/api/corporate-announcements?index=equities"
    r = s.get(url, timeout=10)

    df = pd.DataFrame(r.json())

    df = df[df["desc"].str.contains(
        "order|contract|award|project|loa",
        case=False, na=False
    )]

    df["Date"] = pd.to_datetime(df["an_dt"]).dt.date
    return df

# ============================================================
# FETCH EQUITY DATA
# ============================================================
@st.cache_data(ttl=900)
def fetch_nse_equity(symbol):
    try:
        s = nse_session()
        s.get("https://www.nseindia.com", timeout=5)

        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        r = s.get(url, timeout=5)
        data = r.json()

        price = data.get("priceInfo", {})
        meta  = data.get("metadata", {})

        return {
            "marketCap": meta.get("marketCap"),
            "volume": price.get("totalTradedVolume", 0),
            "sector": meta.get("industry", "NA")
        }
    except:
        return None

# ============================================================
# TEXT EXTRACTION
# ============================================================
def extract_order_value(text):
    m = re.search(r"(₹|Rs\.?)\s?([\d,]+)\s?crore", text, re.I)
    return float(m.group(2).replace(",", "")) if m else None

def extract_completion_time(text):
    m = re.search(r"(within|over|in)\s(\d+)\s(year|month|months|years)", text, re.I)
    return f"{m.group(2)} {m.group(3)}" if m else "Not Specified"

# ============================================================
# UI
# ============================================================
st.info("⚠ NSE APIs are called **only after clicking the button**")

col1, col2 = st.columns(2)
start_date = col1.date_input("📅 Start Date", date.today().replace(day=1))
end_date   = col2.date_input("📅 End Date", date.today())

if st.button("🚀 Fetch & Analyze NSE Orders"):
    with st.spinner("Fetching NSE announcements…"):
        try:
            orders = fetch_nse_orders()

            # Date Filter
            orders = orders[
                (orders["Date"] >= start_date) &
                (orders["Date"] <= end_date)
            ]

            st.subheader("🔁 NSE Order Announcements")
            st.dataframe(
                orders[["symbol", "desc", "Date"]],
                use_container_width=True
            )

            results = []

            for sym in orders["symbol"].unique():
                eq = fetch_nse_equity(sym)
                if not eq or not eq["marketCap"]:
                    continue

                mcap_cr = eq["marketCap"] / 1e7

                for _, r in orders[orders.symbol == sym].iterrows():
                    order_val = extract_order_value(r.desc)
                    if not order_val:
                        continue

                    impact = min((order_val / mcap_cr) * 5, 100)

                    results.append({
                        "Stock": sym,
                        "Order ₹Cr": round(order_val, 1),
                        "Market Cap ₹Cr": round(mcap_cr, 0),
                        "Order % MCap": round((order_val / mcap_cr) * 100, 2),
                        "Completion Time": extract_completion_time(r.desc),
                        "Sector": eq["sector"],
                        "Impact Score": round(impact, 1),
                        "Order Date": r.Date
                    })

            if results:
                df = pd.DataFrame(results).sort_values(
                    "Impact Score", ascending=False
                )

                st.subheader("🧠 Order Impact Ranking")
                st.dataframe(
                    df.style.background_gradient(
                        subset=["Impact Score"],
                        cmap="RdYlGn"
                    ),
                    use_container_width=True
                )

                st.download_button(
                    "⬇ Download Order Book (CSV)",
                    df.to_csv(index=False),
                    file_name="nse_order_intelligence.csv"
                )
            else:
                st.warning("No qualifying orders found in selected date range.")

        except Exception as e:
            st.error("NSE blocked the request. Retry later.")
            st.code(str(e))

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown("""
**Designed by – Gaurav Singh Yadav**  
📦 NSE Order Flow | 🧠 Institutional Tracking  
""")
