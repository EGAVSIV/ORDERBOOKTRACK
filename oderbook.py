import streamlit as st
import requests
import pandas as pd
import re
from datetime import date, timedelta
import time

import hashlib

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
# NSE SCAN TRIGGER FLAG (MUST BE AFTER LOGIN)
# ============================================================
if "run_nse_scan" not in st.session_state:
    st.session_state.run_nse_scan = False



# ============================================================
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(
    page_title="NSE Order Intelligence",
    layout="wide",
    page_icon="📦"
)

# 🔄 MANUAL + AUTO REFRESH (NO EXTERNAL LIB)
# =====================================================
c1, c2, c3 = st.columns([1.2, 1.8, 6])

with c1:
    if st.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.session_state.run_nse_scan = True
        st.rerun()

with c2:
    auto_refresh = st.toggle("⏱ Auto Refresh (45 min)", value=False)

with c3:
    st.caption("Manual refresh forces fresh to Get Recent Communication to NSE from Companies")
# =====================================================
# AUTO REFRESH TIMER (SAFE)
# =====================================================
if auto_refresh:
    now = time.time()
    last = st.session_state.get("last_refresh", 0)

    if now - last > 45 * 60:  # 1 minute
        st.session_state["last_refresh"] = now
        st.cache_data.clear()
        st.session_state.run_nse_scan = True
        st.rerun()

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
# FETCH HISTORICAL NSE ORDERS (REAL ARCHIVE)
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

        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        r = s.get(url, timeout=5)
        data = r.json()

        price = data.get("priceInfo", {})
        meta = data.get("metadata", {})

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
    m = re.search(r"(within|over|in)\s(\d+)\s(year|years|month|months)", text, re.I)
    return f"{m.group(2)} {m.group(3)}" if m else "Not Specified"

# ============================================================
# MAKE PDF LINK CLICKABLE
# ============================================================
def make_clickable(url):
    return f'<a href="{url}" target="_blank">📄 Open PDF</a>'

# ============================================================
# UI – DATE SELECTION
# ============================================================
st.info("⚠ NSE APIs are called **only after clicking the button**")

col1, col2 = st.columns(2)
end_date = col2.date_input("📅 To Date", date.today())
start_date = col1.date_input(
    "📅 From Date",
    end_date - timedelta(days=1)
)

if st.session_state.run_nse_scan:



st.markdown("""
---
**Designed by:-  
Gaurav Singh Yadav**   
🩷💛🩵💙🩶💜🤍🤎💖  Built With Love 🫶  
📦 NSE Order Flow | 🧠 Institutional Intelligence  
📱 +91-8003994518 〽️   
📧 yadav.gauravsingh@gmail.com ™️
""")
