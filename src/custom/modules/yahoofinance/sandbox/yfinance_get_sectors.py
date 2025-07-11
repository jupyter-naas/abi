import yfinance as yf # type: ignore
from src.utils.Storage import save_json
import pandas as pd

# https://pypi.org/project/yfinance/ & https://ranaroussi.github.io/yfinance/

sector_key = "financial-services"
data_store_path = f"datastore/yahoofinance/yfinance/sectors/{sector_key}"

sector = yf.Sector(sector_key)

# Get clean df
def result_df_to_dict(result):
    df = pd.DataFrame(result)
    # Create index from name column
    df.insert(0, 'key', df.index)
    df = df.fillna(0)
    for column in df.columns:
        df.rename(columns={column: column.strip().replace(" ", "_")}, inplace=True)
    return df.to_dict(orient="records")

# Get sector info
sector_key = sector.key
sector_name = sector.name
sector_symbol = sector.symbol

sector_ticker = sector.ticker.info
print("sector_ticker:", sector_ticker)
save_json(sector_ticker, data_store_path, f"{sector_key}_ticker.json")

sector_overview = sector.overview
print("sector_overview:", sector_overview)
save_json(sector_overview, data_store_path, f"{sector_key}_overview.json")

sector_top_companies = result_df_to_dict(sector.top_companies)
print("sector_top_companies:", sector_top_companies)
save_json(sector_top_companies, data_store_path, f"{sector_key}_top_companies.json")

sector_research_reports = sector.research_reports
print("sector_research_reports:", sector_research_reports)
save_json(sector_research_reports, data_store_path, f"{sector_key}_research_reports.json")

# Sector information
sector_top_etfs = sector.top_etfs
print("sector_top_etfs:", sector_top_etfs)
save_json(sector_top_etfs, data_store_path, f"{sector_key}_top_etfs.json")

sector_top_mutual_funds = sector.top_mutual_funds
print("sector_top_mutual_funds:", sector_top_mutual_funds)
save_json(sector_top_mutual_funds, data_store_path, f"{sector_key}_top_mutual_funds.json")
sector_industries = result_df_to_dict(sector.industries)
print("sector_industries:", sector_industries)
save_json(sector_industries, data_store_path, f"{sector_key}_industries.json")

sector_info = {
    "key": sector_key,
    "name": sector_name,
    "symbol": sector_symbol,
    "ticker": sector_ticker,
    "overview": sector_overview,
    "top_companies": sector_top_companies,
    "research_reports": sector_research_reports,
    "top_etfs": sector_top_etfs,
    "top_mutual_funds": sector_top_mutual_funds,
    "industries": sector_industries,
}
print("sector_info:", sector_info)
save_json(sector_info, data_store_path, f"{sector_key}_info.json")