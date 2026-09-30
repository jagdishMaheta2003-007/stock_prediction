# NIFTY / SENSEX Options Dashboard

## What this app does

- NIFTY 50 / SENSEX indicative quote
- Option-chain area
- CE / PE selection
- Buy-premium calculator
- Target sell-price calculator
- Stop-loss calculator
- Capital and lot-size check
- Risk-budget check
- Market-news feed
- Keyword-based "potential impact" classification
- Pre-market checklist

## Important data limitation

Free data providers can be delayed, incomplete, or block option-chain requests.
For real trading, verify all prices in your broker.

NSE provides paid real-time market-data feeds. A production version should connect
to an authorized broker/data-vendor API rather than scrape NSE pages.

## Broker integration architecture

Create a separate file such as `broker_adapter.py` with functions:

    get_spot(index)
    get_option_chain(index, expiry)
    place_buy_order(...)
    place_target_order(...)
    place_stop_order(...)
    get_order_status(...)

Then replace the demo/free-data functions in `app.py`.

Do NOT hard-code API keys. Use Streamlit secrets:

    st.secrets["BROKER_API_KEY"]
    st.secrets["BROKER_ACCESS_TOKEN"]

## Run

Windows PowerShell:

    py -m pip install -r requirements.txt
    py -m streamlit run app.py

Then open the local URL Streamlit prints.

## Suggested production tabs

1. Dashboard
2. NIFTY option chain
3. SENSEX option chain
4. Trade calculator
5. Paper trading
6. News & events
7. Trade journal
8. Risk monitor

## Paper trading first

Before connecting order execution, implement paper trading:
- virtual capital
- simulated entry
- target/SL
- P&L
- trade history
- daily loss limit

Only after testing should real order execution be connected.

## Disclaimer

This software is for educational/informational purposes. It does not provide
guaranteed signals, investment advice, or guaranteed execution.
