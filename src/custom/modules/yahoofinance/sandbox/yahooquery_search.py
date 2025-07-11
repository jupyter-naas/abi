from yahooquery import search # type: ignore
from pprint import pprint

def search_yahoo_ticker(company_name: str) -> list:
    """Search for Yahoo Finance ticker symbol from company name.
    
    Args:
        company_name (str): Name of the company to search for
        
    Returns:
        pd.DataFrame: DataFrame containing search results with columns:
            - symbol: Yahoo Finance ticker symbol
            - name: Full company name
            - exch: Exchange where stock is listed
            - type: Type of security
            - exchDisp: Display name of exchange
            - typeDisp: Display name of security type
    """
    try:
        # Search Yahoo Finance
        results = search(company_name)
        if len(results) > 0:
            return results.get("quotes")
        else:
            return []
        
    except Exception as e:
        print(f"Error searching for {company_name}: {str(e)}")
        return []
    
if __name__ == "__main__":
    results = search_yahoo_ticker("ACCOR")
    pprint(results)


