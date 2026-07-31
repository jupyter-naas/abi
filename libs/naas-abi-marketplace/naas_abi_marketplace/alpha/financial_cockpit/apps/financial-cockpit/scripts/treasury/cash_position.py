#!/usr/bin/env python3
"""Generate the **fake** Cash Position demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/balance_sheet.py → this script

Answers "how much cash is available today?". The balance sheet already states
how much cash exists each month; this script only decides **where it sits** —
splitting that one line across bank accounts by fixed weights, so the accounts
always sum back to the balance sheet's "Cash & equivalents".

Each account carries a bank, a country and a currency (balances are reported in
EUR either way), plus the share of its balance that is restricted — pledged as
collateral, held against a guarantee, or otherwise not spendable today. The
page's Available Cash is the balance net of that.

One record per account per month.

Run from the app root (after performance/balance_sheet.py):
    python scripts/treasury/cash_position.py
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

CP_PAGE_ID = "cash-position"
CP_RELATIVE_PATH = "cash_position/bank_accounts.json"
BS_RELATIVE_PATH = os.path.join("balance_sheet", "balance_sheet.json")
SCHEMA_VERSION = "1.0"

CASH_LINE = "Cash & equivalents"
SHORT_TERM_DEBT_LINE = "Short-term borrowings"

# Memo records carry context the accounts themselves cannot: the short-term debt
# the cash is measured against. `account_type: "memo"` keeps them out of the
# accounts table while the Net Cash KPI reads them.
MEMO_TYPE = "memo"
MEMO_SHORT_TERM_DEBT = "_short_term_debt"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@dataclass(frozen=True)
class AccountDef:
    key: str
    label: str
    bank: str
    account_type: str  # "current" | "savings" | "escrow" | "term_deposit"
    country: str
    country_label: str
    currency: str
    # Share of total cash held in this account.
    weight: float
    # Share of *this account's* balance that is not spendable today.
    restricted_share: float


ACCOUNTS = [
    AccountDef(
        "bnp_main", "Main operating account", "BNP Paribas", "current",
        "FR", "France", "EUR", 0.265, 0.0,
    ),
    AccountDef(
        "bnp_payroll", "Payroll account", "BNP Paribas", "current",
        "FR", "France", "EUR", 0.105, 0.0,
    ),
    AccountDef(
        "sg_collections", "Collections account", "Société Générale", "current",
        "FR", "France", "EUR", 0.130, 0.0,
    ),
    AccountDef(
        "sg_escrow", "Escrow — property deposits", "Société Générale", "escrow",
        "FR", "France", "EUR", 0.075, 1.0,
    ),
    AccountDef(
        "hsbc_uk", "UK operations", "HSBC", "current",
        "GB", "United Kingdom", "GBP", 0.095, 0.0,
    ),
    AccountDef(
        "hsbc_term", "Term deposit 12M", "HSBC", "term_deposit",
        "GB", "United Kingdom", "EUR", 0.115, 0.60,
    ),
    AccountDef(
        "ing_be", "Benelux operations", "ING", "current",
        "BE", "Belgium", "EUR", 0.070, 0.0,
    ),
    AccountDef(
        "revolut_cards", "Card & expenses float", "Revolut", "current",
        "LT", "Lithuania", "EUR", 0.035, 0.0,
    ),
    AccountDef(
        "bbva_es", "Iberia operations", "BBVA", "current",
        "ES", "Spain", "EUR", 0.060, 0.0,
    ),
    AccountDef(
        "bnp_reserve", "Guarantee reserve", "BNP Paribas", "savings",
        "FR", "France", "EUR", 0.050, 1.0,
    ),
]


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"cp-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _cash_by_period(balance_sheet: dict) -> list[tuple[str, str, str, float, float]]:
    """``(period, scenario, year, cash, short-term debt)`` from the balance sheet."""
    periods: dict[str, tuple[str, str]] = {}
    cash: dict[str, float] = {}
    debt: dict[str, float] = {}
    for record in balance_sheet.get("records", []):
        category = record.get("category")
        if category not in (CASH_LINE, SHORT_TERM_DEBT_LINE):
            continue
        period = record["period"]
        periods[period] = (record["scenario"], record["scenario_year"])
        target = cash if category == CASH_LINE else debt
        target[period] = target.get(period, 0.0) + float(record["amount"])
    return [
        (period, *periods[period], cash.get(period, 0.0), debt.get(period, 0.0))
        for period in sorted(periods)
    ]


def _build_records(entity_id: str, balance_sheet: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    periods = _cash_by_period(balance_sheet)

    # Fixed per-account IBAN-ish reference, stable across the horizon.
    references = {
        account.key: f"{account.country}{rng.randint(10, 99)} •••• "
        f"{rng.randint(1000, 9999)}"
        for account in ACCOUNTS
    }

    records: list[dict] = []
    previous_balances: dict[str, float] = {}

    for period, scenario, scenario_year, total_cash, short_term_debt in periods:
        # Jitter the weights each month, then renormalize so the accounts still
        # sum exactly to the balance sheet's cash line.
        jittered = {
            account.key: account.weight * rng.uniform(0.90, 1.10)
            for account in ACCOUNTS
        }
        weight_total = sum(jittered.values())

        for account in ACCOUNTS:
            balance = total_cash * (jittered[account.key] / weight_total)
            restricted = balance * account.restricted_share
            # Movement since last month — drives the Daily Cash Flow KPI.
            previous = previous_balances.get(account.key)
            movement = balance - previous if previous is not None else 0.0
            previous_balances[account.key] = balance

            records.append(
                {
                    "period": period,
                    "scenario": scenario,
                    "scenario_year": scenario_year,
                    "organization_slug": entity_id,
                    "account": account.key,
                    "account_label": account.label,
                    "bank": account.bank,
                    "account_type": account.account_type,
                    "country": account.country,
                    "country_label": account.country_label,
                    "currency": account.currency,
                    "reference": references[account.key],
                    "balance": round(balance, 2),
                    "restricted": round(restricted, 2),
                    "available": round(balance - restricted, 2),
                    "movement": round(movement, 2),
                }
            )

        # Memo: the short-term debt the Net Cash KPI nets the balances against.
        records.append(
            {
                "period": period,
                "scenario": scenario,
                "scenario_year": scenario_year,
                "organization_slug": entity_id,
                "account": MEMO_SHORT_TERM_DEBT,
                "account_label": "Short-term borrowings",
                "bank": "",
                "account_type": MEMO_TYPE,
                "country": "",
                "country_label": "",
                "currency": "EUR",
                "reference": "",
                "balance": round(short_term_debt, 2),
                "restricted": 0.0,
                "available": 0.0,
                "movement": 0.0,
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
    pages[CP_PAGE_ID] = [CP_RELATIVE_PATH]
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
    print(f"Generating fake cash positions for {len(entities)} entity(ies)…")

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
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "cash_position")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "bank_accounts.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):5d} records")

    print("Done.")


if __name__ == "__main__":
    main()
