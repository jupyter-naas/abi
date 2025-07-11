import src.custom.modules.yahoofinance.sandbox.yfinance_get_data as yf # type: ignore
from src.utils.Storage import save_json

# https://pypi.org/project/yfinance/ & https://ranaroussi.github.io/yfinance/

ticker_symbol = "ALV.DE"
ticker = yf.Ticker(ticker_symbol)

# Get ticker info
ticker_info = ticker.info
print("ticker_info", ticker_info)
save_json(ticker_info, f"datastore/yahoofinance/yfinance/{ticker_symbol}", f"{ticker_symbol}_info.json")

# Get ticker calendar
print("ticker_calendar", ticker.calendar)
save_json(ticker.calendar, f"datastore/yahoofinance/yfinance/{ticker_symbol}", f"{ticker_symbol}_calendar.json")

# Get ticker analyst price targets
print("ticker_analyst_price_targets", ticker.analyst_price_targets)
save_json(ticker.analyst_price_targets, f"datastore/yahoofinance/yfinance/{ticker_symbol}", f"{ticker_symbol}_analyst_price_targets.json")

# Get ticker quarterly income statement
print("ticker_quarterly_income_stmt", ticker.quarterly_income_stmt)
save_json(ticker.quarterly_income_stmt, f"datastore/yahoofinance/yfinance/{ticker_symbol}", f"{ticker_symbol}_quarterly_income_stmt.json")

# Get ticker history
print("ticker_history", ticker.history(period='1mo'))
save_json(ticker.history(period='1mo'), f"datastore/yahoofinance/yfinance/{ticker_symbol}", f"{ticker_symbol}_history.json")