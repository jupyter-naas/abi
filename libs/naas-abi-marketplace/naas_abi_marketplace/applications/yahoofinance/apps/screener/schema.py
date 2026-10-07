"""Screener UI schema: include fields, response columns, filters."""

from __future__ import annotations

from naas_abi_marketplace.applications.yahoofinance.integrations.YahooFinanceScreenerIntegration import (
    INCLUDE_FIELDS,
    INDUSTRIES,
    REGIONS,
    SECTORS,
)

SORT_FIELDS = [
    {"value": "intradaymarketcap", "label": "Market cap"},
    {"value": "ebitda.lasttwelvemonths", "label": "EBITDA (LTM)"},
    {"value": "totalrevenues.lasttwelvemonths", "label": "Revenue (LTM)"},
    {"value": "percentchange", "label": "Change %"},
    {"value": "avgdailyvol3m", "label": "Avg volume 3m"},
    {"value": "dayvolume", "label": "Day volume"},
    {"value": "peratio.lasttwelvemonths", "label": "P/E (LTM)"},
    {"value": "companyshortname.raw", "label": "Company name"},
    {"value": "intradayprice", "label": "Price"},
]

INCLUDE_FIELD_GROUPS = [
    {
        "id": "identity",
        "label": "Identity",
        "fields": [
            "ticker",
            "companyshortname",
            "region",
            "sector",
            "industry",
            "quotesCurrency",
            "financialCurrency",
            "is_morningstar_primary",
        ],
    },
    {
        "id": "price",
        "label": "Price & volume",
        "fields": [
            "intradayprice",
            "day_open_price",
            "intradaypricechange",
            "percentchange",
            "fiftytwowklow",
            "fiftytwowkhigh",
            "dayvolume",
            "avgdailyvol3m",
            "intradaymarketcap",
        ],
    },
    {
        "id": "fundamentals",
        "label": "Fundamentals",
        "fields": [
            "totalrevenues.lasttwelvemonths",
            "total_revenue_market_currency.annual",
            "ebitda.lasttwelvemonths",
            "grossprofit.lasttwelvemonths",
            "operatingincome.lasttwelvemonths",
            "cashfromoperations.lasttwelvemonths",
            "peratio.lasttwelvemonths",
            "fulltimeemployees.annual",
            "totaldebt.lasttwelvemonths",
            "totalassets.lasttwelvemonths",
            "totalcashandshortterminvestments.lasttwelvemonths",
            "totalcurrentassets.lasttwelvemonths",
            "totalequity.lasttwelvemonths",
            "totalcommonsharesoutstanding.lasttwelvemonths",
            "totalcurrentliabilities.lasttwelvemonths",
            "totalcommonequity.lasttwelvemonths",
            "cash_on_hand_quarterly_market_currency",
            "net_income_per_employee_annual_market_currency",
            "total_revenue_per_employee_annual_market_currency",
            "basicepscontinuingoperations.lasttwelvemonths",
        ],
    },
]

COLUMNS = [
    {"key": "ticker", "label": "Ticker", "type": "text", "sticky": True},
    {"key": "companyName", "label": "Company", "type": "text", "sticky": True},
    {"key": "primaryTicker", "label": "Primary ticker", "type": "text"},
    {"key": "listingCount", "label": "Listings", "type": "number"},
    {"key": "stockIds", "label": "Stock IDs", "type": "text"},
    {"key": "region", "label": "Region", "type": "text"},
    {"key": "sector", "label": "Sector", "type": "text"},
    {"key": "industry", "label": "Industry", "type": "text"},
    {"key": "quotesCurrency", "label": "Quote FX", "type": "text"},
    {"key": "financialCurrency", "label": "Financial FX", "type": "text"},
    {"key": "regularMarketPrice", "label": "Price", "type": "number"},
    {"key": "regularMarketOpen", "label": "Open", "type": "number"},
    {"key": "regularMarketChange", "label": "Change", "type": "number"},
    {"key": "regularMarketChangePercent", "label": "Change %", "type": "percent"},
    {"key": "fiftyTwoWeekLow", "label": "52w low", "type": "number"},
    {"key": "fiftyTwoWeekHigh", "label": "52w high", "type": "number"},
    {"key": "regularMarketVolume", "label": "Volume", "type": "number"},
    {"key": "avgDailyVol3m", "label": "Avg vol 3m", "type": "number"},
    {"key": "marketCap", "label": "Market cap", "type": "number"},
    {"key": "peRatioLtm", "label": "P/E LTM", "type": "number"},
    {"key": "totalRevenueLtm", "label": "Revenue LTM", "type": "number"},
    {
        "key": "totalRevenueAnnualMarketCurrency",
        "label": "Revenue annual (mkt FX)",
        "type": "number",
    },
    {"key": "ebitdaLtm", "label": "EBITDA LTM", "type": "number"},
    {
        "key": "ebitdaMargin",
        "label": "EBITDA margin",
        "type": "percent",
        "derived": True,
    },
    {"key": "grossProfitLtm", "label": "Gross profit LTM", "type": "number"},
    {"key": "operatingIncomeLtm", "label": "Operating income LTM", "type": "number"},
    {"key": "cashFromOperationsLtm", "label": "CFO LTM", "type": "number"},
    {"key": "fullTimeEmployees", "label": "Employees", "type": "number"},
    {"key": "basicEpsContinuingOperationsLtm", "label": "Basic EPS LTM", "type": "number"},
    {"key": "totalDebtLtm", "label": "Total debt LTM", "type": "number"},
    {"key": "totalAssetsLtm", "label": "Total assets LTM", "type": "number"},
    {
        "key": "totalCashAndShortTermInvestmentsLtm",
        "label": "Cash & ST investments",
        "type": "number",
    },
    {"key": "totalCurrentAssetsLtm", "label": "Current assets LTM", "type": "number"},
    {"key": "totalEquityLtm", "label": "Total equity LTM", "type": "number"},
    {
        "key": "totalCommonSharesOutstandingLtm",
        "label": "Shares outstanding",
        "type": "number",
    },
    {
        "key": "totalCurrentLiabilitiesLtm",
        "label": "Current liabilities LTM",
        "type": "number",
    },
    {"key": "totalCommonEquityLtm", "label": "Common equity LTM", "type": "number"},
    {
        "key": "cashOnHandQuarterlyMarketCurrency",
        "label": "Cash on hand (mkt FX)",
        "type": "number",
    },
    {
        "key": "netIncomePerEmployeeAnnualMarketCurrency",
        "label": "NI / employee",
        "type": "number",
    },
    {
        "key": "totalRevenuePerEmployeeAnnualMarketCurrency",
        "label": "Revenue / employee",
        "type": "number",
    },
]

DEFAULT_VISIBLE_COLUMNS = [
    "ticker",
    "companyName",
    "region",
    "quotesCurrency",
    "financialCurrency",
    "marketCap",
    "totalRevenueLtm",
    "ebitdaLtm",
    "ebitdaMargin",
    "operatingIncomeLtm",
    "fullTimeEmployees",
    "regularMarketPrice",
    "listingCount",
]

WATCHLISTS = [
    {
        "id": "ovh-peers",
        "label": "OVH peers",
        "tokens": [
            "OVH.PA",
            "OVH",
            "DOCN",
            "DigitalOcean",
            "RXT",
            "Rackspace",
            "CRWV",
            "CoreWeave",
            "688158.SS",
            "UCloud",
            "688316.SS",
            "QingCloud",
            "BLZE",
            "Backblaze",
            "GIGA.MC",
            "Gigas Hosting",
            "DHH.MI",
            "Dominion Hosting",
            "MSFT",
            "Microsoft Corporation",
            "ORCL",
            "NET",
            "Cloudflare",
            "AKAM",
            "Akamai",
            "GDDY",
            "GoDaddy",
            "NTNX",
            "Nutanix",
        ],
    }
]


def parse_company_list(text: str) -> list[str]:
    """Split a pasted ticker/name list on commas, semicolons, or newlines."""
    tokens: list[str] = []
    seen: set[str] = set()
    for part in text.replace(";", ",").replace("\n", ",").split(","):
        token = part.strip()
        key = token.lower()
        if not token or key in seen:
            continue
        seen.add(key)
        tokens.append(token)
    return tokens


def _ticker_values(row: dict) -> list[str]:
    values = [str(row.get("ticker") or ""), str(row.get("primaryTicker") or "")]
    stock_ids = row.get("stockIds")
    if isinstance(stock_ids, str):
        values.extend(stock_ids.split(","))
    elif isinstance(stock_ids, list):
        values.extend(str(item) for item in stock_ids if item)
    return [item.strip().lower() for item in values if item and str(item).strip()]


def row_matches_company_list(row: dict, tokens: list[str]) -> bool:
    """True when the row ticker or company name matches any watchlist token."""
    if not tokens:
        return True
    tickers = _ticker_values(row)
    name = str(row.get("companyName") or "").strip().lower()
    for token in tokens:
        needle = token.lower()
        if any(
            ticker == needle or ticker.startswith(f"{needle}.") for ticker in tickers
        ):
            return True
        if not name:
            continue
        if name == needle or name.startswith((f"{needle} ", f"{needle},")):
            return True
        if len(needle) >= 4 and name.startswith(needle):
            return True
    return False


DEFAULT_QUERY = {
    "size": 100,
    "offset": 0,
    "fetch_all": False,
    "save": False,
    "sector": "Technology",
    "industry": "Software—Infrastructure",
    "sort_type": "DESC",
    "sort_field": "intradaymarketcap",
    "min_revenue": 0,
    "include_fields": list(INCLUDE_FIELDS),
    "regions": list(REGIONS),
    "formatted": True,
    "use_records_response": True,
    "lang": "en-US",
    "query_region": "US",
    "require_positive": True,
}


def public_schema() -> dict:
    """Return the UI contract for the screener app."""
    return {
        "includeFields": INCLUDE_FIELDS,
        "includeFieldGroups": INCLUDE_FIELD_GROUPS,
        "regions": REGIONS,
        "sectors": SECTORS,
        "industries": INDUSTRIES,
        "sortFields": SORT_FIELDS,
        "columns": COLUMNS,
        "defaultVisibleColumns": DEFAULT_VISIBLE_COLUMNS,
        "defaults": DEFAULT_QUERY,
        "watchlists": WATCHLISTS,
    }
