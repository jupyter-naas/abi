import yfinance as yf # type: ignore
from src.utils.Storage import save_json
import pandas as pd

# https://pypi.org/project/yfinance/ & https://ranaroussi.github.io/yfinance/

ticker_symbol = "MSFT"
data_store_path = f"datastore/yahoofinance/yfinance/tickers/{ticker_symbol}"

ticker = yf.Ticker(ticker_symbol)

# Get clean df
def result_df_to_dict(result):
    df = pd.DataFrame(result)
    print(df)
    # Convert index to string if it's a timestamp
    if isinstance(df.index, pd.DatetimeIndex):
        df.index = df.index.strftime('%Y-%m-%dT%H:%M:%S%z')
    # Create index from name column
    df.insert(0, 'key', df.index)
    df = df.fillna(0)
    for column in df.columns:
        if isinstance(column, pd.Timestamp):
            new_col = column.isoformat()
        else:
            new_col = str(column).strip().replace(" ", "_").lower()
        df.rename(columns={column: new_col}, inplace=True)
    return df.to_dict(orient="records")

def convert_list(values: list):
    data = []
    for v in values:
        if isinstance(v, pd.Timestamp):
            v = v.isoformat()
        elif hasattr(v, 'isoformat'):  # Handle other datetime-like objects
            v = v.isoformat()
        elif hasattr(v, 'strftime'):  # Handle date objects
            v = v.strftime('%Y-%m-%d')
        elif pd.isna(v):
            v = None
        data.append(v)
    return data

# Convert datetime to string in json serializable format
def convert_to_json(data_json: dict | list):
    """Convert DataFrame to dictionary and handle timestamp serialization."""
    if isinstance(data_json, dict):
        data_json = [data_json]
        
    for record in data_json:
        if isinstance(record, dict):
            for key, value in record.items():
                if pd.isna(value):  # Handle NaN values
                    record[key] = None
                elif isinstance(value, pd.Timestamp):  # Convert timestamps to ISO format
                    record[key] = value.isoformat()
                elif isinstance(value, list):  # Handle lists recursively
                    record[key] = convert_list(value)
                elif hasattr(value, 'isoformat'):  # Handle other datetime-like objects
                    record[key] = value.isoformat()
                elif hasattr(value, 'strftime'):  # Handle date objects
                    record[key] = value.strftime('%Y-%m-%d')
    return data_json

# Get ticker info
print("Getting ticker info")
ticker_info = ticker.info
save_json(ticker_info, data_store_path, f"{ticker_symbol}_info.json")

# Get ticker calendar
print("Getting ticker calendar")
ticker_calendar = convert_to_json(ticker.calendar)
save_json(ticker_calendar, data_store_path, f"{ticker_symbol}_calendar.json")

# Get ticker analyst price targets
print("Getting ticker analyst price targets")
ticker_analyst_price_targets = ticker.analyst_price_targets
save_json(ticker_analyst_price_targets, data_store_path, f"{ticker_symbol}_analyst_price_targets.json")

# Get ticker quarterly income statement
print("Getting ticker quarterly income statement")
ticker_quarterly_income_stmt = result_df_to_dict(ticker.quarterly_income_stmt)
save_json(ticker_quarterly_income_stmt, data_store_path, f"{ticker_symbol}_quarterly_income_stmt.json")

# Get ticker history
print("Getting ticker history")
ticker_history = result_df_to_dict(ticker.history(period='1mo'))
save_json(ticker_history, data_store_path, f"{ticker_symbol}_history.json")