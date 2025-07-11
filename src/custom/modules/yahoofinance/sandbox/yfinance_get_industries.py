import yfinance as yf # type: ignore
from src.utils.Storage import save_json
import pandas as pd

# https://pypi.org/project/yfinance/ & https://ranaroussi.github.io/yfinance/

industry_key = "insurance-diversified"
data_store_path = f"datastore/yahoofinance/yfinance/industries/{industry_key}"

industry = yf.Industry(industry_key)

# Get clean df
def result_df_to_dict(result):
    df = pd.DataFrame(result)
    # Create index from name column
    df.insert(0, 'key', df.index)
    df = df.fillna(0)
    for column in df.columns:
        df.rename(columns={column: column.strip().replace(" ", "_")}, inplace=True)
    return df.to_dict(orient="records")

# Get industry info
industry_sector_key = industry.sector_key
print("industry_sector_key", industry_sector_key)
save_json(industry_sector_key, data_store_path, f"{industry_key}_sector_key.json")

industry_sector_name = industry.sector_name
print("industry_sector_name", industry_sector_name)
save_json(industry_sector_name, data_store_path, f"{industry_key}_sector_name.json")

industry_top_performing_companies = result_df_to_dict(industry.top_performing_companies)
print("industry_top_performing_companies", industry_top_performing_companies)
save_json(industry_top_performing_companies, data_store_path, f"{industry_key}_top_performing_companies.json")

industry_top_growth_companies = result_df_to_dict(industry.top_growth_companies)
print("industry_top_growth_companies", industry_top_growth_companies)
save_json(industry_top_growth_companies, data_store_path, f"{industry_key}_top_growth_companies.json")

industry_info = {
    "sector_key": industry_sector_key,
    "sector_name": industry_sector_name,
    "top_performing_companies": industry_top_performing_companies,
    "top_growth_companies": industry_top_growth_companies,
}
print("industry_info", industry_info)
save_json(industry_info, data_store_path, f"{industry_key}_info.json")