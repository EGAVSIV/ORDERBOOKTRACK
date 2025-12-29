import streamlit as st
import requests
import pandas as pd
import re
from datetime import date, timedelta
import time
import hashlib

# ============================================================
# LOGIN
# ============================================================
def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

USERS = st.secrets["users"]

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Login Required")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if u in USERS and hash_pwd(p) == USERS[u]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

# ============================================================
# HELPERS
# ============================================================
def screener_link(symbol):
    return f'<a href="https://www.screener.in/company/{symbol}/consolidated/" target="_blank">📊 Financials</a>'

def make_clickable(url):
    return f'<a href="{url}" target="_blank">📄 Open PDF</a>'

def extract_order_value(text):
    m = re.search(r"(₹|Rs\.?)\s?([\d,]+)\s?crore", text, re.I)
    return float(m.group(2).replace(",", "")) if m else None

def extract_completion_time(text):
    m = re.search(r"(within|over|in)\s(\d+)\s(year|years|month|months)", text, re.I)
    return f"{m.group(2)} {m.group(3)}" if m else "Not Specified"

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
# NSE SESSION
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
# FETCH FUNCTIONS
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

@st.cache_data(ttl=900)
def fetch_nse_equity(symbol):
    try:
        s = nse_session()
        s.get("https://www.nseindia.com", timeout=5)

        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        r = s.get(url, timeout=5)
        data = r.json()

        return {
            "marketCap": data["metadata"].get("marketCap"),
            "sector": data["metadata"].get("industry", "NA")
        }
    except:
        return None

# ============================================================
# DATE SELECTION
# ============================================================
st.info("⚠ NSE APIs are called **only after clicking the button**")

c1, c2 = st.columns(2)
start_date = c1.date_input("📅 From Date", date.today() - timedelta(days=1))
end_date = c2.date_input("📅 To Date", date.today())

if "run_nse_scan" not in st.session_state:
    st.session_state.run_nse_scan = False

if st.button("🚀 Fetch & Analyze NSE Orders"):
    st.cache_data.clear()
    st.session_state.run_nse_scan = True
    st.rerun()

# ============================================================
# MAIN EXECUTION
# ============================================================
if st.session_state.run_nse_scan:
    with st.spinner("Fetching historical NSE announcements…"):
        try:
            st.session_state.run_nse_scan = False

            orders = fetch_nse_orders_range(start_date, end_date)

            orders = orders[
                orders["attchmntText"].str.contains(
                    "order|contract|award|project|agreement|loa",
                    case=False, na=False
                )
            ]

            # ============================================================
            # FILTERS (CORRECT LOCATION)
            # ============================================================
            st.markdown("### 🔎 Filters")

            # ============================================================
            # FILTERS: SYMBOL + DESC (SINGLE SELECT DROPDOWN)
            # ============================================================

            st.markdown("### 🔎 Filters")

            col_f1, col_f2 = st.columns(2)

            # ---------- SYMBOL DROPDOWN ----------
            with col_f1:
                symbol_options = ["All"] + sorted(orders["symbol"].dropna().unique().tolist())
                selected_symbol = st.selectbox(
                    "Select Stock",
                    options=symbol_options,
                    index=0
                )

            # ---------- DESC DROPDOWN ----------
            with col_f2:
                desc_options = ["All"] + sorted(orders["desc"].dropna().unique().tolist())
                selected_desc = st.selectbox(
                    "Select Order Type (DESC)",
                    options=desc_options,
                    index=0
                )

            # ---------- APPLY FILTERS ----------
            if selected_symbol != "All":
                orders = orders[orders["symbol"] == selected_symbol]

            if selected_desc != "All":
                orders = orders[orders["desc"] == selected_desc]


            # ============================================================
            # TABLE 1: RAW ANNOUNCEMENTS
            # ============================================================
            st.subheader("🔁 NSE Order Announcements")

            orders_view = orders[["symbol", "sm_name", "desc", "Date", "attchmntFile"]].copy()
            orders_view["Financials"] = orders_view["symbol"].apply(screener_link)
            orders_view["attchmntFile"] = orders_view["attchmntFile"].apply(make_clickable)

            st.markdown(
                orders_view.to_html(escape=False, index=False),
                unsafe_allow_html=True
            )

            # ============================================================
            # TABLE 2: IMPACT ANALYSIS
            # ============================================================
            results = []

            for sym in orders["symbol"].unique():
                eq = fetch_nse_equity(sym)
                if not eq or not eq["marketCap"]:
                    continue

                market_cap_cr = eq["marketCap"] / 1e7

                for _, r in orders[orders.symbol == sym].iterrows():
                    order_val = extract_order_value(r.attchmntText)
                    if not order_val:
                        continue

                    impact = min((order_val / market_cap_cr) * 5, 100)

                    results.append({
                        "Stock": sym,
                        "Company": r.sm_name,
                        "Order ₹Cr": round(order_val, 1),
                        "Market Cap ₹Cr": round(market_cap_cr, 0),
                        "Order % MCap": round((order_val / market_cap_cr) * 100, 2),
                        "Completion Time": extract_completion_time(r.attchmntText),
                        "Sector": eq["sector"],
                        "Impact Score": round(impact, 1),
                        "Order Date": r.Date.date(),
                        "Financials": screener_link(sym),
                        "PDF Link": make_clickable(r.attchmntFile)
                    })

            if results:
                df = pd.DataFrame(results).sort_values("Impact Score", ascending=False)

                st.subheader("🧠 Order Impact Ranking")
                st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

                st.download_button(
                    "⬇ Download Order Book (CSV)",
                    df.to_csv(index=False),
                    file_name="nse_order_intelligence.csv"
                )
            else:
                st.warning("No qualifying big orders found.")

        except Exception as e:
            st.error("NSE blocked or rate-limited the request.")
            st.code(str(e))

# ============================================================
# FOOTER
# ============================================================
st.markdown("""
---
**Designed by:-  
Gaurav Singh Yadav**  
📦 NSE Order Flow | 🧠 Institutional Intelligence  
📱 +91-8003994518  
📧 yadav.gauravsingh@gmail.com
""")
