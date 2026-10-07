"""Yahoo Finance equity screener integration."""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from naas_abi_core.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.utils.Storage import find_storage_folder
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_marketplace.applications.yahoofinance import ABIModule

cache = CacheFactory.CacheFS_find_storage(subpath="yahoofinance")
SCREENER_SUBPATH = "screener"
YAHOOFINANCE_APP_DIR = Path(__file__).resolve().parent.parent
SCREENER_CACHE_TTL = timedelta(days=7)

SCREENER_URL = "https://query1.finance.yahoo.com/v1/finance/screener"
CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
COOKIE_URL = "https://fc.yahoo.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
)
INCLUDE_FIELDS = [
    "ticker",
    "companyshortname",
    "intradaypricechange",
    "percentchange",
    "dayvolume",
    "avgdailyvol3m",
    "intradaymarketcap",
    "peratio.lasttwelvemonths",
    "day_open_price",
    "intradayprice",
    "fiftytwowklow",
    "fiftytwowkhigh",
    "region",
    "is_morningstar_primary",
    "sector",
    "industry",
    "quotesCurrency",
    "financialCurrency",
    "totalrevenues.lasttwelvemonths",
    "total_revenue_market_currency.annual",
    "ebitda.lasttwelvemonths",
    "grossprofit.lasttwelvemonths",
    "operatingincome.lasttwelvemonths",
    "cashfromoperations.lasttwelvemonths",
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
]

# Yahoo's screener UI adds these as `gt 0` query operands when the columns are
# selected. includeFields alone does not always populate them on the record.
REQUIRE_POSITIVE_FIELDS = [
    "totalrevenues.lasttwelvemonths",
    "total_revenue_market_currency.annual",
    "ebitda.lasttwelvemonths",
    "grossprofit.lasttwelvemonths",
    "operatingincome.lasttwelvemonths",
    "cashfromoperations.lasttwelvemonths",
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
]

# These are the regions, sectors, and industries selected in the browser-exported
# request. Every available Yahoo value is included, so the groups do not narrow
# the universe; they are stored so the payload matches the UI.
REGIONS = [
    "us",
    "ar",
    "at",
    "au",
    "be",
    "br",
    "ca",
    "ch",
    "cl",
    "cn",
    "cz",
    "de",
    "dk",
    "ee",
    "eg",
    "es",
    "fi",
    "fr",
    "gb",
    "gr",
    "hk",
    "hu",
    "id",
    "ie",
    "il",
    "in",
    "is",
    "it",
    "jp",
    "kr",
    "kw",
    "lk",
    "lt",
    "lv",
    "mx",
    "my",
    "nl",
    "no",
    "nz",
    "pe",
    "ph",
    "pk",
    "pl",
    "pt",
    "qa",
    "ru",
    "sa",
    "se",
    "sg",
    "za",
    "sr",
    "th",
    "tr",
    "tw",
    "ve",
    "vn",
]

SECTORS = [
    "Technology",
    "Basic Materials",
    "Consumer Cyclical",
    "Financial Services",
    "Real Estate",
    "Consumer Defensive",
    "Healthcare",
    "Utilities",
    "Communication Services",
    "Energy",
    "Industrials",
]

INDUSTRIES = [
    "Software—Infrastructure",
    "Information Technology Services",
    "Software—Application",
    "Communication Equipment",
    "Computer Hardware",
    "Consumer Electronics",
    "Electronic Components",
    "Electronics & Computer Distribution",
    "Scientific & Technical Instruments",
    "Semiconductor Equipment & Materials",
    "Semiconductors",
    "Solar",
    "Agricultural Inputs",
    "Building Materials",
    "Chemicals",
    "Specialty Chemicals",
    "Lumber & Wood Production",
    "Paper & Paper Products",
    "Aluminum",
    "Copper",
    "Other Industrial Metals & Mining",
    "Gold",
    "Silver",
    "Other Precious Metals & Mining",
    "Coking Coal",
    "Steel",
    "Auto & Truck Dealerships",
    "Auto Manufacturers",
    "Auto Parts",
    "Recreational Vehicles",
    "Furnishings, Fixtures & Appliances",
    "Residential Construction",
    "Textile Manufacturing",
    "Apparel Manufacturing",
    "Footwear & Accessories",
    "Packaging & Containers",
    "Personal Services",
    "Restaurants",
    "Apparel Retail",
    "Department Stores",
    "Home Improvement Retail",
    "Luxury Goods",
    "Internet Retail",
    "Specialty Retail",
    "Gambling",
    "Leisure",
    "Lodging",
    "Resorts & Casinos",
    "Travel Services",
    "Asset Management",
    "Banks—Diversified",
    "Banks—Regional",
    "Mortgage Finance",
    "Capital Markets",
    "Financial Data & Stock Exchanges",
    "Insurance—Life",
    "Insurance—Property & Casualty",
    "Insurance—Reinsurance",
    "Insurance—Specialty",
    "Insurance Brokers",
    "Insurance—Diversified",
    "Shell Companies",
    "Financial Conglomerates",
    "Credit Services",
    "Real Estate—Development",
    "Real Estate Services",
    "Real Estate—Diversified",
    "REIT—Healthcare Facilities",
    "REIT—Hotel & Motel",
    "REIT—Industrial",
    "REIT—Office",
    "REIT—Residential",
    "REIT—Retail",
    "REIT—Mortgage",
    "REIT—Specialty",
    "REIT—Diversified",
    "Beverages—Brewers",
    "Beverages—Wineries & Distilleries",
    "Beverages—Non-Alcoholic",
    "Confectioners",
    "Farm Products",
    "Household & Personal Products",
    "Packaged Foods",
    "Education & Training Services",
    "Discount Stores",
    "Food Distribution",
    "Grocery Stores",
    "Tobacco",
    "Biotechnology",
    "Drug Manufacturers—General",
    "Drug Manufacturers—Specialty & Generic",
    "Healthcare Plans",
    "Medical Care Facilities",
    "Pharmaceutical Retailers",
    "Health Information Services",
    "Medical Devices",
    "Medical Instruments & Supplies",
    "Diagnostics & Research",
    "Medical Distribution",
    "Utilities—Independent Power Producers",
    "Utilities—Renewable",
    "Utilities—Regulated Water",
    "Utilities—Regulated Electric",
    "Utilities—Regulated Gas",
    "Utilities—Diversified",
    "Telecom Services",
    "Advertising Agencies",
    "Publishing",
    "Broadcasting",
    "Entertainment",
    "Internet Content & Information",
    "Electronic Gaming & Multimedia",
    "Oil & Gas Drilling",
    "Oil & Gas E&P",
    "Oil & Gas Integrated",
    "Oil & Gas Midstream",
    "Oil & Gas Refining & Marketing",
    "Oil & Gas Equipment & Services",
    "Thermal Coal",
    "Uranium",
    "Aerospace & Defense",
    "Specialty Business Services",
    "Consulting Services",
    "Rental & Leasing Services",
    "Security & Protection Services",
    "Staffing & Employment Services",
    "Conglomerates",
    "Engineering & Construction",
    "Infrastructure Operations",
    "Building Products & Equipment",
    "Farm & Heavy Construction Machinery",
    "Industrial Distribution",
    "Business Equipment & Supplies",
    "Specialty Industrial Machinery",
    "Metal Fabrication",
    "Pollution & Treatment Controls",
    "Tools & Accessories",
    "Electrical Equipment & Parts",
    "Airports & Air Services",
    "Airlines",
    "Railroads",
    "Marine Shipping",
    "Trucking",
    "Integrated Freight & Logistics",
    "Waste Management",
]


def _eq_values(value: str | list[str] | None, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        return [value]
    values = [item for item in value if item]
    if not values:
        raise ValueError("At least one value is required")
    return values


def _or_eq(field: str, values: list[str]) -> dict[str, Any]:
    return {
        "operator": "or",
        "operands": [
            {"operator": "eq", "operands": [field, item]} for item in values
        ],
    }


def taxonomy() -> dict[str, list[str]]:
    """Return the stored Yahoo screener region, sector, and industry values."""
    return {
        "regions": list(REGIONS),
        "sectors": list(SECTORS),
        "industries": list(INDUSTRIES),
    }


def _join_output(output_dir: str, *parts: str) -> str:
    path = Path(output_dir)
    for part in parts:
        path /= part
    return path.as_posix()


def local_screener_root(datastore_path: str = "yahoofinance") -> Path:
    storage_root = find_storage_folder(str(YAHOOFINANCE_APP_DIR), "storage")
    return Path(storage_root) / "datastore" / datastore_path / SCREENER_SUBPATH


def _screener_cache_key(**params: Any) -> str:
    payload = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:32]
    return f"screener_page_{digest}"


@dataclass
class YahooFinanceScreenerIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for the Yahoo Finance screener integration."""

    datastore_path: str = field(
        default_factory=lambda: ABIModule.get_instance().configuration.datastore_path
    )


class YahooFinanceScreenerIntegration(Integration):
    """Fetch and persist Yahoo Finance equity screener exports."""

    __configuration: YahooFinanceScreenerIntegrationConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: YahooFinanceScreenerIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(
            ABIModule.get_instance().engine.services.object_storage
        )

    def screener_prefix(self, *relative: str) -> str:
        parts = [self.__configuration.datastore_path, SCREENER_SUBPATH, *relative]
        return "/".join(part for part in parts if part)

    def save_json_at(
        self, relative_path: str, payload: dict[str, Any] | list[Any]
    ) -> None:
        relative = Path(relative_path)
        parent_parts = [part for part in relative.parent.parts if part not in {".", ""}]
        prefix = (
            self.screener_prefix(*parent_parts)
            if parent_parts
            else self.screener_prefix()
        )
        filename = relative.name
        self.__storage_utils.save_json(payload, prefix, filename, copy=False)

    @cache(
        lambda self, size, offset, sector, industry, sort_type, sort_field, min_revenue, include_fields, regions, cookie, crumb, formatted, use_records_response, lang, query_region, require_positive: _screener_cache_key(
            size=size,
            offset=offset,
            sector=sector,
            industry=industry,
            sort_type=sort_type,
            sort_field=sort_field,
            min_revenue=min_revenue,
            include_fields=include_fields,
            regions=regions,
            cookie=bool(cookie),
            crumb=bool(crumb),
            formatted=formatted,
            use_records_response=use_records_response,
            lang=lang,
            query_region=query_region,
            require_positive=require_positive,
        ),
        cache_type=DataType.JSON,
        ttl=SCREENER_CACHE_TTL,
    )
    def fetch_screener_page(
        self,
        size: int,
        offset: int,
        sector: str | list[str] | None = None,
        industry: str | list[str] | None = None,
        sort_type: str = "DESC",
        sort_field: str = "intradaymarketcap",
        min_revenue: float | None = None,
        include_fields: list[str] | None = None,
        regions: list[str] | None = None,
        cookie: str | None = None,
        crumb: str | None = None,
        formatted: bool = True,
        use_records_response: bool = True,
        lang: str = "en-US",
        query_region: str = "US",
        require_positive: bool = True,
    ) -> dict[str, Any]:
        try:
            return _fetch_screener_uncached(
                size,
                offset,
                sector,
                industry,
                sort_type,
                sort_field,
                min_revenue,
                include_fields,
                regions,
                cookie,
                crumb,
                formatted,
                use_records_response,
                lang,
                query_region,
                require_positive,
            )
        except RuntimeError as exc:
            raise IntegrationConnectionError(str(exc)) from exc

    def run_export(self, args: argparse.Namespace) -> None:
        main(args)


_default_integration: YahooFinanceScreenerIntegration | None = None


def get_screener_integration() -> YahooFinanceScreenerIntegration:
    global _default_integration
    if _default_integration is None:
        _default_integration = YahooFinanceScreenerIntegration(
            YahooFinanceScreenerIntegrationConfiguration()
        )
    return _default_integration


def write_taxonomy(path: Path | None = None) -> str:
    """Write region, sector, and industry values to screener/_metadata/taxonomy.json."""
    _ = path
    relative = "_metadata/taxonomy.json"
    get_screener_integration().save_json_at(relative, taxonomy())
    return relative


def build_payload(
    size: int,
    offset: int,
    sector: str | list[str] | None = None,
    industry: str | list[str] | None = None,
    sort_type: str = "DESC",
    sort_field: str = "intradaymarketcap",
    min_revenue: float | None = None,
    include_fields: list[str] | None = None,
    regions: list[str] | None = None,
    require_positive: bool = True,
) -> dict[str, Any]:
    """Build the global equity screener request body."""
    region_list = list(regions) if regions else list(REGIONS)
    if not region_list:
        raise ValueError("At least one region is required")
    fields = list(include_fields) if include_fields else list(INCLUDE_FIELDS)
    if not fields:
        raise ValueError("At least one include field is required")
    operands: list[dict[str, Any]] = [_or_eq("region", region_list)]
    operands.append(_or_eq("sector", _eq_values(sector, SECTORS)))
    operands.append(_or_eq("industry", _eq_values(industry, INDUSTRIES)))
    if require_positive:
        for field in REQUIRE_POSITIVE_FIELDS:
            operands.append(
                {
                    "operator": "or",
                    "operands": [
                        {"operator": "gt", "operands": [field, 0]},
                    ],
                }
            )
    if min_revenue is not None and not (
        require_positive
        and min_revenue == 0
        and "totalrevenues.lasttwelvemonths" in REQUIRE_POSITIVE_FIELDS
    ):
        operands.append(
            {
                "operator": "or",
                "operands": [
                    {
                        "operator": "gt",
                        "operands": [
                            "totalrevenues.lasttwelvemonths",
                            min_revenue,
                        ],
                    },
                ],
            }
        )

    return {
        "size": size,
        "offset": offset,
        "sortType": sort_type.upper(),
        "sortField": sort_field,
        "includeFields": fields,
        "topOperator": "AND",
        "query": {
            "operator": "and",
            "operands": operands,
        },
        "quoteType": "EQUITY",
    }


def create_opener() -> urllib.request.OpenerDirector:
    """Create an HTTP opener that retains Yahoo session cookies."""
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )


def get_crumb(
    opener: urllib.request.OpenerDirector, crumb: str | None = None
) -> str:
    """Return an environment-provided crumb or obtain one from Yahoo."""
    crumb = (crumb or os.getenv("YAHOO_FINANCE_CRUMB") or "").strip()
    if crumb:
        return crumb

    # Yahoo's cookie bootstrap endpoint normally responds with 404 after setting
    # the A3 session cookie. The cookie is retained by the opener.
    cookie_request = urllib.request.Request(
        COOKIE_URL,
        headers={"Accept": "*/*", "User-Agent": USER_AGENT},
    )
    try:
        with opener.open(cookie_request, timeout=30):
            pass
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Yahoo Finance cookie request failed ({exc.code}): {details}"
            ) from exc

    request = urllib.request.Request(
        CRUMB_URL,
        headers={"Accept": "*/*", "User-Agent": USER_AGENT},
    )
    try:
        with opener.open(request, timeout=30) as response:
            crumb = response.read().decode("utf-8").strip()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Yahoo Finance crumb request failed ({exc.code}): {details}"
        ) from exc

    if not crumb or crumb.startswith("{"):
        raise RuntimeError("Yahoo Finance returned an invalid crumb")
    return crumb


def fetch_screener(
    size: int,
    offset: int,
    sector: str | list[str] | None = None,
    industry: str | list[str] | None = None,
    sort_type: str = "DESC",
    sort_field: str = "intradaymarketcap",
    min_revenue: float | None = None,
    include_fields: list[str] | None = None,
    regions: list[str] | None = None,
    cookie: str | None = None,
    crumb: str | None = None,
    formatted: bool = True,
    use_records_response: bool = True,
    lang: str = "en-US",
    query_region: str = "US",
    require_positive: bool = True,
) -> dict[str, Any]:
    """Fetch one page of Yahoo Finance screener records."""
    return get_screener_integration().fetch_screener_page(
        size,
        offset,
        sector,
        industry,
        sort_type,
        sort_field,
        min_revenue,
        include_fields,
        regions,
        cookie,
        crumb,
        formatted,
        use_records_response,
        lang,
        query_region,
        require_positive,
    )


def _fetch_screener_uncached(
    size: int,
    offset: int,
    sector: str | list[str] | None = None,
    industry: str | list[str] | None = None,
    sort_type: str = "DESC",
    sort_field: str = "intradaymarketcap",
    min_revenue: float | None = None,
    include_fields: list[str] | None = None,
    regions: list[str] | None = None,
    cookie: str | None = None,
    crumb: str | None = None,
    formatted: bool = True,
    use_records_response: bool = True,
    lang: str = "en-US",
    query_region: str = "US",
    require_positive: bool = True,
) -> dict[str, Any]:
    """Perform the live Yahoo Finance screener HTTP request."""
    cookie = (cookie or os.getenv("YAHOO_FINANCE_COOKIE") or "").strip() or None
    # urllib's cookie processor replaces a Cookie header with the jar. When a
    # browser session is supplied, send that header on a plain opener.
    opener = urllib.request.build_opener() if cookie else create_opener()
    crumb = get_crumb(opener, crumb)
    query = urllib.parse.urlencode(
        {
            "formatted": "true" if formatted else "false",
            "useRecordsResponse": "true" if use_records_response else "false",
            "lang": lang,
            "region": query_region,
            "crumb": crumb,
        }
    )
    headers = {
        "Accept": "*/*",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json",
        "Origin": "https://finance.yahoo.com",
        "Referer": "https://finance.yahoo.com/research-hub/screener/",
        "User-Agent": USER_AGENT,
        "X-Crumb": crumb,
    }
    if cookie:
        headers["Cookie"] = cookie

    payload = build_payload(
        size,
        offset,
        sector,
        industry,
        sort_type,
        sort_field,
        min_revenue,
        include_fields,
        regions,
        require_positive,
    )
    if cookie:
        result = _fetch_screener_curl(payload, crumb, cookie, query)
    else:
        request = urllib.request.Request(
            f"{SCREENER_URL}?{query}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with opener.open(request, timeout=60) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Yahoo Finance screener request failed ({exc.code}): {details}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Yahoo Finance returned a non-JSON response") from exc

    finance = result.get("finance")
    if not isinstance(finance, dict):
        raise RuntimeError("Yahoo Finance response is missing the finance object")
    if finance.get("error"):
        raise RuntimeError(f"Yahoo Finance API error: {finance['error']}")
    if not isinstance(finance.get("result"), list):
        raise RuntimeError("Yahoo Finance response is missing finance.result")
    return result


def _fetch_screener_curl(
    payload: dict[str, Any],
    crumb: str,
    cookie: str,
    query: str | None = None,
) -> dict[str, Any]:
    """POST the screener request with curl so browser cookies are sent intact."""
    if query is None:
        query = urllib.parse.urlencode(
            {
                "formatted": "true",
                "useRecordsResponse": "true",
                "lang": "en-US",
                "region": "US",
                "crumb": crumb,
            }
        )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as payload_file:
        json.dump(payload, payload_file, ensure_ascii=False)
        payload_path = payload_file.name
    try:
        completed = subprocess.run(
            [
                "curl",
                "-sS",
                "--compressed",
                "--url",
                f"{SCREENER_URL}?{query}",
                "-H",
                "accept: */*",
                "-H",
                "accept-language: fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "-H",
                "content-type: application/json",
                "-H",
                f"cookie: {cookie}",
                "-H",
                "origin: https://finance.yahoo.com",
                "-H",
                "referer: https://finance.yahoo.com/research-hub/screener/",
                "-H",
                f"user-agent: {USER_AGENT}",
                "-H",
                f"x-crumb: {crumb}",
                "--data-binary",
                f"@{payload_path}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        Path(payload_path).unlink(missing_ok=True)

    if completed.returncode != 0:
        raise RuntimeError(
            f"Yahoo Finance curl request failed: {completed.stderr.strip()}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Yahoo Finance returned a non-JSON response") from exc


def output_dir_for(
    sector: str | list[str] | None, industry: str | list[str] | None
) -> str:
    sector_dir = sector if isinstance(sector, str) and sector else "all"
    if Path(sector_dir).name != sector_dir:
        raise ValueError("--sector must not contain path separators")
    if Path(sector_dir).name != sector_dir:
        raise ValueError("--sector must not contain path separators")
    parts = [sector_dir]
    if isinstance(industry, str) and industry:
        if Path(industry).name != industry:
            raise ValueError("--industry must not contain path separators")
        parts.append(industry)
    return "/".join(parts)


def save_json(result: dict[str, Any], output: str) -> None:
    """Save the complete Yahoo Finance response under screener/."""
    get_screener_integration().save_json_at(output, result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Yahoo Finance equity screener results to JSON."
    )
    parser.add_argument("--size", type=int, default=25, help="Records per page")
    parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    parser.add_argument("--sector", help="Exact Yahoo Finance sector name")
    parser.add_argument("--industry", help="Exact Yahoo Finance industry name")
    parser.add_argument(
        "--sort-type",
        choices=("asc", "desc", "ASC", "DESC"),
        default="DESC",
        help="Sort direction",
    )
    parser.add_argument(
        "--sort-field",
        default="intradaymarketcap",
        help="Yahoo Finance field used for sorting",
    )
    parser.add_argument(
        "--min-revenue",
        type=float,
        help="Require trailing-twelve-month revenue greater than this value",
    )
    parser.add_argument(
        "--require-positive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Add gt 0 query operands for the selected financial columns",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path (default: data/<sector>/<offset>_<size>_screener.json)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch every page until Yahoo's reported total is reached",
    )
    parser.add_argument(
        "--timestamp-dir",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When using --all, write into a UTC timestamp subfolder",
    )
    parser.add_argument(
        "--by-sector",
        action="store_true",
        help="Fetch each sector separately so Yahoo's 10k offset cap is not hit",
    )
    parser.add_argument(
        "--by-industry",
        action="store_true",
        help="Fetch each industry into screener/<sector>/<industry>/<timestamp>/",
    )
    parser.add_argument(
        "--list-taxonomy",
        choices=("regions", "sectors", "industries", "all"),
        help="Print Yahoo screener regions, sectors, or industries and exit",
    )
    args = parser.parse_args()
    if args.size < 1 or args.size > 250:
        parser.error("--size must be between 1 and 250")
    if args.offset < 0:
        parser.error("--offset must be zero or greater")
    if args.all and args.output is not None:
        parser.error("--output cannot be combined with --all")
    if args.by_sector and not args.all:
        parser.error("--by-sector requires --all")
    if args.by_sector and args.sector:
        parser.error("--by-sector cannot be combined with --sector")
    if args.by_industry and not args.all:
        parser.error("--by-industry requires --all")
    if args.by_industry and (args.sector or args.industry):
        parser.error("--by-industry cannot be combined with --sector or --industry")
    if args.by_industry and args.by_sector:
        parser.error("--by-industry cannot be combined with --by-sector")
    return args


def _page(result: dict[str, Any]) -> dict[str, Any]:
    pages = result.get("finance", {}).get("result") or []
    return pages[0] if pages else {}


def fetch_all_pages(
    size: int,
    offset: int = 0,
    sector: str | list[str] | None = None,
    industry: str | list[str] | None = None,
    sort_type: str = "DESC",
    sort_field: str = "intradaymarketcap",
    min_revenue: float | None = None,
    include_fields: list[str] | None = None,
    regions: list[str] | None = None,
    cookie: str | None = None,
    crumb: str | None = None,
    formatted: bool = True,
    use_records_response: bool = True,
    lang: str = "en-US",
    query_region: str = "US",
    require_positive: bool = True,
    combined_output_dir: str | None = None,
    page_log_dir: str | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Download every screener page and optionally write a combined JSON file.

    Per-page responses are written under ``page_log_dir`` (typically a UTC run
    folder). ``all_screener.json`` is written at ``combined_output_dir`` (sector
    or industry root). ``output_dir`` is kept as an alias for ``combined_output_dir``.
    """
    combined_root = combined_output_dir or output_dir
    pages_root = page_log_dir if page_log_dir is not None else combined_root
    current = offset
    records: list[dict[str, Any]] = []
    total = None
    last_page: dict[str, Any] = {}
    while True:
        result = fetch_screener(
            size,
            current,
            sector,
            industry,
            sort_type,
            sort_field,
            min_revenue,
            include_fields,
            regions,
            cookie,
            crumb,
            formatted,
            use_records_response,
            lang,
            query_region,
            require_positive,
        )
        page = _page(result)
        last_page = page
        page_records = page.get("records") or []
        total = page.get("total", 0)
        returned_start = page.get("start", current)
        if returned_start != current:
            print(
                f"Yahoo clamped pagination at start {returned_start} "
                f"(requested offset {current}, total {total})"
            )
            break
        if pages_root is not None:
            page_path = _join_output(pages_root, f"{current}_{size}_screener.json")
            save_json(result, page_path)
            print(
                f"Saved {page.get('count', 0)} records "
                f"(offset {page.get('start', current)}, total {total}) "
                f"to {page_path}"
            )
        records.extend(page_records)
        if not page_records or current + size >= total:
            break
        current += size
        time.sleep(0.4)

    combined = {
        "finance": {
            "result": [
                {
                    "start": offset,
                    "count": len(records),
                    "total": total if total is not None else len(records),
                    "records": records,
                    "userHasReadRecord": last_page.get("userHasReadRecord", False),
                    "useRecords": last_page.get("useRecords", True),
                }
            ],
            "error": None,
        }
    }
    if combined_root is not None:
        combined_path = _join_output(combined_root, "all_screener.json")
        save_json(combined, combined_path)
        print(f"Saved {len(records)} combined records to {combined_path}")
    return combined


def fetch_all_sectors(
    size: int,
    offset: int = 0,
    sort_type: str = "DESC",
    sort_field: str = "intradaymarketcap",
    min_revenue: float | None = None,
    include_fields: list[str] | None = None,
    regions: list[str] | None = None,
    cookie: str | None = None,
    crumb: str | None = None,
    formatted: bool = True,
    use_records_response: bool = True,
    lang: str = "en-US",
    query_region: str = "US",
    require_positive: bool = True,
    output_dir: str | None = None,
    run_timestamp: str | None = None,
) -> dict[str, Any]:
    """Fetch every sector on its own to stay under Yahoo's pagination cap."""
    run_ts = run_timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    last_page: dict[str, Any] = {}
    for sector in SECTORS:
        sector_root = _join_output(output_dir, sector) if output_dir is not None else None
        page_log_dir = (
            _join_output(sector_root, run_ts) if sector_root is not None else None
        )
        combined = fetch_all_pages(
            size,
            offset,
            sector,
            None,
            sort_type,
            sort_field,
            min_revenue,
            include_fields,
            regions,
            cookie,
            crumb,
            formatted,
            use_records_response,
            lang,
            query_region,
            require_positive,
            combined_output_dir=sector_root,
            page_log_dir=page_log_dir,
        )
        last_page = _page(combined)
        for record in last_page.get("records") or []:
            ticker = str(record.get("ticker") or "")
            if ticker in seen:
                continue
            seen.add(ticker)
            records.append(record)
        print(f"Sector {sector}: {last_page.get('count', 0)} listings")

    merged = {
        "finance": {
            "result": [
                {
                    "start": offset,
                    "count": len(records),
                    "total": len(records),
                    "records": records,
                    "userHasReadRecord": last_page.get("userHasReadRecord", False),
                    "useRecords": last_page.get("useRecords", True),
                }
            ],
            "error": None,
        }
    }
    if output_dir is not None:
        combined_path = _join_output(output_dir, "all_screener.json")
        save_json(merged, combined_path)
        print(f"Saved {len(records)} combined records to {combined_path}")
    return merged


def infer_sector(records: list[dict[str, Any]]) -> str:
    """Pick the dominant Yahoo sector label for a set of listings."""
    if not records:
        return "Unknown"
    counts: dict[str, int] = {}
    for record in records:
        sector = record.get("sector") or "Unknown"
        counts[sector] = counts.get(sector, 0) + 1
    return max(counts, key=lambda name: (counts[name], name))


def write_dedup(
    records: list[dict[str, Any]], output: str, source: str | Path
) -> int:
    """Write an organization-level dedup file for one screener export."""
    from naas_abi_marketplace.applications.yahoofinance.integrations.utils.DedupScreenerOrgs import (
        dedup_records,
    )

    organizations = dedup_records(records)
    payload = {
        "source": str(source),
        "inputCount": len(records),
        "organizationCount": len(organizations),
        "organizations": organizations,
    }
    save_json(payload, output)
    return len(organizations)


def fetch_all_industries(
    size: int,
    offset: int = 0,
    sort_type: str = "DESC",
    sort_field: str = "intradaymarketcap",
    min_revenue: float | None = None,
    include_fields: list[str] | None = None,
    regions: list[str] | None = None,
    cookie: str | None = None,
    crumb: str | None = None,
    formatted: bool = True,
    use_records_response: bool = True,
    lang: str = "en-US",
    query_region: str = "US",
    require_positive: bool = True,
    run_timestamp: str | None = None,
) -> dict[str, Any]:
    """Fetch each industry into data/<sector>/<industry>/<timestamp>/ and merge."""
    run_ts = run_timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    merged_records: list[dict[str, Any]] = []
    seen: set[str] = set()
    last_page: dict[str, Any] = {}

    for industry in INDUSTRIES:
        probe = fetch_screener(
            1,
            0,
            None,
            industry,
            sort_type,
            sort_field,
            min_revenue,
            include_fields,
            regions,
            cookie,
            crumb,
            formatted,
            use_records_response,
            lang,
            query_region,
            require_positive,
        )
        probe_page = _page(probe)
        total = probe_page.get("total", 0)
        if not total:
            print(f"Industry {industry}: 0 listings, skip")
            continue

        probe_records = probe_page.get("records") or []
        sector = infer_sector(probe_records)
        industry_root = _join_output(sector, industry)
        page_log_dir = _join_output(industry_root, run_ts)
        combined = fetch_all_pages(
            size,
            offset,
            sector,
            industry,
            sort_type,
            sort_field,
            min_revenue,
            include_fields,
            regions,
            cookie,
            crumb,
            formatted,
            use_records_response,
            lang,
            query_region,
            require_positive,
            combined_output_dir=industry_root,
            page_log_dir=page_log_dir,
        )
        last_page = _page(combined)
        industry_records = last_page.get("records") or []
        combined_path = _join_output(industry_root, "all_screener.json")
        org_count = write_dedup(
            industry_records,
            _join_output(industry_root, "all_screener_dedup.json"),
            combined_path,
        )
        print(
            f"Industry {industry} ({sector}): {len(industry_records)} listings, "
            f"{org_count} organizations"
        )
        for record in industry_records:
            ticker = str(record.get("ticker") or "")
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            merged_records.append(record)

    merged = {
        "finance": {
            "result": [
                {
                    "start": offset,
                    "count": len(merged_records),
                    "total": len(merged_records),
                    "records": merged_records,
                    "userHasReadRecord": last_page.get("userHasReadRecord", False),
                    "useRecords": last_page.get("useRecords", True),
                }
            ],
            "error": None,
        }
    }
    combined_path = "_all/all_screener.json"
    save_json(merged, combined_path)
    org_count = write_dedup(
        merged_records, "_all/all_screener_dedup.json", combined_path
    )
    print(
        f"Saved {len(merged_records)} combined listings to {combined_path} "
        f"and {org_count} organizations to _all/all_screener_dedup.json"
    )
    return merged


def main(args: argparse.Namespace | None = None) -> None:
    args = args or parse_args()
    if args.list_taxonomy:
        data = taxonomy()
        if args.list_taxonomy in ("regions", "all"):
            print("REGIONS")
            for item in data["regions"]:
                print(item)
        if args.list_taxonomy in ("sectors", "all"):
            print("SECTORS")
            for item in data["sectors"]:
                print(item)
        if args.list_taxonomy in ("industries", "all"):
            print("INDUSTRIES")
            for item in data["industries"]:
                print(item)
        return
    taxonomy_path = write_taxonomy()
    print(f"TAXONOMY={taxonomy_path}")
    if args.all:
        run_ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        if args.by_industry:
            write_taxonomy()
            fetch_all_industries(
                args.size,
                args.offset,
                args.sort_type,
                args.sort_field,
                args.min_revenue,
                require_positive=args.require_positive,
                run_timestamp=run_ts,
            )
            print(f"RUN_TIMESTAMP={run_ts}")
            return

        export_root = output_dir_for(args.sector, args.industry)
        page_log_dir = (
            _join_output(export_root, run_ts) if args.timestamp_dir else export_root
        )
        write_taxonomy()
        if args.by_sector:
            fetch_all_sectors(
                args.size,
                args.offset,
                args.sort_type,
                args.sort_field,
                args.min_revenue,
                require_positive=args.require_positive,
                output_dir=export_root,
                run_timestamp=run_ts,
            )
        else:
            fetch_all_pages(
                args.size,
                args.offset,
                args.sector,
                args.industry,
                args.sort_type,
                args.sort_field,
                args.min_revenue,
                require_positive=args.require_positive,
                combined_output_dir=export_root,
                page_log_dir=page_log_dir,
            )
        print(f"OUTPUT_DIR={export_root}")
        if args.timestamp_dir:
            print(f"PAGE_LOG_DIR={page_log_dir}")
        return

    result = fetch_screener(
        args.size,
        args.offset,
        args.sector,
        args.industry,
        args.sort_type,
        args.sort_field,
        args.min_revenue,
        require_positive=args.require_positive,
    )
    output = args.output
    if output is None:
        output = _join_output(
            output_dir_for(args.sector, args.industry),
            f"{args.offset}_{args.size}_screener.json",
        )
    save_json(result, output)

    page = _page(result)
    print(
        f"Saved {page.get('count', 0)} records "
        f"(offset {page.get('start', args.offset)}, total {page.get('total', 0)}) "
        f"to {output}"
    )


if __name__ == "__main__":
    from naas_abi_marketplace.applications.yahoofinance.scripts.RunScreenerExport import (
        main as run_cli,
    )

    run_cli()
