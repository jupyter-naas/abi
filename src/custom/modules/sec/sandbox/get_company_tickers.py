import requests
from src.utils.Storage import save_json

def get_company_tickers():
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    save_json(data, "datastore/sec", "company_tickers.json")

if __name__ == "__main__":
    get_company_tickers()