
import os
import math
import time
import feedparser
import requests
import pandas as pd
import streamlit as st
import yfinance as yf
import feedparser

st.set_page_config(
    page_title="NIFTY / SENSEX Options Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 NIFTY / SENSEX Options Dashboard")
st.caption("Educational decision-support dashboard — not a guaranteed buy/sell signal.")

# -----------------------------
# Helpers
# -----------------------------
@st.cache_data(ttl=30)
def get_index_quote(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1d", interval="1m", auto_adjust=False)
        if hist.empty:
            hist = t.history(period="5d", interval="1d", auto_adjust=False)
        if hist.empty:
            return None
        last = float(hist["Close"].dropna().iloc[-1])
        prev = float(hist["Close"].dropna().iloc[-2]) if len(hist) > 1 else last
        return {
            "price": last,
            "change": last - prev,
            "change_pct": ((last - prev) / prev * 100) if prev else 0,
            "time": str(hist.index[-1]),
        }
    except Exception:
        return None


@st.cache_data(ttl=60)
def get_option_chain_yahoo(symbol):
    """Best-effort option chain through Yahoo Finance.
    This is NOT a guaranteed real-time NSE feed."""
    try:
        t = yf.Ticker(symbol)
        expiries = t.options
        if not expiries:
            return None, []
        frames = []
        for expiry in expiries[:4]:
            try:
                chain = t.option_chain(expiry)
                calls = chain.calls.copy()
                puts = chain.puts.copy()
                calls["option_type"] = "CE"
                puts["option_type"] = "PE"
                calls["expiry"] = expiry
                puts["expiry"] = expiry
                frames.extend([calls, puts])
            except Exception:
                pass
        if not frames:
            return None, expiries
        return pd.concat(frames, ignore_index=True), expiries
    except Exception:
        return None, []


def premium_cost(premium, lot):
    return float(premium) * int(lot)


def pnl_per_unit(entry, exit_price, side="LONG"):
    if side == "LONG":
        return exit_price - entry
    return entry - exit_price


def trade_summary(entry, target, stop, lot, charges=0):
    target_pnl = (target - entry) * lot - charges
    stop_pnl = (stop - entry) * lot - charges
    return target_pnl, stop_pnl


@st.cache_data(ttl=300)
def get_news():
    feeds = [
        ("Google News - NIFTY", "https://news.google.com/rss/search?q=NIFTY+India+market&hl=en-IN&gl=IN&ceid=IN:en"),
        ("Google News - RBI", "https://news.google.com/rss/search?q=RBI+India+economy+markets&hl=en-IN&gl=IN&ceid=IN:en"),
        ("Google News - crude oil", "https://news.google.com/rss/search?q=India+crude+oil+market&hl=en-IN&gl=IN&ceid=IN:en"),
        ("Google News - US markets", "https://news.google.com/rss/search?q=US+markets+Fed+India+NIFTY&hl=en-IN&gl=IN&ceid=IN:en"),
    ]
    rows = []
    for source, url in feeds:
        try:
            parsed = feedparser.parse(url)
            for item in parsed.entries[:8]:
                rows.append({
                    "source": source,
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "published": item.get("published", ""),
                })
        except Exception:
            pass
    return pd.DataFrame(rows).drop_duplicates(subset=["title"])


def classify_news(title):
    text = title.lower()
    positive = [
        "rate cut", "growth", "gdp", "record high", "surge", "rally",
        "strong earnings", "inflow", "stimulus", "cooling inflation",
        "bullish", "upgrade"
    ]
    negative = [
        "rate hike", "war", "crisis", "recession", "inflation rises",
        "selloff", "slump", "fall", "surge in oil", "sanction",
        "downgrade", "bearish"
    ]
    p = sum(x in text for x in positive)
    n = sum(x in text for x in negative)
    if p > n:
        return "Potentially positive"
    if n > p:
        return "Potentially negative"
    return "Mixed / unclear"


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.header("⚙️ Settings")

index_name = st.sidebar.selectbox("Index", ["NIFTY 50", "SENSEX"])
capital = st.sidebar.number_input("Trading capital (₹)", min_value=100.0, value=1000.0, step=100.0)

# Verify current lot size with your broker/exchange before trading.
nifty_lot = st.sidebar.number_input("NIFTY lot size", min_value=1, value=65, step=1)
sensex_lot = st.sidebar.number_input("SENSEX lot size", min_value=1, value=20, step=1)
lot = nifty_lot if index_name == "NIFTY 50" else sensex_lot

symbol = "^NSEI" if index_name == "NIFTY 50" else "^BSESN"

st.sidebar.info(
    "Prices from free market-data sources can be delayed or unavailable. "
    "For actual order execution, verify the price in your broker."
)

# -----------------------------
# Live Market
# -----------------------------
st.header("1️⃣ Live / Indicative Market")

quote = get_index_quote(symbol)

if quote:
    c1, c2, c3 = st.columns(3)
    c1.metric(index_name, f"{quote['price']:,.2f}")
    c2.metric("Change", f"{quote['change']:+,.2f}")
    c3.metric("Change %", f"{quote['change_pct']:+.2f}%")
    st.caption(f"Last data timestamp returned by provider: {quote['time']}")
else:
    st.warning("Market quote unavailable from the free data provider.")

# -----------------------------
# Option chain
# -----------------------------
st.header("2️⃣ Option Chain")

yahoo_symbol = "^NSEI" if index_name == "NIFTY 50" else "^BSESN"
chain, expiries = get_option_chain_yahoo(yahoo_symbol)

if chain is None:
    st.warning(
        "Free Yahoo Finance does not provide a usable option chain for this index right now. "
        "Use the broker/NSE adapter described in README.md for real option-chain data."
    )
else:
    expiry = st.selectbox("Expiry", expiries)
    selected = chain[chain["expiry"] == expiry].copy()

    if quote:
        spot = quote["price"]
        selected["distance"] = (selected["strike"] - spot).abs()
        nearest = selected.sort_values("distance").head(15)
        cols = [c for c in [
            "contractSymbol", "strike", "lastPrice", "bid", "ask",
            "volume", "openInterest", "impliedVolatility", "option_type"
        ] if c in nearest.columns]
        st.dataframe(nearest[cols], use_container_width=True, hide_index=True)
    else:
        st.dataframe(selected.head(30), use_container_width=True, hide_index=True)

# -----------------------------
# Trade calculator
# -----------------------------
st.header("3️⃣ Buy → Target / Stop-Loss Calculator")

col1, col2, col3 = st.columns(3)
with col1:
    option_type = st.selectbox("Option", ["CE (Call)", "PE (Put)"])
    entry = st.number_input("Buy price / premium (₹)", min_value=0.05, value=13.30, step=0.05)
with col2:
    target = st.number_input("Target sell price (₹)", min_value=0.05, value=15.00, step=0.05)
    stop = st.number_input("Stop-loss sell price (₹)", min_value=0.05, value=10.00, step=0.05)
with col3:
    qty = st.number_input("Lots", min_value=1, value=1, step=1)
    charges = st.number_input("Estimated total charges (₹)", min_value=0.0, value=0.0, step=1.0)

quantity = lot * qty
capital_required = entry * quantity
target_profit = (target - entry) * quantity - charges
stop_loss = (stop - entry) * quantity - charges
target_return = (target - entry) / entry * 100
stop_return = (stop - entry) / entry * 100

a, b, c, d = st.columns(4)
a.metric("Quantity", f"{quantity}")
b.metric("Capital required", f"₹{capital_required:,.2f}")
c.metric("Target P&L", f"₹{target_profit:,.2f}")
d.metric("Stop P&L", f"₹{stop_loss:,.2f}")

st.write(
    f"**Example:** Buy {option_type} at ₹{entry:.2f} → target ₹{target:.2f}. "
    f"Price move = **{target_return:+.2f}%** and gross P&L before charges = "
    f"**₹{(target-entry)*quantity:,.2f}**."
)

if capital_required > capital:
    st.error(f"One lot requires about ₹{capital_required:,.2f}, which is above your ₹{capital:,.2f} capital.")
else:
    st.success(f"One position fits within your configured capital of ₹{capital:,.2f} before charges.")

st.markdown(
    """
### Auto-exit logic

If your broker supports target/stop orders, the intended logic is:

- **BUY** at entry premium
- **SELL automatically** when premium reaches target
- **SELL automatically** when premium reaches stop-loss
- Only one exit should remain active after the other executes

This dashboard calculates the levels; it does **not** place trades.
"""
)

# -----------------------------
# Risk controls
# -----------------------------
st.header("4️⃣ Risk Controls")

risk_pct = st.slider("Maximum planned loss as % of capital", 1, 100, 20)
max_loss_budget = capital * risk_pct / 100

if stop_loss < 0:
    st.warning(
        f"Your calculated loss at stop is about ₹{abs(stop_loss):,.2f}. "
        f"Your configured loss budget is ₹{max_loss_budget:,.2f}."
    )
else:
    st.info("Your stop price is above/equal to the entry price, so this setup does not represent a normal long-option stop-loss.")

if abs(stop_loss) > max_loss_budget:
    st.error("Stop-loss risk is above your configured risk budget.")
else:
    st.success("Stop-loss risk is within your configured risk budget.")

# -----------------------------
# News
# -----------------------------
st.header("5️⃣ Market News & Possible Impact")

news = get_news()
if news.empty:
    st.warning("News feed unavailable.")
else:
    news["impact"] = news["title"].apply(classify_news)
    for _, row in news.head(15).iterrows():
        st.markdown(
            f"**{row['impact']}** — {row['title']}  \n"
            f"{row['published']} · [{row['source']}]({row['link']})"
        )

st.caption(
    "News impact labels are keyword-based and are not predictions. "
    "Read the source before acting. A headline can affect markets differently depending on context."
)

# -----------------------------
# Pre-market checklist
# -----------------------------
st.header("6️⃣ Before-Market Checklist")

checks = [
    "Check global markets (US/Asia) and overnight moves.",
    "Check GIFT NIFTY / pre-open indication where available.",
    "Check scheduled RBI, Fed, inflation, GDP and major-event calendar.",
    "Check crude oil, USD/INR and India VIX.",
    "Check NIFTY option-chain OI, change in OI, volume and IV.",
    "Define entry, target and stop-loss BEFORE entering.",
    "Do not increase quantity just because the premium is cheap.",
]

for item in checks:
    st.checkbox(item, key=item)

st.warning(
    "Options can lose most or all of the premium quickly. This app is an educational "
    "dashboard and does not guarantee profit or predict the market."
)
