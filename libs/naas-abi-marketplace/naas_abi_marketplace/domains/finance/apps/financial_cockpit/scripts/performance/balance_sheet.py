#!/usr/bin/env python3
"""Generate the **fake** Balance Sheet demo dataset for Financial Cockpit.

The template ships no upstream balance-sheet source, so this standalone script
(no ABI runtime dependency — plain stdlib) fabricates a self-consistent balance
sheet for the bundled ``_demo`` entity and wires it into the manifest.

It emits monthly period-end snapshots (Jan 2023 → Dec 2026) whose Assets always
equal Equity + Liabilities (Reserves is the balancing plug), so the
"Assets vs Liabilities" view balances exactly. Amounts are deterministic
(seeded RNG) so re-running is stable. The record shape mirrors the P&L actuals
dataset (``scenario`` / ``scenario_year`` drive the portal's period picker).

Run from the app root:
    python scripts/performance/balance_sheet.py
"""

from __future__ import annotations

import calendar
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

BS_PAGE_ID = "balance-sheet"
BS_RELATIVE_PATH = "balance_sheet/balance_sheet.json"
SCHEMA_VERSION = "1.0"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

START_YEAR = 2023
END_YEAR = 2026


@dataclass(frozen=True)
class LineDef:
    section: str  # "assets" | "equity_liabilities"
    group: str
    group_label: str
    category: str
    is_cash: bool = False
    is_debt: bool = False
    is_current: bool = False


# Balance sheet skeleton — order drives table rendering.
ASSET_LINES = [
    LineDef("assets", "non_current_assets", "Non-current assets", "Intangible assets"),
    LineDef("assets", "non_current_assets", "Non-current assets", "Property, plant & equipment"),
    LineDef("assets", "non_current_assets", "Non-current assets", "Financial assets"),
    LineDef("assets", "current_assets", "Current assets", "Inventory", is_current=True),
    LineDef("assets", "current_assets", "Current assets", "Trade receivables", is_current=True),
    LineDef("assets", "current_assets", "Current assets", "Other receivables", is_current=True),
    LineDef(
        "assets", "current_assets", "Current assets", "Cash & equivalents",
        is_cash=True, is_current=True,
    ),
]

# Non-equity liabilities — generated independently; equity then balances.
LIABILITY_LINES = [
    LineDef(
        "equity_liabilities", "non_current_liabilities", "Non-current liabilities",
        "Long-term borrowings", is_debt=True,
    ),
    LineDef(
        "equity_liabilities", "current_liabilities", "Current liabilities",
        "Trade payables", is_current=True,
    ),
    LineDef(
        "equity_liabilities", "current_liabilities", "Current liabilities",
        "Tax & social liabilities", is_current=True,
    ),
    LineDef(
        "equity_liabilities", "current_liabilities", "Current liabilities",
        "Short-term borrowings", is_debt=True, is_current=True,
    ),
]

EQUITY_GROUP = ("equity", "Equity")


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(entity_id.encode()).digest()[:4], "big")


def _months() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for year in range(START_YEAR, END_YEAR + 1):
        for month in range(1, 13):
            last = calendar.monthrange(year, month)[1]
            out.append((f"{year}-{month:02d}-{last:02d}", f"{year}-{month:02d}", str(year)))
    return out


def _scenarios(months: list[tuple[str, str, str]]) -> list[dict[str, str]]:
    years = sorted({y for _, _, y in months})
    options: list[dict[str, str]] = [
        {"id": y, "label": y, "split": "date_year"} for y in reversed(years)
    ]
    for _, scenario_month, _ in reversed(months):
        year_part, _, month_part = scenario_month.partition("-")
        label = f"{MONTH_LABELS[int(month_part)]} {year_part}"
        options.append({"id": scenario_month, "label": label, "split": "date_month"})
    return options


def _build_records(entity_id: str) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    unit = 1_000_000.0 * rng.uniform(6.0, 12.0)  # base magnitude in EUR

    fixed_base = unit * rng.uniform(0.9, 1.6)
    incorp_w = 0.12
    corp_w = rng.uniform(0.62, 0.74)
    fin_w = 1.0 - incorp_w - corp_w
    stocks_w = rng.uniform(0.02, 0.10)
    recv_w = rng.uniform(0.18, 0.32)
    other_recv_w = rng.uniform(0.04, 0.10)
    cash_w = rng.uniform(0.10, 0.22)
    capital = round(unit * rng.uniform(0.15, 0.35), 2)
    debt_lt_start = unit * rng.uniform(0.35, 0.75)
    payables_w = rng.uniform(0.10, 0.20)
    tax_w = rng.uniform(0.05, 0.12)

    records: list[dict] = []
    months = _months()
    n = len(months)
    for t, (period, scenario_month, scenario_year) in enumerate(months):
        growth = (1.0 + 0.010) ** t
        noise = lambda: rng.uniform(0.96, 1.04)  # noqa: E731
        current_base = unit * growth

        fixed = fixed_base * (1.0 + 0.004 * t)
        asset_values = {
            "Intangible assets": fixed * incorp_w * noise(),
            "Property, plant & equipment": fixed * corp_w * noise(),
            "Financial assets": fixed * fin_w * noise(),
            "Inventory": current_base * stocks_w * noise(),
            "Trade receivables": current_base * recv_w * noise(),
            "Other receivables": current_base * other_recv_w * noise(),
            "Cash & equivalents": current_base * cash_w * (1.0 + 0.006 * t) * noise(),
        }
        total_assets = sum(asset_values.values())

        debt_lt = max(0.0, debt_lt_start * (1.0 - 0.010 * t)) * noise()
        liab_values = {
            "Long-term borrowings": debt_lt,
            "Trade payables": current_base * payables_w * noise(),
            "Tax & social liabilities": current_base * tax_w * noise(),
            "Short-term borrowings": current_base * rng.uniform(0.01, 0.05) * noise(),
        }
        total_liabilities = sum(liab_values.values())

        equity_total = total_assets - total_liabilities
        result = current_base * rng.uniform(0.02, 0.06) * (0.5 + t / n)
        reserves = equity_total - capital - result  # plug so Assets == Equity + Liab
        equity_values = {
            "Share capital": capital,
            "Reserves": reserves,
            "Net income for the year": result,
        }

        def emit(line: LineDef, amount: float) -> None:
            records.append(
                {
                    "period": period,
                    "scenario": scenario_month,
                    "scenario_year": scenario_year,
                    "organization_slug": entity_id,
                    "section": line.section,
                    "group": line.group,
                    "group_label": line.group_label,
                    "category": line.category,
                    "amount": round(amount, 2),
                    "is_cash": line.is_cash,
                    "is_debt": line.is_debt,
                    "is_current": line.is_current,
                }
            )

        for line in ASSET_LINES:
            emit(line, asset_values[line.category])
        for cat, amount in equity_values.items():
            emit(LineDef("equity_liabilities", EQUITY_GROUP[0], EQUITY_GROUP[1], cat), amount)
        for line in LIABILITY_LINES:
            emit(line, liab_values[line.category])

    return records


def _patch_manifest(entity_id: str, data_version: str) -> None:
    path = os.path.join(ENTITIES_DIR, entity_id, "manifest.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    pages = manifest.setdefault("datasets", {}).setdefault("pages", {})
    pages[BS_PAGE_ID] = [BS_RELATIVE_PATH]
    manifest["data_version"] = data_version
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entities_with_pnl() -> list[str]:
    out: list[str] = []
    for mf in glob.glob(os.path.join(ENTITIES_DIR, "*", "manifest.json")):
        with open(mf, encoding="utf-8") as handle:
            manifest = json.load(handle)
        if "pnl" in manifest.get("datasets", {}).get("pages", {}):
            out.append(os.path.basename(os.path.dirname(mf)))
    return sorted(out)


def main() -> None:
    data_version = datetime.now().strftime("%Y-%m-%d %H:%M")
    entities = _entities_with_pnl()
    print(f"Generating fake balance sheets for {len(entities)} entity(ies)…")

    months = _months()
    scenarios = _scenarios(months)
    for entity_id in entities:
        records = _build_records(entity_id)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "data_version": data_version,
            "entity_id": entity_id,
            "scenarios": scenarios,
            "records": records,
        }
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "balance_sheet")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "balance_sheet.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):5d} records")

    print("Done.")


if __name__ == "__main__":
    main()
