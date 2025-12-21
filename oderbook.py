import streamlit as st
import requests
import pandas as pd
import re
import pdfplumber
from datetime import date, timedelta
from io import BytesIO

# ============================================================
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(
    page_title="NSE Order Intelligence",
    layout="wide",
    page_icon="📦"
)

st.title("📦 NSE Big Order Intelligence – Historical")

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
# FETCH HISTORICAL NSE ORDERS
# ============================================================
@st.cache_data(ttl=900)
def fetch_nse_orders_range(start_date, end_date):
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
# FETCH NSE EQUITY DATA
# ============================================================
@st.cache_data(ttl=900)
def fetch_nse_equity(symbol):
    try:
        s = nse_session()
        s.get("https://www.nseindia.com", timeout=5)
        r = s.get(f"https://www.nseindia.com/api/quote-equity?symbol={symbol}", timeout=5)
        d = r.json()
        return {
            "marketCap": d.get("metadata", {}).get("marketCap"),
            "sector": d.get("metadata", {}).get("industry", "NA")
        }
    except:
        return None

# ============================================================
# TEXT EXTRACTION (DESC)
# ============================================================
def extract_order_value(text):
    m = re.search(r"(₹|Rs\.?)\s?([\d,]+)\s?crore", text, re.I)
    return float(m.group(2).replace(",", "")) if m else None

def extract_completion_time(text):
    m = re.search(r"(by|within|over|on or before)\s.*?(\d{4})", text, re.I)
    return m.group(0) if m else "Not Specified"

# ============================================================
# PDF PARSING (SAFE)
# ============================================================
def parse_pdf_for_order_details(pdf_url):
    try:
        r = requests.get(pdf_url, timeout=10)
        with pdfplumber.open(BytesIO(r.content)) as pdf:
            text = " ".join(page.extract_text() or "" for page in pdf.pages)

        order_val = extract_order_value(text)

        target = re.search(
            r"(by|within|on or before)\s.*?(20\d{2})",
            text,
            re.I
        )
        target_date = target.group(0) if target else "Not Mentioned"

        return order_val, target_date

    except:
        return None, "NA"

# ============================================================
# CLICKABLE LINK
# ============================================================
def make_clickable(url):
    return f'<a href="{url}" target="_blank">📄 Open PDF</a>'

# ============================================================
# UI – DATE SELECTION
# ============================================================
st.info("⚠ NSE APIs are called **only after clicking the button**")

col1, col2 = st.columns(2)
end_date = col2.date_input("📅 To Date", date.today())
start_date = col1.date_input("📅 From Date", end_date - timedelta(days=30))

if st.button("🚀 Fetch & Analyze NSE Orders"):
    with st.spinner("Fetching & analyzing NSE announcements…"):
        try:
            orders = fetch_nse_orders_range(start_date, end_date)

            orders = orders[
                orders["attchmntText"].str.contains(
                    "bagging|receiving|order|contract|award|project|loa",
                    case=False, na=False
                )
            ]

            results = []

            for sym in orders["symbol"].unique():
                eq = fetch_nse_equity(sym)
                if not eq or not eq["marketCap"]:
                    continue

                mcap_cr = eq["marketCap"] / 1e7

                for _, r in orders[orders.symbol == sym].iterrows():
                    desc_val = extract_order_value(r.attchmntText)

                    pdf_val, target_date = parse_pdf_for_order_details(r.attchmntFile)

                    final_order_val = pdf_val or desc_val
                    if not final_order_val:
                        continue

                    order_pct = round((final_order_val / mcap_cr) * 100, 2)

                    results.append({
                        "Stock": sym,
                        "Company": r.sm_name,
                        "Market Cap ₹Cr": round(mcap_cr, 0),
                        "Order Value ₹Cr": round(final_order_val, 1),
                        "Order % of MCap": order_pct,
                        "Target / Completion": target_date,
                        "Sector": eq["sector"],
                        "Order Date": r.Date.date(),
                        "PDF": make_clickable(r.attchmntFile)
                    })

            if not results:
                st.warning("No valid order data extracted.")
                st.stop()

            df = pd.DataFrame(results).sort_values(
                "Order % of MCap", ascending=False
            )

            st.subheader("🧠 NSE Order Intelligence (Enriched)")
            st.markdown(
                df.to_html(escape=False, index=False),
                unsafe_allow_html=True
            )

            st.download_button(
                "⬇ Download CSV",
                df.to_csv(index=False),
                "nse_order_intelligence_enriched.csv"
            )

        except Exception as e:
            st.error("Error occurred while processing NSE data.")
            st.code(str(e))

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown("""
**Designed by – Gaurav Singh Yadav**  
📦 NSE Order Flow | 🧠 Institutional Intelligence  
""")
