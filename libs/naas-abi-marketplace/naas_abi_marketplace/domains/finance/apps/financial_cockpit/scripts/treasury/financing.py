#!/usr/bin/env python3
"""Generate the **fake** Financing demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/balance_sheet.py → performance/cash_flow.py → this script

Answers "how is the company financed?". The balance sheet already states how
much debt is outstanding each month; this script only decides **who lent it and
on what terms** — splitting the borrowings lines across a facility book by
fixed weights, so the loans always sum back to the balance sheet.

Rates are drawn per facility (fixed or floating over Euribor) and the interest
charged is the outstanding balance at that rate, which reconciles with the
interest the cash flow generator books. Each facility carries an origination
and maturity date, so the page can show a maturity timeline and the next
repayment wall.

One record per facility per month.

Run from the app root (after the two scripts above):
    python scripts/treasury/financing.py
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import random
from dataclasses import dataclass
from datetime import datetime

# web/data mirrors the R2 layout the Next.js app reads from.
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_ROOT = os.path.join(APP_ROOT, "web", "data")
ENTITIES_DIR = os.path.join(DATA_ROOT, "entities")

FIN_PAGE_ID = "financing"
FIN_RELATIVE_PATH = "financing/loans.json"
BS_RELATIVE_PATH = os.path.join("balance_sheet", "balance_sheet.json")
SCHEMA_VERSION = "1.0"

LONG_TERM_LINE = "Long-term borrowings"
SHORT_TERM_LINE = "Short-term borrowings"

# Asset lines summed for the Debt Ratio denominator.
ASSET_LINES = (
    "Intangible assets",
    "Property, plant & equipment",
    "Financial assets",
    "Inventory",
    "Trade receivables",
    "Other receivables",
    "Cash & equivalents",
)

# Memo records carry the balance-sheet context the loan book itself cannot —
# `instrument: "memo"` keeps them out of the loans table while the Debt Ratio
# KPI reads them.
MEMO_INSTRUMENT = "memo"
MEMO_TOTAL_ASSETS = "_total_assets"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@dataclass(frozen=True)
class LoanDef:
    key: str
    label: str
    lender: str
    instrument: str  # "term_loan" | "revolving" | "lease" | "bond" | "state_backed"
    # "long" draws from Long-term borrowings, "short" from Short-term.
    bucket: str
    weight: float
    annual_rate: float
    is_floating: bool
    origination: str
    maturity: str
    covenant: str


LOANS = [
    LoanDef(
        "bnp_term_a", "Term loan A", "BNP Paribas", "term_loan", "long", 0.315,
        0.0385, False, "2022-06-30", "2028-06-30", "Net debt / EBITDA < 3.0x",
    ),
    LoanDef(
        "sg_term_b", "Term loan B", "Société Générale", "term_loan", "long", 0.225,
        0.0442, True, "2023-03-31", "2029-03-31", "Net debt / EBITDA < 3.0x",
    ),
    LoanDef(
        "bei_green", "Green investment facility", "Banque Européenne d'Investissement",
        "term_loan", "long", 0.145, 0.0295, False, "2024-01-31", "2031-01-31",
        "Capex earmarked to energy efficiency",
    ),
    LoanDef(
        "bond_private", "Private placement 2027", "Institutional investors", "bond",
        "long", 0.135, 0.0510, False, "2021-09-30", "2027-09-30",
        "Interest cover > 4.0x",
    ),
    LoanDef(
        "lease_fleet", "Fleet & equipment leases", "CA Leasing", "lease", "long",
        0.090, 0.0475, False, "2023-07-31", "2028-07-31", "None",
    ),
    LoanDef(
        "state_pge", "State-backed loan", "BPI France", "state_backed", "long",
        0.090, 0.0225, False, "2022-01-31", "2027-01-31", "None",
    ),
    LoanDef(
        "rcf_bnp", "Revolving credit facility", "BNP Paribas", "revolving", "short",
        0.620, 0.0525, True, "2024-06-30", "2027-06-30", "Net debt / EBITDA < 3.0x",
    ),
    LoanDef(
        "factoring", "Receivables factoring line", "Eurofactor", "revolving", "short",
        0.380, 0.0590, True, "2025-01-31", "2027-12-31", "None",
    ),
]

# Reference rate the floating facilities price over, per calendar year.
EURIBOR_BY_YEAR = {
    "2023": 0.0325,
    "2024": 0.0355,
    "2025": 0.0270,
    "2026": 0.0215,
}
DEFAULT_EURIBOR = 0.0250


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"fin-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _borrowings_by_period(
    balance_sheet: dict,
) -> list[tuple[str, str, str, dict[str, float], float]]:
    """``(period, scenario, year, {bucket: amount}, total assets)``."""
    periods: dict[str, tuple[str, str]] = {}
    buckets: dict[str, dict[str, float]] = {}
    assets: dict[str, float] = {}
    for record in balance_sheet.get("records", []):
        category = record.get("category")
        period = record["period"]
        if category in (LONG_TERM_LINE, SHORT_TERM_LINE):
            periods[period] = (record["scenario"], record["scenario_year"])
            bucket = "long" if category == LONG_TERM_LINE else "short"
            buckets.setdefault(period, {})[bucket] = (
                buckets.setdefault(period, {}).get(bucket, 0.0) + float(record["amount"])
            )
        if category in ASSET_LINES:
            assets[period] = assets.get(period, 0.0) + float(record["amount"])
    return [
        (period, *periods[period], buckets[period], assets.get(period, 0.0))
        for period in sorted(periods)
    ]


def _build_records(entity_id: str, balance_sheet: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    periods = _borrowings_by_period(balance_sheet)

    # Weights are normalized per bucket so each bucket's loans sum to its line.
    bucket_totals = {
        bucket: sum(loan.weight for loan in LOANS if loan.bucket == bucket)
        for bucket in ("long", "short")
    }
    # A stable spread over the reference rate for each floating facility.
    spreads = {
        loan.key: loan.annual_rate - EURIBOR_BY_YEAR.get("2026", DEFAULT_EURIBOR)
        for loan in LOANS
        if loan.is_floating
    }

    records: list[dict] = []
    previous_balances: dict[str, float] = {}

    for period, scenario, scenario_year, buckets, total_assets in periods:
        euribor = EURIBOR_BY_YEAR.get(scenario_year, DEFAULT_EURIBOR)

        for loan in LOANS:
            bucket_total = buckets.get(loan.bucket, 0.0)
            share = loan.weight / bucket_totals[loan.bucket]
            outstanding = bucket_total * share

            # Floating facilities reprice with the reference rate; fixed ones do
            # not. Spreads stay constant, which is what makes the rate move.
            if loan.is_floating:
                rate = euribor + spreads[loan.key]
            else:
                rate = loan.annual_rate

            interest = outstanding * rate / 12.0
            previous = previous_balances.get(loan.key)
            repayment = max(0.0, previous - outstanding) if previous is not None else 0.0
            drawdown = max(0.0, outstanding - previous) if previous is not None else 0.0
            previous_balances[loan.key] = outstanding

            # A facility past its maturity date is shown as repaid, not negative.
            matured = period > loan.maturity

            records.append(
                {
                    "period": period,
                    "scenario": scenario,
                    "scenario_year": scenario_year,
                    "organization_slug": entity_id,
                    "loan": loan.key,
                    "loan_label": loan.label,
                    "lender": loan.lender,
                    "instrument": loan.instrument,
                    "bucket": loan.bucket,
                    "outstanding": round(0.0 if matured else outstanding, 2),
                    "rate": round(rate, 6),
                    "is_floating": loan.is_floating,
                    "reference_rate": round(euribor, 6) if loan.is_floating else None,
                    "interest": round(0.0 if matured else interest, 2),
                    "repayment": round(repayment, 2),
                    "drawdown": round(drawdown, 2),
                    "origination": loan.origination,
                    "maturity": loan.maturity,
                    "covenant": loan.covenant,
                    "is_matured": matured,
                }
            )

        # Memo: the asset base the Debt Ratio KPI measures the debt against.
        records.append(
            {
                "period": period,
                "scenario": scenario,
                "scenario_year": scenario_year,
                "organization_slug": entity_id,
                "loan": MEMO_TOTAL_ASSETS,
                "loan_label": "Total assets",
                "lender": "",
                "instrument": MEMO_INSTRUMENT,
                "bucket": "memo",
                "outstanding": round(total_assets, 2),
                "rate": 0.0,
                "is_floating": False,
                "reference_rate": None,
                "interest": 0.0,
                "repayment": 0.0,
                "drawdown": 0.0,
                "origination": "",
                "maturity": "",
                "covenant": "",
                "is_matured": False,
            }
        )

    # Keep the RNG referenced so the seed stays meaningful if weights gain jitter.
    del rng
    return records


def _scenarios(payload: dict, records: list[dict]) -> list[dict[str, str]]:
    """Reuse the upstream scenario list, or rebuild it from the records."""
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
    pages[FIN_PAGE_ID] = [FIN_RELATIVE_PATH]
    manifest["data_version"] = data_version
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entities_with_sources() -> list[str]:
    out: list[str] = []
    for manifest_path in glob.glob(os.path.join(ENTITIES_DIR, "*", "manifest.json")):
        entity_dir = os.path.dirname(manifest_path)
        if os.path.exists(os.path.join(entity_dir, BS_RELATIVE_PATH)):
            out.append(os.path.basename(entity_dir))
    return sorted(out)


def main() -> None:
    data_version = datetime.now().strftime("%Y-%m-%d %H:%M")
    entities = _entities_with_sources()
    if not entities:
        raise SystemExit(
            "No balance sheet found — run scripts/performance/balance_sheet.py first."
        )
    print(f"Generating fake financing books for {len(entities)} entity(ies)…")

    for entity_id in entities:
        balance_sheet = _load(entity_id, BS_RELATIVE_PATH)
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
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "financing")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "loans.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):5d} records")

    print("Done.")


if __name__ == "__main__":
    main()
