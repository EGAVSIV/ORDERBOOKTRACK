# ==========================================================
# UPSTOX STREAMLIT OPTIONS ALGO – PAPER TRADING VERSION
# ==========================================================

import streamlit as st
import pandas as pd
import numpy as np
import requests
import gzip, json
from datetime import datetime
import hashlib

# ==========================================================
# CONFIG
# ==========================================================
UPSTOX_BASE = "https://api.upstox.com/v2"
TOKEN_FILE = "token.txt"

st.set_page_config("Upstox Options Algo Trader", layout="wide", page_icon="⚡")

# ==========================================================
# SESSION STATE
# ==========================================================
for k in ["trades", "pnl"]:
    if k not in st.session_state:
        st.session_state[k] = []

# ==========================================================
# TOKEN UTILS
# ==========================================================
def save_token(token):
    with open(TOKEN_FILE, "w") as f:
        f.write(token)

def load_token():
    try:
        return open(TOKEN_FILE).read().strip()
    except:
        return ""

def headers(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

# ==========================================================
# MASTER CONTRACT
# ==========================================================
@st.cache_data
def load_master():
    with gzip.open("complete.json.gz", "rt", encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)

master_df = load_master()

# ==========================================================
# INSTRUMENT HELPERS
# ==========================================================
def get_spot_key(symbol):
    if symbol in ["NIFTY","BANKNIFTY","FINNIFTY"]:
        return master_df[
            (master_df.segment=="NSE_INDEX") &
            (master_df.symbol.str.contains(symbol.replace("NIFTY","Nifty"), case=False))
        ].instrument_key.iloc[0]

    return master_df[
        (master_df.segment=="NSE_EQ") &
        (master_df.symbol==symbol)
    ].instrument_key.iloc[0]

def get_atm_option(symbol, spot_price, side):
    df = master_df[
        (master_df.segment=="NSE_FO") &
        (master_df.symbol==symbol) &
        (master_df.option_type==side)
    ].copy()

    df["diff"] = abs(df["strike"] - spot_price)
    return df.sort_values("diff").iloc[0]

# ==========================================================
# MARKET DATA
# ==========================================================
def fetch_candles(token, instrument_key, interval="1minute", count=100):
    url = f"{UPSTOX_BASE}/historical-candle/intraday/{instrument_key}/{interval}"
    r = requests.get(url, headers=headers(token))
    candles = r.json().get("data",{}).get("candles",[])
    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(candles, columns=["time","open","high","low","close","volume"])
    df["time"] = pd.to_datetime(df["time"])
    return df.tail(count)

# ==========================================================
# INDICATORS
# ==========================================================
def ema(s,p): return s.ewm(span=p,adjust=False).mean()

def bollinger(df):
    m = df.close.rolling(20).mean()
    s = df.close.rolling(20).std()
    df["bb_upper"] = m + 2*s
    df["bb_lower"] = m - 2*s
    return df

# ==========================================================
# ALGO ENGINE
# ==========================================================
def run_algo(token, symbol, htf_tf, ltf_tf):
    spot_key = get_spot_key(symbol)

    htf = fetch_candles(token, spot_key, htf_tf)
    ltf = fetch_candles(token, spot_key, ltf_tf)

    if htf.empty or ltf.empty or len(ltf)<50:
        return None

    htf["ema20"], htf["ema50"] = ema(htf.close,20), ema(htf.close,50)
    ltf["ema20"], ltf["ema50"] = ema(ltf.close,20), ema(ltf.close,50)
    ltf = bollinger(ltf)

    prev, curr = ltf.iloc[-2], ltf.iloc[-1]

    if htf.ema20.iloc[-1] > htf.ema50.iloc[-1]:
        if prev.close < prev.ema20 and curr.close > curr.ema20:
            return "CE"

    if htf.ema20.iloc[-1] < htf.ema50.iloc[-1]:
        if prev.close > prev.ema20 and curr.close < curr.ema20:
            return "PE"

    return None

# ==========================================================
# PAPER TRADING ENGINE
# ==========================================================
def paper_trade(symbol, option, entry):
    trade = {
        "Time": datetime.now(),
        "Symbol": symbol,
        "Option": option.trading_symbol,
        "Strike": option.strike,
        "Side": option.option_type,
        "Entry": entry,
        "LTP": entry,
        "PnL": 0
    }
    st.session_state.trades.append(trade)

# ==========================================================
# UI
# ==========================================================
st.title("⚡ Upstox Options Algo Trader (Paper Trading)")

token = st.text_input("🔑 Access Token", load_token(), type="password")

if st.button("💾 Save Token"):
    save_token(token)

symbols = st.multiselect(
    "Select Symbols",
    ["NIFTY","BANKNIFTY","FINNIFTY","RELIANCE","INFY","TCS"],
    ["NIFTY"]
)

htf_tf = st.selectbox("Trend TF", ["5minute","15minute"])
ltf_tf = st.selectbox("Entry TF", ["1minute","3minute"])

# ==========================================================
# RUN ONCE (STREAMLIT SAFE)
# ==========================================================
if st.button("🚀 Run Algo (Paper Trade)"):
    for sym in symbols:
        signal = run_algo(token, sym, htf_tf, ltf_tf)
        if signal:
            spot_key = get_spot_key(sym)
            spot = fetch_candles(token, spot_key, "1minute", 1).close.iloc[-1]
            atm = get_atm_option(sym, spot, signal)
            paper_trade(sym, atm, atm.last_price if "last_price" in atm else spot)
            st.success(f"{sym} BUY {signal} @ {atm.strike}")

# ==========================================================
# DASHBOARD
# ==========================================================
st.divider()
st.header("📊 Paper Trades & PnL")

if st.session_state.trades:
    df = pd.DataFrame(st.session_state.trades)
    st.dataframe(df, use_container_width=True)
    st.metric("Total Trades", len(df))
else:
    st.info("No trades yet")
