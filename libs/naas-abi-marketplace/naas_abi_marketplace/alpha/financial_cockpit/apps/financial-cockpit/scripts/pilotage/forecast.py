#!/usr/bin/env python3
"""Generate the **fake** Forecast demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/balance_sheet.py → performance/cash_flow.py → this script

Answers "where will we finish the year?", so the dataset has to contain both a
closed past and an open future. ``ACTUALS_THROUGH`` splits the timeline:

* months up to it carry an ``actual`` (read from the cash flow's memo P&L and
  the balance sheet's cash line) **and** the ``forecast`` that was standing at
  the time — the gap between the two is what makes Forecast Accuracy real
  rather than invented;
* months after it carry a ``forecast`` only, extrapolated from the trailing
  trend, with a confidence band that widens with the horizon.

Every month also carries the ``budget`` originally set for the year, so the
page can show forecast-vs-budget variance. Four metrics are emitted: revenue,
EBITDA and cash in euros, plus margin as a rate.

Run from the app root (after the two scripts above):
    python scripts/pilotage/forecast.py
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

FORECAST_PAGE_ID = "forecast"
FORECAST_RELATIVE_PATH = "forecast/forecast.json"
BS_RELATIVE_PATH = os.path.join("balance_sheet", "balance_sheet.json")
CF_RELATIVE_PATH = os.path.join("cash_flow", "cash_flow.json")
SCHEMA_VERSION = "1.0"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

CASH_LINE = "Cash & equivalents"

# Last period-end with actuals. Later months are forecast-only.
ACTUALS_THROUGH = "2026-07-31"

# How many trailing months feed the extrapolation of a forecast month.
TREND_WINDOW = 6
# Half-width of the confidence band at horizon 1, and how much it widens per
# additional month ahead.
BAND_BASE = 0.035
BAND_PER_MONTH = 0.022


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    unit: str  # "currency" | "percent"
    # A stock (cash) carries its level forward; a flow accumulates over a year.
    is_stock: bool = False


METRICS = [
    MetricDef("revenue", "Revenue", "currency"),
    MetricDef("ebitda", "EBITDA", "currency"),
    MetricDef("cash", "Cash", "currency", is_stock=True),
    MetricDef("margin", "EBITDA Margin", "percent"),
]


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"fc-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _actual_series(
    balance_sheet: dict, cash_flow: dict
) -> tuple[list[tuple[str, str, str]], dict[str, dict[str, float]]]:
    """Monthly actuals per metric, keyed by period-end."""
    periods: dict[str, tuple[str, str]] = {}
    values: dict[str, dict[str, float]] = {}

    for record in cash_flow.get("records", []):
        if record.get("activity") != "memo":
            continue
        period = record["period"]
        periods[period] = (record["scenario"], record["scenario_year"])
        bucket = values.setdefault(period, {})
        if record["category"] == "Revenue":
            bucket["revenue"] = float(record["amount"])
        elif record["category"] == "EBITDA":
            bucket["ebitda"] = float(record["amount"])

    for record in balance_sheet.get("records", []):
        if record.get("category") != CASH_LINE:
            continue
        period = record["period"]
        periods.setdefault(period, (record["scenario"], record["scenario_year"]))
        values.setdefault(period, {})["cash"] = float(record["amount"])

    for bucket in values.values():
        revenue = bucket.get("revenue", 0.0)
        bucket["margin"] = bucket.get("ebitda", 0.0) / revenue if revenue > 0 else 0.0

    ordered = [(period, *periods[period]) for period in sorted(periods)]
    return ordered, values


def _extrapolate(history: list[float], metric: MetricDef, step: int) -> float:
    """Project one month ahead from the trailing window."""
    window = history[-TREND_WINDOW:] or [0.0]
    average = sum(window) / len(window)
    if metric.is_stock or metric.unit == "percent":
        # Levels and rates drift from the latest observation, not the mean.
        latest = history[-1] if history else average
        if len(window) >= 2:
            drift = (window[-1] - window[0]) / max(1, len(window) - 1)
        else:
            drift = 0.0
        return latest + drift * step
    if len(window) >= 2:
        drift = (window[-1] - window[0]) / max(1, len(window) - 1)
    else:
        drift = 0.0
    return average + drift * step


def _build_records(entity_id: str, balance_sheet: dict, cash_flow: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    ordered, actuals = _actual_series(balance_sheet, cash_flow)

    # Budget is set once per year, as the year's actual total nudged by a
    # planning error — so budget variance is neither zero nor absurd.
    budget_bias = {
        year: rng.uniform(0.92, 1.06)
        for year in sorted({scenario_year for _, _, scenario_year in ordered})
    }

    records: list[dict] = []
    # Running history per metric, used to extrapolate the forecast months.
    history: dict[str, list[float]] = {metric.key: [] for metric in METRICS}
    horizon = 0

    for period, scenario, scenario_year in ordered:
        is_actual = period <= ACTUALS_THROUGH
        if not is_actual:
            horizon += 1

        for metric in METRICS:
            actual = actuals.get(period, {}).get(metric.key)

            if is_actual and actual is not None:
                # The forecast standing at the time missed by a small margin.
                error = rng.uniform(-0.055, 0.055)
                forecast = actual * (1.0 + error)
                history[metric.key].append(actual)
                band = abs(actual) * BAND_BASE
                low, high = forecast - band, forecast + band
            else:
                forecast = _extrapolate(history[metric.key], metric, horizon)
                forecast *= 1.0 + rng.uniform(-0.012, 0.012)
                history[metric.key].append(forecast)
                spread = BAND_BASE + BAND_PER_MONTH * horizon
                band = abs(forecast) * spread
                low, high = forecast - band, forecast + band
                actual = None

            budget = (
                (actual if actual is not None else forecast)
                * budget_bias[scenario_year]
                * (1.0 + rng.uniform(-0.02, 0.02))
            )

            digits = 6 if metric.unit == "percent" else 2
            records.append(
                {
                    "period": period,
                    "scenario": scenario,
                    "scenario_year": scenario_year,
                    "organization_slug": entity_id,
                    "metric": metric.key,
                    "metric_label": metric.label,
                    "unit": metric.unit,
                    "is_stock": metric.is_stock,
                    "is_actual": is_actual,
                    "actual": round(actual, digits) if actual is not None else None,
                    "forecast": round(forecast, digits),
                    "budget": round(budget, digits),
                    "low": round(low, digits),
                    "high": round(high, digits),
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
    pages[FORECAST_PAGE_ID] = [FORECAST_RELATIVE_PATH]
    manifest["data_version"] = data_version
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entities_with_sources() -> list[str]:
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
    print(f"Generating fake forecasts for {len(entities)} entity(ies)…")

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
            "scenarios": _scenarios(cash_flow, records),
            "records": records,
        }
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "forecast")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "forecast.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):5d} records")

    print("Done.")


if __name__ == "__main__":
    main()
