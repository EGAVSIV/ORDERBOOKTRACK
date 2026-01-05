# ============================================================
# NSE ORDER INTELLIGENCE – FINAL STABLE VERSION (ENHANCED)
# ============================================================

import streamlit as st
import requests
import pandas as pd
import re
import io
from pypdf import PdfReader
from bs4 import BeautifulSoup
from datetime import date, timedelta
import hashlib

# ============================================================
# LOGIN (SAFE MODE)
# ============================================================
def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

USERS = st.secrets.get("users", {})

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if USERS and not st.session_state.authenticated:
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
else:
    st.session_state.authenticated = True

# ============================================================
# HELPERS
# ============================================================
def screener_link(symbol):
    return f'<a href="https://www.screener.in/company/{symbol}/consolidated/" target="_blank">📊 Financials</a>'

def make_clickable(url):
    return f'<a href="{url}" target="_blank">📄 Open PDF</a>'

# ============================================================
# READ NSE PDF
# ============================================================
@st.cache_data(ttl=3600)
def read_nse_pdf_text(pdf_url):
    try:
        r = requests.get(pdf_url, timeout=20)
        reader = PdfReader(io.BytesIO(r.content))
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text
    except:
        return ""

# ============================================================
# EXTRACT ORDER VALUE
# ============================================================
def extract_total_order_value(text):
    patterns = [
        r"(₹|Rs\.?)\s?([\d,\.]+)\s?crore",
        r"([\d,\.]+)\s?crore",
        r"(₹|Rs\.?)\s?([\d,\.]+)\s?lakh"
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            val = float(m.group(len(m.groups())).replace(",", ""))
            if "lakh" in p.lower():
                return round(val / 100, 2)
            return round(val, 2)
    return None

# ============================================================
# EXTRACT COMPLETION DURATION
# ============================================================
def extract_total_duration(text):
    patterns = [
        r"within\s(\d+)\s(years?|months?)",
        r"over\s(\d+)\s(years?|months?)",
        r"period\s+of\s+(\d+)\s(years?|months?)",
        r"(\d+)\s(years?|months?)"
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return f"{m.group(1)} {m.group(2)}"
    return "Not Found"

# ============================================================
# FETCH FULL FINANCIAL DATA FROM SCREENER
# ============================================================
@st.cache_data(ttl=3600)
def fetch_financials_screener(symbol):
    data = {
        "Market Cap": None,
        "Current Price": None,
        "Stock P/E": None,
        "Industry P/E": None,
        "Book Value": None,
        "ROCE": None,
        "ROE": None,
        "Dividend Yield": None,
        "Promoter Holding": None
    }

    try:
        url = f"https://www.screener.in/company/{symbol}/consolidated/"
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        for li in soup.select("li"):
            text = li.text.strip()

            def num():
                span = li.find("span", class_="number")
                return span.text.strip() if span else None

            if text.startswith("Market Cap"):
                data["Market Cap"] = num()
            elif text.startswith("Current Price"):
                data["Current Price"] = num()
            elif text.startswith("Stock P/E"):
                data["Stock P/E"] = num()
            elif text.startswith("Industry P/E"):
                data["Industry P/E"] = num()
            elif text.startswith("Book Value"):
                data["Book Value"] = num()
            elif text.startswith("ROCE"):
                data["ROCE"] = num()
            elif text.startswith("ROE"):
                data["ROE"] = num()
            elif text.startswith("Dividend Yield"):
                data["Dividend Yield"] = num()
            elif text.startswith("Promoter Holding"):
                data["Promoter Holding"] = num()

        return data
    except:
        return data

# ============================================================
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(
    page_title="NSE Order Intelligence",
    layout="wide",
    page_icon="📦"
)

st.title("📦 NSE Big Order Intelligence")

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
# FETCH NSE ANNOUNCEMENTS
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
# DATE SELECTION
# ============================================================
c1, c2 = st.columns(2)
start_date = c1.date_input("📅 From Date", date.today() - timedelta(days=1))
end_date = c2.date_input("📅 To Date", date.today())

# ============================================================
# FETCH BUTTON
# ============================================================
if st.button("🚀 Fetch NSE Announcements"):
    st.cache_data.clear()
    st.session_state.orders_df = fetch_nse_orders_range(start_date, end_date)

# ============================================================
# MAIN DISPLAY
# ============================================================
if "orders_df" in st.session_state and st.session_state.orders_df is not None:

    orders = st.session_state.orders_df.copy()

    st.subheader("🔁 NSE Order Announcements")
    view = orders[["symbol", "sm_name", "desc", "Date", "attchmntFile"]].copy()
    view["Financials"] = view["symbol"].apply(screener_link)
    view["attchmntFile"] = view["attchmntFile"].apply(make_clickable)
    st.markdown(view.to_html(escape=False, index=False), unsafe_allow_html=True)

    # ========================================================
    # IMPACT ANALYSIS WITH FINANCIAL DATA
    # ========================================================
    results = []

    for _, r in orders.iterrows():
        pdf_text = read_nse_pdf_text(r.attchmntFile)
        order_val = extract_total_order_value(pdf_text)
        duration = extract_total_duration(pdf_text)

        fin = fetch_financials_screener(r.symbol)

        try:
            mcap = float(fin["Market Cap"].replace(",", ""))
        except:
            mcap = None

        order_pct = round((order_val / mcap) * 100, 2) if order_val and mcap else "NA"

        results.append({
            "Stock": r.symbol,
            "Company": r.sm_name,
            "Total Order Value ₹Cr": order_val if order_val else "Not Found",
            "Completion Duration": duration,
            "Market Cap ₹Cr": fin["Market Cap"],
            "Order % of Market Cap": order_pct,
            "Current Price": fin["Current Price"],
            "Stock P/E": fin["Stock P/E"],
            "Industry P/E": fin["Industry P/E"],
            "Book Value": fin["Book Value"],
            "ROCE %": fin["ROCE"],
            "ROE %": fin["ROE"],
            "Dividend Yield %": fin["Dividend Yield"],
            "Promoter Holding %": fin["Promoter Holding"],
            "Screener Link": screener_link(r.symbol)
        })

    df = pd.DataFrame(results)
    st.subheader("📊 Order Impact + Financial Strength")
    st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
