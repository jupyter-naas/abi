from src import services

# Initialize workflow
ontology_store=services.ontology_store_service

# Query
symbol = "AAPL"
query = f"""
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?Symbol ?Company ?Earnings_Date ?EPS_Estimate ?Reported_EPS ?Surprise_Percentage
WHERE {{
  ?tickerEntity a abi:Ticker ;
    rdfs:label ?Symbol ;
    abi:isTickerSymbolOf ?company .
  
  ?company rdfs:label ?Company .
  
  FILTER(?Symbol = "{symbol}"@en)

  # Get earnings call and EPS data
  ?company abi:hostsEarningsCall ?call .
  ?call abi:hasEarningsPerShareData ?eps .
  ?call abi:occursAtTime ?timeRegion .
  ?timeRegion abi:alt_label ?Earnings_Date .
  # Get EPS details
  OPTIONAL {{
    ?eps abi:estimated_earnings_per_share ?EPS_Estimate ;
         abi:reported_earnings_per_share ?Reported_EPS ;
         abi:earnings_per_share_surprise_percentage ?Surprise_Percentage .
  }}
}}
ORDER BY DESC(?timeRegion)
"""

# Execute query
results = ontology_store.query(query)
data = []
for row in results:
    data_dict = {}
    for key in row.labels:
        data_dict[key] = str(row[key]) if row[key] else None
    data.append(data_dict)
import pandas as pd
print(pd.DataFrame(data))