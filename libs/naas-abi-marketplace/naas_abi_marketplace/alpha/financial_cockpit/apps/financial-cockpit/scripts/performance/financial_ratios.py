#!/usr/bin/env python3
"""Generate the **fake** Financial Ratios demo dataset for Financial Cockpit.

The template ships no upstream ratio source, so this standalone script (no ABI
runtime dependency — plain stdlib) computes a ratio pack from the two datasets
that already exist and wires it into the manifest. It is the last link of the
demo-data chain:

    performance/balance_sheet.py → performance/cash_flow.py → this script

Stock-based ratios (ROE, ROA, debt ratio, quick ratio) read the balance-sheet
snapshot directly. Flow-based ratios (gross and EBITDA margin) need an income
statement, which the balance sheet does not carry — so they read the revenue /
gross profit / EBITDA / net income lines the cash flow generator publishes,
rather than re-synthesizing them here. That keeps the ratios page numerically
consistent with both other pages. Flow figures are annualized over the trailing
twelve months.

Every record carries an industry ``benchmark`` and an internal ``target`` plus
``higher_is_better``, which the section uses for the benchmark bars, the radar
scoring and the KPI tones.

Run from the app root (after the two scripts above):
    python scripts/performance/financial_ratios.py
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from datetime import datetime

# web/data mirrors the R2 layout the Next.js app reads from.
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_ROOT = os.path.join(APP_ROOT, "web", "data")
ENTITIES_DIR = os.path.join(DATA_ROOT, "entities")

FR_PAGE_ID = "financial-ratios"
FR_RELATIVE_PATH = "financial_ratios/financial_ratios.json"
BS_RELATIVE_PATH = os.path.join("balance_sheet", "balance_sheet.json")
CF_RELATIVE_PATH = os.path.join("cash_flow", "cash_flow.json")
SCHEMA_VERSION = "1.0"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Balance-sheet categories this script reads.
INVENTORY_LINE = "Inventory"
CURRENT_ASSET_LINES = (
    "Inventory",
    "Trade receivables",
    "Other receivables",
    "Cash & equivalents",
)
NON_CURRENT_ASSET_LINES = (
    "Intangible assets",
    "Property, plant & equipment",
    "Financial assets",
)
CURRENT_LIABILITY_LINES = (
    "Trade payables",
    "Tax & social liabilities",
    "Short-term borrowings",
)
NON_CURRENT_LIABILITY_LINES = ("Long-term borrowings",)
EQUITY_LINES = ("Share capital", "Reserves", "Net income for the year")


@dataclass(frozen=True)
class RatioDef:
    key: str
    label: str
    category: str
    category_label: str
    unit: str  # "percent" (stored as a rate) | "ratio"
    benchmark: float
    target: float
    higher_is_better: bool
    hint: str


# Order drives the table and the radar axes.
RATIO_DEFS = [
    RatioDef(
        "gross_margin", "Gross Margin", "profitability", "Profitability", "percent",
        benchmark=0.58, target=0.64, higher_is_better=True,
        hint="Gross profit over revenue, trailing twelve months.",
    ),
    RatioDef(
        "ebitda_margin", "EBITDA Margin", "profitability", "Profitability", "percent",
        benchmark=0.16, target=0.20, higher_is_better=True,
        hint="EBITDA over revenue, trailing twelve months.",
    ),
    RatioDef(
        "roe", "Return on Equity", "returns", "Returns", "percent",
        benchmark=0.12, target=0.15, higher_is_better=True,
        hint="Trailing twelve-month net income over shareholders' equity.",
    ),
    RatioDef(
        "roa", "Return on Assets", "returns", "Returns", "percent",
        benchmark=0.06, target=0.08, higher_is_better=True,
        hint="Trailing twelve-month net income over total assets.",
    ),
    RatioDef(
        "debt_ratio", "Debt Ratio", "leverage", "Leverage", "percent",
        benchmark=0.55, target=0.45, higher_is_better=False,
        hint="Total liabilities over total assets — lower means less leveraged.",
    ),
    RatioDef(
        "quick_ratio", "Quick Ratio", "liquidity", "Liquidity", "ratio",
        benchmark=1.0, target=1.2, higher_is_better=True,
        hint="Current assets excluding inventory over current liabilities.",
    ),
]

# Trailing window for flow-based ratios.
TTM_MONTHS = 12


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _snapshots(payload: dict) -> list[tuple[str, str, str, dict[str, float]]]:
    """Collapse balance-sheet records into ``(period, scenario, year, amounts)``."""
    by_period: dict[str, dict[str, float]] = {}
    meta: dict[str, tuple[str, str]] = {}
    for record in payload.get("records", []):
        period = record["period"]
        amounts = by_period.setdefault(period, {})
        category = record["category"]
        amounts[category] = amounts.get(category, 0.0) + float(record["amount"])
        meta[period] = (record["scenario"], record["scenario_year"])
    return [
        (period, meta[period][0], meta[period][1], by_period[period])
        for period in sorted(by_period)
    ]


def _total(amounts: dict[str, float], lines: tuple[str, ...]) -> float:
    return sum(amounts.get(line, 0.0) for line in lines)


def _income_by_period(cash_flow: dict) -> dict[str, dict[str, float]]:
    """Read the monthly P&L the cash flow generator publishes as memo lines."""
    out: dict[str, dict[str, float]] = {}
    for record in cash_flow.get("records", []):
        activity = record.get("activity")
        category = record.get("category")
        if activity == "memo" and category in {"Revenue", "Gross profit", "EBITDA"}:
            out.setdefault(record["period"], {})[category] = float(record["amount"])
        elif activity == "operating" and category == "Net income":
            out.setdefault(record["period"], {})["Net income"] = float(record["amount"])
    return out


def _build_records(entity_id: str, balance_sheet: dict, cash_flow: dict) -> list[dict]:
    snapshots = _snapshots(balance_sheet)
    income = _income_by_period(cash_flow)
    periods = [period for period, _, _, _ in snapshots]

    def flow(line: str) -> list[float]:
        return [income.get(period, {}).get(line, 0.0) for period in periods]

    revenue = flow("Revenue")
    gross_profit = flow("Gross profit")
    ebitda = flow("EBITDA")
    net_income = flow("Net income")

    records: list[dict] = []
    for index, (period, scenario, scenario_year, amounts) in enumerate(snapshots):
        start = max(0, index - TTM_MONTHS + 1)
        window = slice(start, index + 1)
        # Annualize when fewer than twelve months of history are available.
        months = index - start + 1
        scale = TTM_MONTHS / months
        ttm_revenue = sum(revenue[window]) * scale
        ttm_gross = sum(gross_profit[window]) * scale
        ttm_ebitda = sum(ebitda[window]) * scale
        ttm_income = sum(net_income[window]) * scale

        current_assets = _total(amounts, CURRENT_ASSET_LINES)
        non_current_assets = _total(amounts, NON_CURRENT_ASSET_LINES)
        total_assets = current_assets + non_current_assets
        current_liabilities = _total(amounts, CURRENT_LIABILITY_LINES)
        total_liabilities = current_liabilities + _total(
            amounts, NON_CURRENT_LIABILITY_LINES
        )
        equity = _total(amounts, EQUITY_LINES)
        inventory = amounts.get(INVENTORY_LINE, 0.0)

        values = {
            "gross_margin": ttm_gross / ttm_revenue if ttm_revenue > 0 else None,
            "ebitda_margin": ttm_ebitda / ttm_revenue if ttm_revenue > 0 else None,
            "roe": ttm_income / equity if equity > 0 else None,
            "roa": ttm_income / total_assets if total_assets > 0 else None,
            "debt_ratio": total_liabilities / total_assets if total_assets > 0 else None,
            "quick_ratio": (
                (current_assets - inventory) / current_liabilities
                if current_liabilities > 0
                else None
            ),
        }

        for definition in RATIO_DEFS:
            value = values[definition.key]
            if value is None:
                continue
            records.append(
                {
                    "period": period,
                    "scenario": scenario,
                    "scenario_year": scenario_year,
                    "organization_slug": entity_id,
                    "category": definition.category,
                    "category_label": definition.category_label,
                    "ratio_key": definition.key,
                    "ratio_label": definition.label,
                    "value": round(value, 6),
                    "unit": definition.unit,
                    "benchmark": definition.benchmark,
                    "target": definition.target,
                    "higher_is_better": definition.higher_is_better,
                    "hint": definition.hint,
                }
            )

    return records


def _scenarios(payload: dict, records: list[dict]) -> list[dict[str, str]]:
    """Reuse the balance sheet's scenario list, or rebuild it from the records."""
    existing = payload.get("scenarios")
    if existing:
        return existing
    months = sorted({record["scenario"] for record in records})
    years = sorted({record["scenario_year"] for record in records})
    options: list[dict[str, str]] = [
        {"id": year, "label": year, "split": "date_year"} for year in reversed(years)
    ]
    for month in reversed(months):
        year_part, _, month_part = month.partition("-")
        options.append(
            {
                "id": month,
                "label": f"{MONTH_LABELS[int(month_part)]} {year_part}",
                "split": "date_month",
            }
        )
    return options


def _patch_manifest(entity_id: str, data_version: str) -> None:
    path = os.path.join(ENTITIES_DIR, entity_id, "manifest.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    pages = manifest.setdefault("datasets", {}).setdefault("pages", {})
    pages[FR_PAGE_ID] = [FR_RELATIVE_PATH]
    manifest["data_version"] = data_version
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entities_with_sources() -> list[str]:
    """Entities carrying both upstream datasets this script reads."""
    out: list[str] = []
    for manifest_path in glob.glob(os.path.join(ENTITIES_DIR, "*", "manifest.json")):
        entity_dir = os.path.dirname(manifest_path)
        if all(
            os.path.exists(os.path.join(entity_dir, relative))
            for relative in (BS_RELATIVE_PATH, CF_RELATIVE_PATH)
        ):
            out.append(os.path.basename(entity_dir))
    return sorted(out)


def main() -> None:
    data_version = datetime.now().strftime("%Y-%m-%d %H:%M")
    entities = _entities_with_sources()
    if not entities:
        raise SystemExit(
            "No balance sheet + cash flow found — run scripts/performance/balance_sheet.py "
            "then scripts/performance/cash_flow.py first."
        )
    print(f"Generating fake financial ratios for {len(entities)} entity(ies)…")

    for entity_id in entities:
        balance_sheet = _load(entity_id, BS_RELATIVE_PATH)
        cash_flow = _load(entity_id, CF_RELATIVE_PATH)
        if balance_sheet is None or cash_flow is None:
            continue
        records = _build_records(entity_id, balance_sheet, cash_flow)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "data_version": data_version,
            "entity_id": entity_id,
            "scenarios": _scenarios(balance_sheet, records),
            "records": records,
        }
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "financial_ratios")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "financial_ratios.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):5d} records")

    print("Done.")


if __name__ == "__main__":
    main()
