import streamlit as st
import requests
import pandas as pd
import re
from datetime import date, timedelta

# ============================================================
# CONFIG
# ============================================================
st.set_page_config("NSE Order Intelligence", layout="wide", page_icon="📦")
st.title("📦 NSE Big Order Intelligence – Institutional Dashboard")

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
# FETCH CORPORATE ANNOUNCEMENTS (HISTORICAL)
# ============================================================
@st.cache_data(ttl=900)
def fetch_orders(start_date, end_date):
    s = nse_session()
    s.get("https://www.nseindia.com", timeout=5)

    url = "https://www.nseindia.com/api/corporate-announcements"
    params = {
        "index": "equities",
        "from_date": start_date.strftime("%d-%m-%Y"),
        "to_date": end_date.strftime("%d-%m-%Y")
    }
    r = s.get(url, params=params, timeout=10)
    df = pd.DataFrame(r.json())
    if df.empty:
        return df
    df["Date"] = pd.to_datetime(df["sort_date"])
    return df

# ============================================================
# FETCH EQUITY SNAPSHOT
# ============================================================
@st.cache_data(ttl=900)
def fetch_equity(symbol):
    try:
        s = nse_session()
        s.get("https://www.nseindia.com", timeout=5)
        r = s.get(f"https://www.nseindia.com/api/quote-equity?symbol={symbol}", timeout=5)
        d = r.json()
        return {
            "mcap": d.get("metadata", {}).get("marketCap"),
            "sector": d.get("metadata", {}).get("industry", "NA"),
            "prevClose": d.get("priceInfo", {}).get("previousClose"),
            "lastPrice": d.get("priceInfo", {}).get("lastPrice"),
        }
    except:
        return None

# ============================================================
# TEXT HELPERS
# ============================================================
def extract_order_value(text):
    m = re.search(r"(₹|Rs\.?)\s?([\d,]+)\s?crore", text, re.I)
    return float(m.group(2).replace(",", "")) if m else None

def extract_duration(text):
    m = re.search(r"(within|over|in)\s(\d+)\s(year|years|month|months)", text, re.I)
    return f"{m.group(2)} {m.group(3)}" if m else "Not Specified"

def classify_price_impact(text):
    t = text.lower()
    if any(k in t for k in ["order", "contract", "award", "project", "acquisition", "capacity"]):
        return "🔥 High"
    if any(k in t for k in ["agreement", "strategic", "subsidiary"]):
        return "⚠ Medium"
    return "ℹ Low"

def make_clickable(url):
    return f'<a href="{url}" target="_blank">📄 PDF</a>'

# ============================================================
# UI CONTROLS
# ============================================================
col1, col2 = st.columns(2)
end_date = col2.date_input("📅 To Date", date.today())
start_date = col1.date_input("📅 From Date", end_date - timedelta(days=30))

desc_filter = st.multiselect(
    "🔍 Description Filter",
    ["order", "contract", "award", "project", "loa", "acquisition", "rights", "expansion"],
    default=["order", "contract", "award", "project", "loa"]
)

# ============================================================
# MAIN EXECUTION
# ============================================================
if st.button("🚀 Fetch & Analyze"):
    with st.spinner("Fetching NSE data…"):
        orders = fetch_orders(start_date, end_date)

        if orders.empty:
            st.warning("No NSE announcements received.")
            st.stop()

        pattern = "|".join(desc_filter)
        orders = orders[
            orders["attchmntText"].str.contains(pattern, case=False, na=False)
        ]

        results = []

        for sym in orders["symbol"].unique():
            eq = fetch_equity(sym)
            if not eq or not eq["mcap"]:
                continue

            mcap_cr = eq["mcap"] / 1e7

            for _, r in orders[orders.symbol == sym].iterrows():
                val = extract_order_value(r.attchmntText)
                if not val:
                    continue

                impact = min((val / mcap_cr) * 5, 100)

                next_move = None
                if eq["prevClose"] and eq["lastPrice"]:
                    next_move = round(
                        ((eq["lastPrice"] - eq["prevClose"]) / eq["prevClose"]) * 100, 2
                    )

                results.append({
                    "Stock": sym,
                    "Company": r.sm_name,
                    "Sector": eq["sector"],
                    "Order ₹Cr": round(val, 1),
                    "Market Cap ₹Cr": round(mcap_cr, 0),
                    "Impact Score": round(impact, 1),
                    "Next Day % Move": next_move,
                    "Completion": extract_duration(r.attchmntText),
                    "Price Impact": classify_price_impact(r.attchmntText),
                    "Order Date": r.Date.date(),
                    "Attachment": make_clickable(r.attchmntFile)
                })

        if not results:
            st.warning("No qualifying orders with value found.")
            st.stop()

        df = pd.DataFrame(results)

        # ====================================================
        # MAIN TABLE
        # ====================================================
        st.subheader("🧠 Order Intelligence")
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

        # ====================================================
        # REPEAT ORDER DETECTION
        # ====================================================
        st.subheader("🧮 Repeat Order Detection (Smart Money)")
        repeat_df = (
            df.groupby("Stock", as_index=False)
            .agg(Orders=("Order ₹Cr", "count"), Total_Order_Value=("Order ₹Cr", "sum"))
            .sort_values("Orders", ascending=False)
        )
        st.dataframe(repeat_df, use_container_width=True)

        # ====================================================
        # SECTOR HEATMAP
        # ====================================================
        st.subheader("🏭 Sector Order Flow")
        sector_df = df.groupby("Sector")["Order ₹Cr"].sum()
        st.bar_chart(sector_df)

        # ====================================================
        # IMPACT vs PRICE MOVE
        # ====================================================
        st.subheader("📈 Impact Score vs Next-Day Move")
        scatter_df = df[["Impact Score", "Next Day % Move"]].dropna()
        if not scatter_df.empty:
            st.scatter_chart(scatter_df)

        # ====================================================
        # DOWNLOAD
        # ====================================================
        st.download_button(
            "⬇ Download CSV",
            df.to_csv(index=False),
            "nse_order_intelligence.csv"
        )

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown("""
**Designed by – Gaurav Singh Yadav**  
📦 NSE Order Flow | 🧠 Smart Money Intelligence  
""")
