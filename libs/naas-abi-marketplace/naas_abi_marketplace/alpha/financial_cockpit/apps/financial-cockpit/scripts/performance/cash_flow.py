#!/usr/bin/env python3
"""Generate the **fake** Cash Flow demo dataset for Financial Cockpit.

The template ships no upstream cash-flow source, so this standalone script (no
ABI runtime dependency — plain stdlib) derives an indirect-method cash flow
statement from the balance sheet produced by ``performance/balance_sheet.py`` and
wires it into the manifest.

Deriving it from the balance sheet keeps the two pages consistent: the closing
cash of every month equals the "Cash & equivalents" line of that month's
balance sheet, and the movement between two snapshots is decomposed into
operating / investing / financing so that

    opening cash + operating + investing + financing == closing cash

holds exactly for every period. Investing and financing are computed from the
balance-sheet deltas (fixed assets, borrowings, share capital) and operating is
the residual, itself split into named lines with "Other operating items" as the
plug. Amounts are deterministic (seeded RNG) so re-running is stable.

The balance sheet carries no income statement, and its accumulating "Net income
for the year" line is too noisy month-over-month to difference, so this script
synthesizes a monthly P&L (revenue → gross profit → EBITDA → net income)
anchored on total assets. Memo lines (``activity: "memo"``) publish that P&L
alongside the opening/closing cash anchors: the section reads them for the
waterfall and the cash-conversion KPI, and ``performance/financial_ratios.py``
reads them so the ratios page agrees with this one. They are excluded from the
statement itself.

Run from the app root (after performance/balance_sheet.py):
    python scripts/performance/cash_flow.py
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import random
from datetime import datetime

# web/data mirrors the R2 layout the Next.js app reads from.
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_ROOT = os.path.join(APP_ROOT, "web", "data")
ENTITIES_DIR = os.path.join(DATA_ROOT, "entities")

CF_PAGE_ID = "cash-flow"
CF_RELATIVE_PATH = "cash_flow/cash_flow.json"
BS_RELATIVE_PATH = os.path.join("balance_sheet", "balance_sheet.json")
SCHEMA_VERSION = "1.0"

ACTIVITY_LABELS = {
    "operating": "Operating activities",
    "investing": "Investing activities",
    "financing": "Financing activities",
    "memo": "Memo",
}

# Category order within each activity — drives table + waterfall rendering.
CATEGORY_ORDER = {
    "operating": [
        "Net income",
        "Depreciation & amortisation",
        "Change in working capital",
        "Other operating items",
    ],
    "investing": [
        "Capital expenditure",
        "Disposals of fixed assets",
        "Financial investments",
    ],
    "financing": [
        "New borrowings",
        "Debt repayments",
        "Share capital increase",
        "Dividends paid",
    ],
}

# Balance-sheet categories this script reads.
CASH_LINE = "Cash & equivalents"
NON_CURRENT_ASSET_LINES = (
    "Intangible assets",
    "Property, plant & equipment",
    "Financial assets",
)
WORKING_CAPITAL_ASSETS = ("Inventory", "Trade receivables", "Other receivables")
WORKING_CAPITAL_LIABILITIES = ("Trade payables", "Tax & social liabilities")
BORROWING_LINES = ("Long-term borrowings", "Short-term borrowings")
CAPITAL_LINE = "Share capital"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

CURRENT_ASSET_LINES = (
    "Inventory",
    "Trade receivables",
    "Other receivables",
    "Cash & equivalents",
)

# Monthly depreciation rate applied to opening non-current assets.
DEPRECIATION_RATE = 0.008
# Monthly interest rate applied to opening gross financial debt (~4.2%/year).
INTEREST_RATE = 0.0035
# Corporate income tax rate applied to a positive pre-tax result.
TAX_RATE = 0.25
# Cash held one month before the first balance-sheet snapshot, as a fraction of
# it — only used to open the very first period.
OPENING_CASH_FACTOR = 0.985
# Share of trailing twelve-month net income paid out as a dividend each June.
DIVIDEND_PAYOUT = 0.25


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"cf-{entity_id}".encode()).digest()[:4], "big")


def _load_balance_sheet(entity_id: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, BS_RELATIVE_PATH)
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


def _income_statement(
    rng: random.Random,
    snapshots: list[tuple[str, str, str, dict[str, float]]],
) -> list[dict[str, float]]:
    """Synthesize a monthly P&L anchored on the balance sheet.

    Revenue is a slowly drifting multiple of total assets; margins drift upward
    over the horizon. Depreciation and interest are charged on the *opening*
    balance-sheet position so the result reconciles with the same figures the
    cash flow uses.
    """
    asset_turnover = rng.uniform(0.095, 0.115)  # monthly revenue / total assets
    gross_margin_base = rng.uniform(0.58, 0.64)
    ebitda_margin_base = rng.uniform(0.15, 0.19)

    out: list[dict[str, float]] = []
    for index, (_, _, _, amounts) in enumerate(snapshots):
        previous = snapshots[index - 1][3] if index > 0 else amounts
        total_assets = _total(amounts, CURRENT_ASSET_LINES) + _total(
            amounts, NON_CURRENT_ASSET_LINES
        )
        drift = index / max(1, len(snapshots) - 1)

        revenue = total_assets * asset_turnover * rng.uniform(0.94, 1.06)
        gross_pct = gross_margin_base + 0.03 * drift + rng.uniform(-0.012, 0.012)
        ebitda_pct = ebitda_margin_base + 0.025 * drift + rng.uniform(-0.010, 0.010)

        depreciation = _total(previous, NON_CURRENT_ASSET_LINES) * DEPRECIATION_RATE
        interest = _total(previous, BORROWING_LINES) * INTEREST_RATE
        ebitda = revenue * ebitda_pct
        pretax = ebitda - depreciation - interest
        tax = max(0.0, pretax) * TAX_RATE

        out.append(
            {
                "revenue": revenue,
                "gross_profit": revenue * gross_pct,
                "ebitda": ebitda,
                "depreciation": depreciation,
                "interest": interest,
                "tax": tax,
                "net_income": pretax - tax,
            }
        )
    return out


def _build_records(entity_id: str, payload: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    snapshots = _snapshots(payload)
    income = _income_statement(rng, snapshots)
    records: list[dict] = []

    for index, (period, scenario, scenario_year, current) in enumerate(snapshots):
        if index == 0:
            # No prior snapshot: assume a slightly lower opening cash balance and
            # treat the rest of the balance sheet as unchanged over the month.
            previous = dict(current)
            previous[CASH_LINE] = current.get(CASH_LINE, 0.0) * OPENING_CASH_FACTOR
        else:
            previous = snapshots[index - 1][3]

        opening_cash = previous.get(CASH_LINE, 0.0)
        closing_cash = current.get(CASH_LINE, 0.0)
        net_change = closing_cash - opening_cash

        month = income[index]
        depreciation = month["depreciation"]

        # --- investing: fixed-asset movements grossed up for depreciation.
        nca_now = _total(current, NON_CURRENT_ASSET_LINES)
        nca_before = _total(previous, NON_CURRENT_ASSET_LINES)
        gross_investment = (nca_now - nca_before) + depreciation

        disposals = 0.0
        capex = 0.0
        if gross_investment >= 0:
            capex = -gross_investment
        else:
            # Assets shrank faster than depreciation — book it as a disposal.
            disposals = -gross_investment
        financial_investments = -abs(nca_before) * rng.uniform(0.0002, 0.0015)
        investing_lines = {
            "Capital expenditure": capex,
            "Disposals of fixed assets": disposals,
            "Financial investments": financial_investments,
        }
        investing_total = sum(investing_lines.values())

        # --- financing: borrowings + share capital, minus a dividend.
        debt_change = _total(current, BORROWING_LINES) - _total(previous, BORROWING_LINES)
        capital_change = current.get(CAPITAL_LINE, 0.0) - previous.get(CAPITAL_LINE, 0.0)
        dividends = 0.0
        # Pay a dividend once a year, in June, out of the trailing year's result.
        if period[5:7] == "06":
            trailing = sum(m["net_income"] for m in income[max(0, index - 12) : index])
            dividends = max(0.0, trailing) * DIVIDEND_PAYOUT
        financing_lines = {
            "New borrowings": max(0.0, debt_change),
            "Debt repayments": min(0.0, debt_change),
            "Share capital increase": capital_change,
            "Dividends paid": -dividends,
        }
        financing_total = sum(financing_lines.values())

        # --- operating: the residual, so the three activities reconcile exactly.
        operating_total = net_change - investing_total - financing_total

        net_income = month["net_income"]

        wc_assets_change = _total(current, WORKING_CAPITAL_ASSETS) - _total(
            previous, WORKING_CAPITAL_ASSETS
        )
        wc_liabilities_change = _total(current, WORKING_CAPITAL_LIABILITIES) - _total(
            previous, WORKING_CAPITAL_LIABILITIES
        )
        working_capital_change = -(wc_assets_change - wc_liabilities_change)

        named_operating = net_income + depreciation + working_capital_change
        operating_lines = {
            "Net income": net_income,
            "Depreciation & amortisation": depreciation,
            "Change in working capital": working_capital_change,
            "Other operating items": operating_total - named_operating,
        }

        def emit(activity: str, category: str, amount: float) -> None:
            records.append(
                {
                    "period": period,
                    "scenario": scenario,
                    "scenario_year": scenario_year,
                    "organization_slug": entity_id,
                    "activity": activity,
                    "activity_label": ACTIVITY_LABELS[activity],
                    "category": category,
                    "amount": round(amount, 2),
                }
            )

        for category in CATEGORY_ORDER["operating"]:
            emit("operating", category, operating_lines[category])
        for category in CATEGORY_ORDER["investing"]:
            emit("investing", category, investing_lines[category])
        for category in CATEGORY_ORDER["financing"]:
            emit("financing", category, financing_lines[category])
        # Waterfall anchors + the synthesized P&L the ratios page reads back.
        emit("memo", "Opening cash", opening_cash)
        emit("memo", "Closing cash", closing_cash)
        emit("memo", "Revenue", month["revenue"])
        emit("memo", "Gross profit", month["gross_profit"])
        emit("memo", "EBITDA", month["ebitda"])

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
    pages[CF_PAGE_ID] = [CF_RELATIVE_PATH]
    manifest["data_version"] = data_version
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entities_with_balance_sheet() -> list[str]:
    out: list[str] = []
    for manifest_path in glob.glob(os.path.join(ENTITIES_DIR, "*", "manifest.json")):
        entity_id = os.path.basename(os.path.dirname(manifest_path))
        if os.path.exists(os.path.join(ENTITIES_DIR, entity_id, BS_RELATIVE_PATH)):
            out.append(entity_id)
    return sorted(out)


def main() -> None:
    data_version = datetime.now().strftime("%Y-%m-%d %H:%M")
    entities = _entities_with_balance_sheet()
    if not entities:
        raise SystemExit(
            "No balance sheet found — run scripts/performance/balance_sheet.py first."
        )
    print(f"Generating fake cash flow statements for {len(entities)} entity(ies)…")

    for entity_id in entities:
        balance_sheet = _load_balance_sheet(entity_id)
        if balance_sheet is None:
            continue
        records = _build_records(entity_id, balance_sheet)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "data_version": data_version,
            "entity_id": entity_id,
            "scenarios": _scenarios(balance_sheet, records),
            "records": records,
        }
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "cash_flow")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "cash_flow.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):5d} records")

    print("Done.")


if __name__ == "__main__":
    main()
