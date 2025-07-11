from pytickersymbols import PyTickerSymbols
from src.utils.Storage import save_json, get_json
import os

# https://pypi.org/project/pytickersymbols/
# Comment: List of all countries, industries, indices, and stocks are stored locally in github repo: https://github.com/portfolioplus/pytickersymbols

data_store_path = "datastore/yahoofinance/pytickersymbols"
indices_sub_path = "indices"
indices_file_name = "indices.json"
countries_sub_path = "countries"
countries_file_name = "countries.json"
industries_sub_path = "industries"
industries_file_name = "industries.json"
by_index_sub_path = "by_index"
stocks_file_name = "stocks.json"

stock_data = PyTickerSymbols()

# Get all countries
countries = stock_data.get_all_countries()
save_json(countries, os.path.join(data_store_path, countries_sub_path), countries_file_name)

# Get all industries
industries = stock_data.get_all_industries()
save_json(industries, os.path.join(data_store_path, industries_sub_path), industries_file_name)

# Get all indices
indices = stock_data.get_all_indices()
save_json(indices, os.path.join(data_store_path, indices_sub_path), indices_file_name)

total_stocks = 0
for index in indices:
    # Get all stocks by country
    dir_path = os.path.join(data_store_path, by_index_sub_path, index)
    index_file_name = f"{index}_{stocks_file_name}"
    stocks_by_index = get_json(dir_path, index_file_name)
    if len(stocks_by_index) == 0:
        stocks_by_index = list(stock_data.get_stocks_by_index(index)) # type: ignore
        save_json(stocks_by_index, dir_path, index_file_name)
    total_stocks += len(stocks_by_index)
    print(f"Stocks found for index {index}: {len(stocks_by_index)}")
print(f"Total stocks: {total_stocks}")