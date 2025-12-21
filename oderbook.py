import streamlit as st
import requests
import pandas as pd
import re
from datetime import date, timedelta

# ============================================================
# STREAMLIT CONFIG
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
# FETCH HISTORICAL CORPORATE ANNOUNCEMENTS
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

        r = s.get(
            f"https://www.nseindia.com/api/quote-equity?symbol={symbol}",
            timeout=5
        )
        data = r.json()
        return {
            "mcap": data.get("metadata", {}).get("marketCap"),
            "sector": data.get("metadata", {}).get("industry", "NA"),
            "prevClose": data.get("priceInfo", {}).get("previousClose"),
            "lastPrice": data.get("priceInfo", {}).get("lastPrice"),
        }
    except:
        return None

# ============================================================
# TEXT EXTRACTION
# ============================================================
def extract_order_value(text):
    m = re.search(r"(₹|Rs\.?)\s?([\d,]+)\s?crore", text, re.I)
    return float(m.group(2).replace(",", "")) if m else None

def extract_duration(text):
    m = re.search(r"(within|over|in)\s(\d+)\s(year|years|month|months)", text, re.I)
    return f"{m.group(2)} {m.group(3)}" if m else "Not Specified"

def classify_price_impact(text):
    text = text.lower()
    if any(k in text for k in ["order", "contract", "award", "project", "acquisition", "capacity", "expansion"]):
        return "🔥 High"
    if any(k in text for k in ["agreement", "strategic", "subsidiary", "moa"]):
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
# MAIN ACTION
# ============================================================
if st.button("🚀 Fetch & Analyze"):
    with st.spinner("Fetching NSE historical data…"):
        orders = fetch_orders(start_date, end_date)

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

                impact_score = min((val / mcap_cr) * 5, 100)

                next_day_move = None
                if eq["prevClose"] and eq["lastPrice"]:
                    next_day_move = round(
                        ((eq["lastPrice"] - eq["prevClose"]) / eq["prevClose"]) * 100, 2
                    )

                results.append({
                    "Stock": sym,
                    "Company": r.sm_name,
                    "Sector": eq["sector"],
                    "Order ₹Cr": round(val, 1),
                    "Market Cap ₹Cr": round(mcap_cr, 0),
                    "Impact Score": round(impact_score, 1),
                    "Next Day % Move": next_day_move,
                    "Completion": extract_duration(r.attchmntText),
                    "Price Impact": classify_price_impact(r.attchmntText),
                    "Order Date": r.Date.date(),
                    "Attachment": make_clickable(r.attchmntFile)
                })

        df = pd.DataFrame(results)

        # ====================================================
        # MAIN TABLE
        # ====================================================
        st.subheader("🧠 Order Intelligence Table")
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

        # ====================================================
        # REPEAT ORDER DETECTION
        # ====================================================
        st.subheader("🧮 Repeat Order Detection (Smart Money)")
        repeat_df = df.groupby("Stock").agg(
            Orders=("Order ₹Cr", "count"),
            Total_Order_Value=("Order ₹Cr", "sum")
        ).sort_values("Orders", ascending=False)

        st.dataframe(repeat_df, use_container_width=True)

        # ====================================================
        # SECTOR HEATMAP
        # ====================================================
        st.subheader("🏭 Sector Order Heatmap")
        sector_df = df.groupby("Sector")["Order ₹Cr"].sum().reset_index()
        st.bar_chart(sector_df.set_index("Sector"))

        # ====================================================
        # IMPACT vs NEXT DAY MOVE
        # ====================================================
        st.subheader("📈 Impact Score vs Next-Day Price Move")
        st.scatter_chart(
            df[["Impact Score", "Next Day % Move"]].dropna()
        )

        # ====================================================
        # DOWNLOAD
        # ====================================================
        st.download_button(
            "⬇ Download CSV",
            df.to_csv(index=False),
            file_name="nse_order_intelligence_full.csv"
        )

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown("""
**Designed by – Gaurav Singh Yadav**  
📦 NSE Order Flow | 🧠 Smart Money Intelligence  
""")
