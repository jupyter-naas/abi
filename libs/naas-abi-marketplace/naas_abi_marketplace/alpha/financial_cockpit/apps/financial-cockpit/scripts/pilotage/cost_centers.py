#!/usr/bin/env python3
"""Generate the **fake** Cost Centers demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/balance_sheet.py → performance/cash_flow.py → this script

Answers "which departments drive performance?". The departments are an
allocation of figures that already exist: each month's total cost base is read
from the cash flow's memo P&L (revenue − EBITDA) and split across cost centers
by fixed weights, and revenue is attributed only to the revenue-generating
ones. So the page's totals tie back to the Income Statement and Cash Flow
rather than being a fourth independent invention.

One record per cost center per month, carrying budget, actual, headcount and
the revenue / margin the center contributed.

Run from the app root (after the two scripts above):
    python scripts/pilotage/cost_centers.py
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

CC_PAGE_ID = "cost-centers"
CC_RELATIVE_PATH = "cost_centers/cost_centers.json"
CF_RELATIVE_PATH = os.path.join("cash_flow", "cash_flow.json")
SCHEMA_VERSION = "1.0"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@dataclass(frozen=True)
class CostCenterDef:
    key: str
    label: str
    division: str
    division_label: str
    # Share of the total monthly cost base.
    cost_weight: float
    # Share of revenue attributed to this center (0 for support functions).
    revenue_weight: float
    # Headcount at the start of the horizon, and monthly growth.
    headcount_start: int
    headcount_growth: float


COST_CENTERS = [
    CostCenterDef("sales", "Sales", "commercial", "Commercial", 0.155, 0.42, 34, 0.0075),
    CostCenterDef("marketing", "Marketing", "commercial", "Commercial", 0.085, 0.14, 16, 0.005),
    CostCenterDef(
        "customer_success", "Customer Success", "commercial", "Commercial",
        0.070, 0.12, 18, 0.006,
    ),
    CostCenterDef("engineering", "Engineering", "product", "Product & Technology", 0.235, 0.20, 62, 0.008),
    CostCenterDef("product", "Product", "product", "Product & Technology", 0.075, 0.08, 14, 0.006),
    CostCenterDef("infrastructure", "Infrastructure", "product", "Product & Technology", 0.095, 0.04, 9, 0.004),
    CostCenterDef("operations", "Operations", "operations", "Operations", 0.115, 0.0, 27, 0.003),
    CostCenterDef("supply_chain", "Supply Chain", "operations", "Operations", 0.065, 0.0, 12, 0.002),
    CostCenterDef("finance", "Finance", "corporate", "Corporate", 0.048, 0.0, 11, 0.002),
    CostCenterDef("people", "People & Culture", "corporate", "Corporate", 0.032, 0.0, 7, 0.003),
    CostCenterDef("legal", "Legal & Compliance", "corporate", "Corporate", 0.025, 0.0, 5, 0.001),

]



def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"cc-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _monthly_pnl(cash_flow: dict) -> list[tuple[str, str, str, float, float]]:
    """``(period, scenario, year, revenue, ebitda)`` from the cash flow memo P&L."""
    periods: dict[str, tuple[str, str]] = {}
    values: dict[str, dict[str, float]] = {}
    for record in cash_flow.get("records", []):
        if record.get("activity") != "memo":
            continue
        category = record.get("category")
        if category not in ("Revenue", "EBITDA"):
            continue
        period = record["period"]
        periods[period] = (record["scenario"], record["scenario_year"])
        values.setdefault(period, {})[category] = float(record["amount"])

    out = []
    for period in sorted(periods):
        scenario, year = periods[period]
        bucket = values[period]
        out.append(
            (period, scenario, year, bucket.get("Revenue", 0.0), bucket.get("EBITDA", 0.0))
        )
    return out


def _build_records(entity_id: str, cash_flow: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    months = _monthly_pnl(cash_flow)

    # Normalize the declared weights so the allocation is exhaustive.
    cost_total = sum(center.cost_weight for center in COST_CENTERS)
    revenue_total = sum(center.revenue_weight for center in COST_CENTERS)

    # A per-center budgeting bias, fixed for the whole horizon: some teams
    # habitually overspend their budget, others come in under. Budget is
    # divided by this, so a bias below 1.0 means the center runs over. The
    # range is skewed low on purpose — a portfolio whose variances cancel to
    # zero would make the headline Variance KPI meaningless.
    bias = {center.key: rng.uniform(0.90, 1.02) for center in COST_CENTERS}

    records: list[dict] = []
    for index, (period, scenario, scenario_year, revenue, ebitda) in enumerate(months):
        cost_base = max(0.0, revenue - ebitda)

        for center in COST_CENTERS:
            share = center.cost_weight / cost_total
            actual = cost_base * share * rng.uniform(0.94, 1.06)
            # Budget is the smooth plan; actual is what happened against it.
            budget = cost_base * share * bias[center.key] * rng.uniform(0.98, 1.02)

            headcount = max(
                1,
                round(
                    center.headcount_start * (1.0 + center.headcount_growth) ** index
                ),
            )

            if revenue_total > 0 and center.revenue_weight > 0:
                contribution = (
                    revenue * (center.revenue_weight / revenue_total)
                    * rng.uniform(0.96, 1.04)
                )
            else:
                # Support functions generate no revenue of their own.
                contribution = 0.0

            # Attributed revenue less the center's own cost. Summed across every
            # center this reconciles to EBITDA (revenue − total cost base), so
            # the page ties back to the income statement rather than drifting.
            margin_contribution = contribution - actual

            records.append(
                {
                    "period": period,
                    "scenario": scenario,
                    "scenario_year": scenario_year,
                    "organization_slug": entity_id,
                    "cost_center": center.key,
                    "cost_center_label": center.label,
                    "division": center.division,
                    "division_label": center.division_label,
                    "budget": round(budget, 2),
                    "actual": round(actual, 2),
                    "headcount": headcount,
                    "revenue_contribution": round(contribution, 2),
                    "margin_contribution": round(margin_contribution, 2),
                }
            )

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
    pages[CC_PAGE_ID] = [CC_RELATIVE_PATH]
    manifest["data_version"] = data_version
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entities_with_sources() -> list[str]:
    out: list[str] = []
    for manifest_path in glob.glob(os.path.join(ENTITIES_DIR, "*", "manifest.json")):
        entity_dir = os.path.dirname(manifest_path)
        if os.path.exists(os.path.join(entity_dir, CF_RELATIVE_PATH)):
            out.append(os.path.basename(entity_dir))
    return sorted(out)


def main() -> None:
    data_version = datetime.now().strftime("%Y-%m-%d %H:%M")
    entities = _entities_with_sources()
    if not entities:
        raise SystemExit(
            "No cash flow found — run scripts/performance/balance_sheet.py then "
            "scripts/performance/cash_flow.py first."
        )
    print(f"Generating fake cost centers for {len(entities)} entity(ies)…")

    for entity_id in entities:
        cash_flow = _load(entity_id, CF_RELATIVE_PATH)
        if cash_flow is None:
            continue
        records = _build_records(entity_id, cash_flow)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "data_version": data_version,
            "entity_id": entity_id,
            "scenarios": _scenarios(cash_flow, records),
            "records": records,
        }
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "cost_centers")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "cost_centers.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):5d} records")

    print("Done.")


if __name__ == "__main__":
    main()
