import xml.etree.ElementTree as ET

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="NIFTY / SENSEX Options Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 NIFTY / SENSEX Options Dashboard")
st.caption(
    "Educational decision-support dashboard. Market data may be delayed; "
    "this app does not guarantee profit or execute trades."
)


# ============================================================
# MARKET DATA
# ============================================================

@st.cache_data(ttl=30)
def get_index_quote(symbol):
    try:
        ticker = yf.Ticker(symbol)

        history = ticker.history(
            period="1d",
            interval="1m",
            auto_adjust=False,
        )

        if history.empty:
            history = ticker.history(
                period="5d",
                interval="1d",
                auto_adjust=False,
            )

        if history.empty:
            return None

        close = history["Close"].dropna()

        if close.empty:
            return None

        last = float(close.iloc[-1])
        previous = float(close.iloc[-2]) if len(close) > 1 else last

        change = last - previous
        change_pct = (change / previous * 100) if previous else 0

        return {
            "price": last,
            "change": change,
            "change_pct": change_pct,
            "time": str(history.index[-1]),
        }

    except Exception as error:
        return {
            "error": str(error)
        }


@st.cache_data(ttl=60)
def get_option_chain_yahoo(symbol):
    """
    Best-effort free option-chain lookup.

    Important:
    Yahoo Finance may not provide NSE/SENSEX index option chains.
    For real NSE option-chain data, connect an authorized broker/data API.
    """

    try:
        ticker = yf.Ticker(symbol)
        expiries = list(ticker.options)

        if not expiries:
            return None, []

        frames = []

        for expiry in expiries[:4]:
            try:
                option_chain = ticker.option_chain(expiry)

                calls = option_chain.calls.copy()
                puts = option_chain.puts.copy()

                calls["option_type"] = "CE"
                puts["option_type"] = "PE"

                calls["expiry"] = expiry
                puts["expiry"] = expiry

                frames.append(calls)
                frames.append(puts)

            except Exception:
                continue

        if not frames:
            return None, expiries

        return pd.concat(frames, ignore_index=True), expiries

    except Exception:
        return None, []


# ============================================================
# NEWS
# ============================================================

@st.cache_data(ttl=300)
def get_news():
    """
    Fetch Google News RSS without feedparser.

    This uses Python's built-in XML parser, so feedparser is NOT required.
    """

    feeds = [
        (
            "NIFTY / India Market",
            "https://news.google.com/rss/search?q=NIFTY+India+stock+market&hl=en-IN&gl=IN&ceid=IN:en",
        ),
        (
            "RBI / Economy",
            "https://news.google.com/rss/search?q=RBI+India+economy+markets&hl=en-IN&gl=IN&ceid=IN:en",
        ),
        (
            "Crude Oil",
            "https://news.google.com/rss/search?q=India+crude+oil+market&hl=en-IN&gl=IN&ceid=IN:en",
        ),
        (
            "US Markets / Fed",
            "https://news.google.com/rss/search?q=US+markets+Fed+India+NIFTY&hl=en-IN&gl=IN&ceid=IN:en",
        ),
    ]

    rows = []

    for source, url in feeds:
        try:
            response = requests.get(
                url,
                timeout=10,
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
            )

            response.raise_for_status()

            root = ET.fromstring(response.content)

            items = root.findall(".//item")

            for item in items[:8]:
                title = item.findtext("title", default="")
                link = item.findtext("link", default="")
                published = item.findtext("pubDate", default="")

                rows.append(
                    {
                        "source": source,
                        "title": title,
                        "link": link,
                        "published": published,
                    }
                )

        except Exception:
            continue

    if not rows:
        return pd.DataFrame(
            columns=["source", "title", "link", "published"]
        )

    return (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["title"])
        .reset_index(drop=True)
    )


def classify_news(title):
    text = str(title).lower()

    positive_words = [
        "rate cut",
        "growth",
        "gdp",
        "record high",
        "surge",
        "rally",
        "strong earnings",
        "inflow",
        "stimulus",
        "cooling inflation",
        "bullish",
        "upgrade",
    ]

    negative_words = [
        "rate hike",
        "war",
        "crisis",
        "recession",
        "inflation rises",
        "selloff",
        "slump",
        "fall",
        "surge in oil",
        "sanction",
        "downgrade",
        "bearish",
    ]

    positive_count = sum(
        word in text for word in positive_words
    )

    negative_count = sum(
        word in text for word in negative_words
    )

    if positive_count > negative_count:
        return "🟢 Potentially positive"

    if negative_count > positive_count:
        return "🔴 Potentially negative"

    return "🟡 Mixed / unclear"


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("⚙️ Settings")

index_name = st.sidebar.selectbox(
    "Select Index",
    ["NIFTY 50", "SENSEX"],
)

capital = st.sidebar.number_input(
    "Trading capital (₹)",
    min_value=100.0,
    value=1000.0,
    step=100.0,
)

st.sidebar.subheader("Lot Size")

nifty_lot = st.sidebar.number_input(
    "NIFTY lot size",
    min_value=1,
    value=65,
    step=1,
)

sensex_lot = st.sidebar.number_input(
    "SENSEX lot size",
    min_value=1,
    value=20,
    step=1,
)

lot = nifty_lot if index_name == "NIFTY 50" else sensex_lot

symbol = "^NSEI" if index_name == "NIFTY 50" else "^BSESN"

st.sidebar.info(
    "Free market-data providers can be delayed or unavailable. "
    "Always verify the actual option price and lot size in your broker."
)


# ============================================================
# 1. MARKET
# ============================================================

st.header("1️⃣ Live / Indicative Market")

quote = get_index_quote(symbol)

if quote and "error" not in quote:

    c1, c2, c3 = st.columns(3)

    c1.metric(
        index_name,
        f"{quote['price']:,.2f}",
    )

    c2.metric(
        "Change",
        f"{quote['change']:+,.2f}",
    )

    c3.metric(
        "Change %",
        f"{quote['change_pct']:+.2f}%",
    )

    st.caption(
        f"Last data timestamp returned by provider: {quote['time']}"
    )

else:
    st.warning(
        "Market quote is unavailable from the free data provider."
    )


# ============================================================
# 2. OPTION CHAIN
# ============================================================

st.header("2️⃣ Option Chain")

chain, expiries = get_option_chain_yahoo(symbol)

if chain is None:

    st.warning(
        "A usable NSE/SENSEX option chain was not returned by "
        "the free Yahoo Finance source."
    )

    st.info(
        "For genuine live CE/PE prices, OI, IV and expiry data, "
        "connect an authorized broker/data API."
    )

else:

    expiry = st.selectbox(
        "Select Expiry",
        expiries,
    )

    selected = chain[
        chain["expiry"] == expiry
    ].copy()

    if quote and "error" not in quote:

        spot = quote["price"]

        selected["distance"] = (
            selected["strike"] - spot
        ).abs()

        nearest = (
            selected
            .sort_values("distance")
            .head(30)
        )

    else:

        nearest = selected.head(30)

    display_columns = [
        "contractSymbol",
        "strike",
        "lastPrice",
        "bid",
        "ask",
        "volume",
        "openInterest",
        "impliedVolatility",
        "option_type",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in nearest.columns
    ]

    st.dataframe(
        nearest[available_columns],
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 3. TRADE CALCULATOR
# ============================================================

st.header("3️⃣ Buy → Target / Stop-Loss Calculator")

col1, col2, col3 = st.columns(3)

with col1:

    option_type = st.selectbox(
        "Option",
        ["CE (Call)", "PE (Put)"],
    )

    entry = st.number_input(
        "Buy price / premium (₹)",
        min_value=0.05,
        value=13.30,
        step=0.05,
    )

with col2:

    target = st.number_input(
        "Target sell price (₹)",
        min_value=0.05,
        value=15.00,
        step=0.05,
    )

    stop = st.number_input(
        "Stop-loss sell price (₹)",
        min_value=0.05,
        value=10.00,
        step=0.05,
    )

with col3:

    lots = st.number_input(
        "Number of lots",
        min_value=1,
        value=1,
        step=1,
    )

    charges = st.number_input(
        "Estimated charges (₹)",
        min_value=0.0,
        value=0.0,
        step=1.0,
    )

quantity = lot * lots

capital_required = entry * quantity

target_profit = (
    (target - entry) * quantity
    - charges
)

stop_loss_pnl = (
    (stop - entry) * quantity
    - charges
)

target_return = (
    (target - entry) / entry * 100
)

stop_return = (
    (stop - entry) / entry * 100
)

a, b, c, d = st.columns(4)

a.metric(
    "Quantity",
    f"{quantity}",
)

b.metric(
    "Capital Required",
    f"₹{capital_required:,.2f}",
)

c.metric(
    "Target P&L",
    f"₹{target_profit:,.2f}",
)

d.metric(
    "Stop P&L",
    f"₹{stop_loss_pnl:,.2f}",
)

st.write(
    f"**Example:** Buy {option_type} at "
    f"₹{entry:.2f} → target ₹{target:.2f}"
)

st.write(
    f"Target price movement: **{target_return:+.2f}%**"
)

st.write(
    f"Stop-loss price movement: **{stop_return:+.2f}%**"
)

if capital_required > capital:

    st.error(
        f"One position requires approximately "
        f"₹{capital_required:,.2f}, which is above your "
        f"₹{capital:,.2f} capital."
    )

else:

    st.success(
        f"Position fits within your configured "
        f"₹{capital:,.2f} capital before charges."
    )


# ============================================================
# 4. AUTO EXIT PLANNER
# ============================================================

st.header("4️⃣ Auto-Exit Planner")

st.write(
    "Use these levels when setting a target/stop-loss order "
    "in your broker."
)

exit_col1, exit_col2 = st.columns(2)

with exit_col1:

    st.subheader("🎯 Target")

    st.write(
        f"Buy: ₹{entry:.2f}"
    )

    st.write(
        f"Sell Target: ₹{target:.2f}"
    )

    st.write(
        f"Estimated P&L: ₹{target_profit:,.2f}"
    )

with exit_col2:

    st.subheader("🛑 Stop Loss")

    st.write(
        f"Buy: ₹{entry:.2f}"
    )

    st.write(
        f"Stop Sell: ₹{stop:.2f}"
    )

    st.write(
        f"Estimated P&L: ₹{stop_loss_pnl:,.2f}"
    )

st.info(
    "This app calculates the levels. It does not place orders. "
    "When using a broker's target/stop feature, execution can differ "
    "from the exact displayed price during fast markets."
)


# ============================================================
# 5. RISK CONTROL
# ============================================================

st.header("5️⃣ Risk Control")

risk_pct = st.slider(
    "Maximum planned loss as % of capital",
    min_value=1,
    max_value=100,
    value=20,
)

max_loss_budget = (
    capital * risk_pct / 100
)

actual_stop_risk = abs(
    min(stop_loss_pnl, 0)
)

r1, r2 = st.columns(2)

r1.metric(
    "Risk Budget",
    f"₹{max_loss_budget:,.2f}",
)

r2.metric(
    "Potential Stop Loss",
    f"₹{actual_stop_risk:,.2f}",
)

if actual_stop_risk > max_loss_budget:

    st.error(
        "The planned stop-loss risk is above your configured risk budget."
    )

else:

    st.success(
        "The planned stop-loss risk is within your configured risk budget."
    )


# ============================================================
# 6. NEWS
# ============================================================

st.header("6️⃣ Market News & Possible Impact")

news = get_news()

if news.empty:

    st.warning(
        "News feed is currently unavailable."
    )

else:

    news["impact"] = news["title"].apply(
        classify_news
    )

    for _, row in news.head(15).iterrows():

        st.markdown(
            f"### {row['impact']}\n"
            f"**{row['title']}**\n\n"
            f"{row['published']} · "
            f"[Read source]({row['link']})"
        )

st.caption(
    "News labels are keyword-based and are not market predictions. "
    "A headline can affect the market differently depending on context."
)


# ============================================================
# 7. PRE-MARKET CHECKLIST
# ============================================================

st.header("7️⃣ Before-Market Checklist")

checks = [
    "Check global markets (US / Asia).",
    "Check GIFT NIFTY / pre-open indication where available.",
    "Check RBI, Fed, inflation and GDP events.",
    "Check crude oil.",
    "Check USD/INR.",
    "Check India VIX.",
    "Check option-chain OI and change in OI.",
    "Check option volume and IV.",
    "Define entry before taking a position.",
    "Define target before taking a position.",
    "Define stop-loss before taking a position.",
    "Do not increase quantity just because premium is cheap.",
]

for number, item in enumerate(checks):

    st.checkbox(
        item,
        key=f"check_{number}",
    )


# ============================================================
# 8. PAPER TRADING
# ============================================================

st.header("8️⃣ Paper Trade")

st.write(
    "Use this section to practice the strategy without placing "
    "a real order."
)

paper_entry = st.number_input(
    "Paper Entry Price",
    min_value=0.05,
    value=float(entry),
    step=0.05,
    key="paper_entry",
)

paper_exit = st.number_input(
    "Paper Exit Price",
    min_value=0.05,
    value=float(target),
    step=0.05,
    key="paper_exit",
)

paper_pnl = (
    paper_exit - paper_entry
) * quantity

st.metric(
    "Paper Trade P&L",
    f"₹{paper_pnl:,.2f}",
)


# ============================================================
# FINAL WARNING
# ============================================================

st.warning(
    "Options can lose most or all of the premium quickly. "
    "This application is for education and calculation only. "
    "It does not guarantee profit, predict the market, or place "
    "real-money trades."
)
