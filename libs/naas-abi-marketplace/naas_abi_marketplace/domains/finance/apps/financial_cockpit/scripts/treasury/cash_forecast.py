#!/usr/bin/env python3
"""Generate the **fake** Cash Forecast demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    … → performance/cash_flow.py → pilotage/forecast.py → this script

Answers "will we have enough cash?". Where the Forecast page projects the year
in months, this projects it **week by week** — because a company can finish a
month comfortably and still run dry inside it, and the whole point of a cash
forecast is to surface that trough.

The monthly closing cash from ``pilotage/forecast.py`` is the anchor: each
month is cut into weeks whose net movements sum exactly to that month's change
in cash, so the weekly walk always lands on the monthly figure. Inside the
month, inflows and outflows follow a plausible rhythm — payroll and rent leave
early, customer collections arrive late.

Three scenarios (base / upside / downside) diverge progressively with the
horizon. One record per week per scenario.

Run from the app root (after the scripts above):
    python scripts/treasury/cash_forecast.py
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# web/data mirrors the R2 layout the Next.js app reads from.
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_ROOT = os.path.join(APP_ROOT, "web", "data")
ENTITIES_DIR = os.path.join(DATA_ROOT, "entities")

CF_PAGE_ID = "treasury"
CF_RELATIVE_PATH = "cash_forecast/cash_forecast.json"
FORECAST_RELATIVE_PATH = os.path.join("forecast", "forecast.json")
SCHEMA_VERSION = "1.0"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Last period-end with actuals — mirrors pilotage/forecast.py.
ACTUALS_THROUGH = "2026-07-31"

WEEKS_PER_MONTH = 4


@dataclass(frozen=True)
class ScenarioDef:
    key: str
    label: str
    is_base: bool
    # Multiplier on inflows and outflows, ramped in over the horizon.
    inflow_factor: float
    outflow_factor: float
    description: str


SCENARIOS = [
    ScenarioDef(
        "upside", "Upside", False, 1.06, 0.99,
        "Collections land early and spend holds to plan.",
    ),
    ScenarioDef("base", "Base", True, 1.0, 1.0, "The current cash forecast."),
    ScenarioDef(
        "downside", "Downside", False, 0.93, 1.045,
        "Customers pay late while costs run ahead of plan.",
    ),
]

# Share of a month's gross inflow landing in each of its four weeks —
# collections cluster after invoicing, late in the month.
INFLOW_RHYTHM = (0.18, 0.22, 0.27, 0.33)
# Outflows front-load: payroll and rent leave in the first half.
OUTFLOW_RHYTHM = (0.34, 0.28, 0.21, 0.17)

# Gross flows are larger than the net movement they produce: this multiplies
# the month's turnover to give realistic inflow/outflow magnitudes.
GROSS_TURNOVER = 2.6


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"cfc-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _monthly_cash(forecast: dict) -> list[tuple[str, str, str, float, bool]]:
    """``(period, scenario, year, closing cash, is_actual)`` from the forecast."""
    out = []
    for record in forecast.get("records", []):
        if record.get("metric") != "cash":
            continue
        value = (
            record["actual"] if record.get("actual") is not None else record["forecast"]
        )
        out.append(
            (
                record["period"],
                record["scenario"],
                record["scenario_year"],
                float(value),
                bool(record.get("is_actual")),
            )
        )
    return sorted(out)


def _week_ends(period: str) -> list[str]:
    """Four week-end dates inside the month ending on ``period``."""
    end = date.fromisoformat(period)
    first = end.replace(day=1)
    span = (end - first).days
    out = []
    for index in range(WEEKS_PER_MONTH):
        offset = round(span * (index + 1) / WEEKS_PER_MONTH)
        out.append((first + timedelta(days=offset)).isoformat())
    return out


def _build_records(entity_id: str, forecast: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    months = _monthly_cash(forecast)
    if not months:
        return []

    records: list[dict] = []
    horizon = 0

    for index, (period, scenario_id, scenario_year, closing, is_actual) in enumerate(
        months
    ):
        opening = months[index - 1][3] if index > 0 else closing * 0.985
        net_change = closing - opening
        if not is_actual:
            horizon += 1

        # Gross flows around the net movement: turnover scaled off the cash
        # level, then split so that inflow − outflow == net_change exactly.
        turnover = abs(opening) * GROSS_TURNOVER / 12.0 * rng.uniform(0.9, 1.1)
        gross_inflow = turnover + max(0.0, net_change)
        gross_outflow = gross_inflow - net_change

        week_ends = _week_ends(period)

        for definition in SCENARIOS:
            # Scenario divergence ramps in with the horizon: the near term is
            # nearly certain, the far term is not.
            ramp = 0.0 if is_actual else min(1.0, horizon / 6.0)
            inflow_factor = 1.0 + (definition.inflow_factor - 1.0) * ramp
            outflow_factor = 1.0 + (definition.outflow_factor - 1.0) * ramp

            balance = opening
            for week_index, week_end in enumerate(week_ends):
                inflow = (
                    gross_inflow
                    * INFLOW_RHYTHM[week_index]
                    * inflow_factor
                    * rng.uniform(0.94, 1.06)
                )
                outflow = (
                    gross_outflow
                    * OUTFLOW_RHYTHM[week_index]
                    * outflow_factor
                    * rng.uniform(0.94, 1.06)
                )
                balance += inflow - outflow

                records.append(
                    {
                        "period": period,
                        "scenario": scenario_id,
                        "scenario_year": scenario_year,
                        "organization_slug": entity_id,
                        "week": f"{period[:7]}-W{week_index + 1}",
                        "week_end": week_end,
                        "week_index": week_index + 1,
                        "case_key": definition.key,
                        "case_label": definition.label,
                        "is_base": definition.is_base,
                        "description": definition.description,
                        "is_actual": is_actual,
                        "inflow": round(inflow, 2),
                        "outflow": round(outflow, 2),
                        "net": round(inflow - outflow, 2),
                        "closing_cash": round(balance, 2),
                    }
                )

            # Re-anchor the base case on the monthly forecast so the weekly walk
            # never drifts away from the Forecast page's closing cash.
            if definition.is_base:
                drift = closing - balance
                for offset in range(WEEKS_PER_MONTH, 0, -1):
                    record = records[-offset]
                    share = (WEEKS_PER_MONTH - offset + 1) / WEEKS_PER_MONTH
                    record["closing_cash"] = round(
                        record["closing_cash"] + drift * share, 2
                    )
                    if offset == WEEKS_PER_MONTH:
                        record["net"] = round(
                            record["closing_cash"] - opening, 2
                        )
                    else:
                        previous = records[-offset - 1]["closing_cash"]
                        record["net"] = round(record["closing_cash"] - previous, 2)
                    record["inflow"] = round(
                        max(0.0, record["net"] + record["outflow"]), 2
                    )

    return records


def _scenarios_option_list(payload: dict, records: list[dict]) -> list[dict[str, str]]:
    """Reuse the upstream period options, or rebuild them from the records."""
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
        raise SystemExit("No forecast found — run scripts/pilotage/forecast.py first.")
    print(f"Generating fake cash forecasts for {len(entities)} entity(ies)…")

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
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "cash_forecast")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "cash_forecast.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):5d} records")

    print("Done.")


if __name__ == "__main__":
    main()
