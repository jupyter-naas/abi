#!/usr/bin/env python3
"""Generate the **fake** Scenario Analysis demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    … → performance/cash_flow.py → pilotage/forecast.py → this script

Answers "what happens if assumptions change?". The **base case is the forecast**
— this script reads the full-year forecast totals and perturbs them through a
set of named business drivers, so the Base scenario on this page equals the
headline figure on the Forecast page rather than a second, unrelated invention.

Four record kinds share the dataset, discriminated by ``kind``:

* ``scenario``   — one per what-if case (Base, Upside, Downside, Severe) with
  its probability and resulting revenue / EBITDA / cash / margin;
* ``driver``     — per-driver low and high EBITDA impact, for the tornado;
* ``sensitivity``— a grid of two drivers crossed, for the matrix;
* ``assumption`` — each driver's value under each scenario, for the table.

Records are emitted as a monthly snapshot (the analysis "as of" that month
targeting its year end), so the section reads the latest period in whatever
scenario window is selected — the same as-of pattern the balance sheet uses.

Run from the app root (after the scripts above):
    python scripts/pilotage/scenario_analysis.py
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

SA_PAGE_ID = "scenario-analysis"
SA_RELATIVE_PATH = "scenario_analysis/scenario_analysis.json"
FORECAST_RELATIVE_PATH = os.path.join("forecast", "forecast.json")
SCHEMA_VERSION = "1.0"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@dataclass(frozen=True)
class ScenarioDef:
    key: str
    label: str
    probability: float
    # Multiplier applied to base revenue, and to the cost base.
    revenue_factor: float
    cost_factor: float
    description: str


SCENARIOS = [
    ScenarioDef(
        "upside", "Upside", 0.20, 1.085, 0.985,
        "Demand holds above plan and input costs ease.",
    ),
    ScenarioDef(
        "base", "Base", 0.50, 1.0, 1.0,
        "The current forecast, carried through unchanged.",
    ),
    ScenarioDef(
        "downside", "Downside", 0.22, 0.925, 1.035,
        "Softer demand with cost inflation running ahead of pricing.",
    ),
    ScenarioDef(
        "severe", "Severe", 0.08, 0.845, 1.075,
        "Demand shock combined with a sustained input-cost spike.",
    ),
]


@dataclass(frozen=True)
class DriverDef:
    key: str
    label: str
    unit: str  # "percent" | "currency" | "ratio"
    base: float
    low: float
    high: float
    # EBITDA sensitivity: euros of EBITDA per unit of driver deviation from base.
    elasticity: float
    hint: str


# Ordered loosely by expected impact; the tornado re-sorts by magnitude.
DRIVERS = [
    DriverDef(
        "volume", "Sales volume", "percent", 0.0, -0.12, 0.10, 1.0,
        "Units sold versus plan.",
    ),
    DriverDef(
        "price", "Average selling price", "percent", 0.0, -0.06, 0.05, 1.55,
        "Realized price versus plan, net of discounts.",
    ),
    DriverDef(
        "input_costs", "Input costs", "percent", 0.0, -0.05, 0.09, -0.80,
        "Purchase cost of goods and materials.",
    ),
    DriverDef(
        "payroll", "Payroll inflation", "percent", 0.03, 0.01, 0.07, -0.62,
        "Wage drift across the workforce.",
    ),
    DriverDef(
        "churn", "Customer churn", "percent", 0.08, 0.05, 0.14, -0.45,
        "Annual revenue lost to departing customers.",
    ),
    DriverDef(
        "fx", "EUR / USD rate", "ratio", 1.08, 1.02, 1.16, 0.28,
        "Translation effect on non-euro revenue.",
    ),
]

# The two drivers crossed in the sensitivity matrix.
MATRIX_ROW = "volume"
MATRIX_COL = "input_costs"
MATRIX_STEPS = 5


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"sa-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _base_case_by_year(forecast: dict) -> dict[str, dict[str, float]]:
    """Full-year expected outcome per year: actual where known, else forecast."""
    out: dict[str, dict[str, float]] = {}
    latest_cash: dict[str, tuple[str, float]] = {}

    for record in forecast.get("records", []):
        year = record["scenario_year"]
        metric = record["metric"]
        value = (
            record["actual"]
            if record.get("actual") is not None
            else record["forecast"]
        )
        bucket = out.setdefault(year, {"revenue": 0.0, "ebitda": 0.0, "cash": 0.0})
        if metric in ("revenue", "ebitda"):
            # Flows accumulate across the year.
            bucket[metric] += float(value)
        elif metric == "cash":
            # A stock: keep the closing level of the last month in the year.
            period = record["period"]
            if year not in latest_cash or period > latest_cash[year][0]:
                latest_cash[year] = (period, float(value))

    for year, (_, cash) in latest_cash.items():
        out.setdefault(year, {"revenue": 0.0, "ebitda": 0.0, "cash": 0.0})
        out[year]["cash"] = cash
    for bucket in out.values():
        bucket["margin"] = (
            bucket["ebitda"] / bucket["revenue"] if bucket["revenue"] > 0 else 0.0
        )
    return out


def _periods(forecast: dict) -> list[tuple[str, str, str]]:
    seen: dict[str, tuple[str, str]] = {}
    for record in forecast.get("records", []):
        seen[record["period"]] = (record["scenario"], record["scenario_year"])
    return [(period, *seen[period]) for period in sorted(seen)]


def _outcome(base: dict[str, float], scenario: ScenarioDef) -> dict[str, float]:
    """Apply a scenario's revenue and cost factors to the base case."""
    revenue = base["revenue"] * scenario.revenue_factor
    # Costs are what is left of revenue after EBITDA in the base case.
    base_costs = base["revenue"] - base["ebitda"]
    ebitda = revenue - base_costs * scenario.cost_factor
    # Cash moves with the EBITDA delta, damped — not every euro converts.
    cash = base["cash"] + (ebitda - base["ebitda"]) * 0.72
    return {
        "revenue": revenue,
        "ebitda": ebitda,
        "cash": cash,
        "margin": ebitda / revenue if revenue > 0 else 0.0,
    }


def _build_records(entity_id: str, forecast: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    base_by_year = _base_case_by_year(forecast)
    row_driver = next(d for d in DRIVERS if d.key == MATRIX_ROW)
    col_driver = next(d for d in DRIVERS if d.key == MATRIX_COL)

    records: list[dict] = []
    for period, scenario_id, scenario_year in _periods(forecast):
        base = base_by_year.get(scenario_year)
        if not base or base["revenue"] <= 0:
            continue

        def emit(kind: str, **fields: object) -> None:
            records.append(
                {
                    "period": period,
                    "scenario": scenario_id,
                    "scenario_year": scenario_year,
                    "organization_slug": entity_id,
                    "kind": kind,
                    **fields,
                }
            )

        # --- scenarios ------------------------------------------------------
        for definition in SCENARIOS:
            outcome = _outcome(base, definition)
            emit(
                "scenario",
                scenario_key=definition.key,
                scenario_label=definition.label,
                probability=definition.probability,
                is_base=definition.key == "base",
                description=definition.description,
                revenue=round(outcome["revenue"], 2),
                ebitda=round(outcome["ebitda"], 2),
                cash=round(outcome["cash"], 2),
                margin=round(outcome["margin"], 6),
            )

        # --- drivers (tornado) ---------------------------------------------
        # Impact = deviation from base × elasticity × base revenue.
        for driver in DRIVERS:
            low_impact = (driver.low - driver.base) * driver.elasticity * base["revenue"]
            high_impact = (
                (driver.high - driver.base) * driver.elasticity * base["revenue"]
            )
            emit(
                "driver",
                driver_key=driver.key,
                driver_label=driver.label,
                unit=driver.unit,
                base_value=driver.base,
                low_value=driver.low,
                high_value=driver.high,
                low_impact=round(low_impact, 2),
                high_impact=round(high_impact, 2),
                hint=driver.hint,
            )

        # --- sensitivity matrix --------------------------------------------
        for row_index in range(MATRIX_STEPS):
            row_value = row_driver.low + (row_driver.high - row_driver.low) * (
                row_index / (MATRIX_STEPS - 1)
            )
            for col_index in range(MATRIX_STEPS):
                col_value = col_driver.low + (col_driver.high - col_driver.low) * (
                    col_index / (MATRIX_STEPS - 1)
                )
                ebitda = (
                    base["ebitda"]
                    + (row_value - row_driver.base)
                    * row_driver.elasticity
                    * base["revenue"]
                    + (col_value - col_driver.base)
                    * col_driver.elasticity
                    * base["revenue"]
                )
                emit(
                    "sensitivity",
                    row_key=row_driver.key,
                    row_label=row_driver.label,
                    row_unit=row_driver.unit,
                    row_value=round(row_value, 6),
                    col_key=col_driver.key,
                    col_label=col_driver.label,
                    col_unit=col_driver.unit,
                    col_value=round(col_value, 6),
                    ebitda=round(ebitda, 2),
                )

        # --- assumptions table ----------------------------------------------
        for driver in DRIVERS:
            for definition in SCENARIOS:
                if definition.key == "base":
                    value = driver.base
                else:
                    # Place each scenario along the driver's range, with a
                    # little seeded jitter so the table is not perfectly linear.
                    span = (
                        driver.high - driver.base
                        if definition.revenue_factor >= 1.0
                        else driver.low - driver.base
                    )
                    weight = abs(definition.revenue_factor - 1.0) / 0.155
                    value = driver.base + span * min(1.0, weight) * rng.uniform(
                        0.88, 1.0
                    )
                emit(
                    "assumption",
                    driver_key=driver.key,
                    driver_label=driver.label,
                    unit=driver.unit,
                    scenario_key=definition.key,
                    scenario_label=definition.label,
                    value=round(value, 6),
                    hint=driver.hint,
                )

    return records


def _scenarios_option_list(payload: dict, records: list[dict]) -> list[dict[str, str]]:
    """Reuse the upstream period picker options, or rebuild from the records."""
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
    pages[SA_PAGE_ID] = [SA_RELATIVE_PATH]
    manifest["data_version"] = data_version
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entities_with_sources() -> list[str]:
    out: list[str] = []
    for manifest_path in glob.glob(os.path.join(ENTITIES_DIR, "*", "manifest.json")):
        entity_dir = os.path.dirname(manifest_path)
        if os.path.exists(os.path.join(entity_dir, FORECAST_RELATIVE_PATH)):
            out.append(os.path.basename(entity_dir))
    return sorted(out)


def main() -> None:
    data_version = datetime.now().strftime("%Y-%m-%d %H:%M")
    entities = _entities_with_sources()
    if not entities:
        raise SystemExit(
            "No forecast found — run scripts/pilotage/forecast.py first."
        )
    print(f"Generating fake scenario analyses for {len(entities)} entity(ies)…")

    for entity_id in entities:
        forecast = _load(entity_id, FORECAST_RELATIVE_PATH)
        if forecast is None:
            continue
        records = _build_records(entity_id, forecast)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "data_version": data_version,
            "entity_id": entity_id,
            "scenarios": _scenarios_option_list(forecast, records),
            "records": records,
        }
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "scenario_analysis")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "scenario_analysis.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):5d} records")

    print("Done.")


if __name__ == "__main__":
    main()
