#!/usr/bin/env python3
"""Generate the **fake** Accounts Payable demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/balance_sheet.py → performance/cash_flow.py → this script

Answers "what do we owe suppliers?". The balance sheet already states how much
is owed each month; this script only decides **who is owed and when it falls
due** — splitting the Trade payables line across a supplier book by fixed
weights, then cutting each supplier's balance into open bills with due dates
either side of the month end. The bills always sum back to the balance sheet.

Purchases and payments are derived from the payables identity

    closing AP = opening AP + purchased − paid

with purchases taken from the cash flow's memo P&L cost base (revenue −
EBITDA), so payments are exact rather than invented and DPO reconciles with the
cost base every other page uses.

Record kinds (`kind` discriminator):
  - ``bill`` — one open supplier invoice, per period-end snapshot (a **stock**).
  - ``memo`` — per-period aggregates: ``purchased``, ``paid``, ``payables``,
    ``dpo``.

Run from the app root (after the two scripts above):
    python scripts/operations/supplier_invoices.py
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

AP_PAGE_ID = "supplier-invoices"
AP_RELATIVE_PATH = "payables/payables.json"
BS_RELATIVE_PATH = os.path.join("balance_sheet", "balance_sheet.json")
CF_RELATIVE_PATH = os.path.join("cash_flow", "cash_flow.json")
SCHEMA_VERSION = "1.0"

PAYABLES_LINE = "Trade payables"

DPO_TRAILING_MONTHS = 3
DAYS_PER_MONTH = 30.4375

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Aging buckets, in days past due. Mirrors the receivables book so the two
# Operations pages read the same way.
AGING_BUCKETS = (
    ("current", "Not yet due", -10**6, 0),
    ("d1_30", "1–30 days", 1, 30),
    ("d31_60", "31–60 days", 31, 60),
    ("d61_90", "61–90 days", 61, 90),
    ("d90_plus", "90+ days", 91, 10**6),
)

# Horizon of the payment calendar, in weeks past the month end.
CALENDAR_WEEKS = 8


@dataclass(frozen=True)
class SupplierDef:
    key: str
    name: str
    category: str
    country: str
    # Share of the Trade payables line. Normalized across the book.
    weight: float
    # Negotiated payment terms, in days.
    terms: int
    # How the balance spreads across the aging buckets — how well *we* pay.
    # (not yet due, 1–30, 31–60, 61–90, 90+)
    aging_profile: tuple[float, float, float, float, float]
    bills: int
    # Early-payment discount, if the supplier offers one.
    discount_pct: float = 0.0


SUPPLIERS = [
    SupplierDef(
        "eurotech", "EuroTech Components", "Raw materials", "DE", 0.155, 60,
        (0.901, 0.068, 0.022, 0.007, 0.002), 6, discount_pct=0.02,
    ),
    SupplierDef(
        "logifret", "LogiFret Transport", "Logistics", "FR", 0.118, 45,
        (0.874, 0.085, 0.027, 0.009, 0.004), 5,
    ),
    SupplierDef(
        "cloudscale", "CloudScale Hosting", "IT & software", "IE", 0.102, 30,
        (0.946, 0.045, 0.009, 0.000, 0.000), 4,
    ),
    SupplierDef(
        "acier_nord", "Acier du Nord", "Raw materials", "BE", 0.095, 60,
        (0.843, 0.094, 0.041, 0.016, 0.006), 5, discount_pct=0.015,
    ),
    SupplierDef(
        "mercure", "Mercure Facility Services", "Facilities", "FR", 0.078, 45,
        (0.883, 0.081, 0.027, 0.007, 0.002), 4,
    ),
    SupplierDef(
        "lexmont", "Lexmont & Associés", "Professional fees", "FR", 0.066, 30,
        (0.820, 0.108, 0.049, 0.018, 0.004), 3,
    ),
    SupplierDef(
        "ibercom", "Ibercom Telecom", "Telecom", "ES", 0.058, 30,
        (0.932, 0.054, 0.014, 0.000, 0.000), 3,
    ),
    SupplierDef(
        "prima_pack", "Prima Packaging", "Raw materials", "IT", 0.054, 45,
        (0.861, 0.090, 0.036, 0.011, 0.002), 4,
    ),
    SupplierDef(
        "nordfleet", "NordFleet Leasing", "Fleet", "SE", 0.048, 30,
        (0.955, 0.040, 0.004, 0.000, 0.000), 2,
    ),
    SupplierDef(
        "atelier_m", "Atelier Métal", "Subcontracting", "FR", 0.045, 45,
        (0.811, 0.104, 0.054, 0.023, 0.009), 3,
    ),
    SupplierDef(
        "greenpower", "GreenPower Utilities", "Energy", "FR", 0.042, 30,
        (0.919, 0.063, 0.018, 0.000, 0.000), 3,
    ),
    SupplierDef(
        "adverto", "Adverto Media Buying", "Marketing", "UK", 0.038, 45,
        (0.834, 0.099, 0.045, 0.018, 0.004), 3,
    ),
    SupplierDef(
        "sanitas", "Sanitas Workwear", "Consumables", "PT", 0.031, 30,
        (0.869, 0.086, 0.032, 0.009, 0.005), 2,
    ),
    SupplierDef(
        "helvetia_ins", "Helvetia Assurances", "Insurance", "CH", 0.028, 60,
        (0.937, 0.049, 0.013, 0.000, 0.000), 2,
    ),
]


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"ap-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _payables_by_period(balance_sheet: dict) -> list[tuple[str, str, str, float]]:
    """``(period, scenario, scenario_year, trade payables)`` sorted by period."""
    periods: dict[str, tuple[str, str]] = {}
    amounts: dict[str, float] = {}
    for record in balance_sheet.get("records", []):
        if record.get("category") != PAYABLES_LINE:
            continue
        period = record["period"]
        periods[period] = (record["scenario"], record["scenario_year"])
        amounts[period] = amounts.get(period, 0.0) + float(record["amount"])
    return [(period, *periods[period], amounts[period]) for period in sorted(periods)]


def _cost_base_by_period(cash_flow: dict) -> dict[str, float]:
    """Revenue − EBITDA from the memo P&L: what the company buys in, per month."""
    revenue: dict[str, float] = {}
    ebitda: dict[str, float] = {}
    for record in cash_flow.get("records", []):
        if record.get("activity") != "memo":
            continue
        if record.get("category") == "Revenue":
            revenue[record["period"]] = float(record["amount"])
        elif record.get("category") == "EBITDA":
            ebitda[record["period"]] = float(record["amount"])
    return {
        period: max(0.0, amount - ebitda.get(period, 0.0))
        for period, amount in revenue.items()
    }


def _split(total: float, weights: list[float]) -> list[float]:
    """Split ``total`` by ``weights`` so the parts sum back to it exactly."""
    weight_sum = sum(weights)
    if weight_sum <= 0 or not weights:
        return [0.0] * len(weights)
    parts = [total * weight / weight_sum for weight in weights[:-1]]
    parts.append(total - sum(parts))
    return parts


def _supplier_bills(
    rng: random.Random,
    supplier: SupplierDef,
    period_end: date,
    balance: float,
    sequence: int,
) -> list[dict]:
    """Cut one supplier's closing balance into open bills."""
    if balance <= 0:
        return []

    count = max(1, supplier.bills + rng.choice((-1, 0, 0, 1)))
    bucket_amounts = _split(balance, list(supplier.aging_profile))

    bills: list[dict] = []
    for (bucket_key, bucket_label, low, high), bucket_total, weight in zip(
        AGING_BUCKETS, bucket_amounts, supplier.aging_profile
    ):
        if bucket_total <= 1.0:
            continue
        # Bill count follows the money: the not-yet-due bucket holds most of
        # the balance and so most of the bills, which is what gives the payment
        # calendar something falling due in every week.
        n = max(1, round(count * weight))
        shares = [0.6 + rng.random() for _ in range(n)]
        for amount in _split(bucket_total, shares):
            if amount <= 0.5:
                continue
            if bucket_key == "current":
                days_overdue = -rng.randint(1, max(2, supplier.terms))
            else:
                floor = max(low, 1)
                ceiling = min(high, floor + 120)
                days_overdue = rng.randint(floor, ceiling)

            due = period_end - timedelta(days=days_overdue)
            received = due - timedelta(days=supplier.terms)
            sequence += 1
            # Weeks from the month end until the money leaves. Overdue bills
            # land in week 0 — they are already payable.
            due_in_days = -days_overdue
            bills.append(
                {
                    "kind": "bill",
                    "supplier": supplier.key,
                    "supplier_name": supplier.name,
                    "category": supplier.category,
                    "country": supplier.country,
                    "bill_ref": f"AP-{period_end.year}{period_end.month:02d}-{sequence:04d}",
                    "received_date": received.isoformat(),
                    "due_date": due.isoformat(),
                    "payment_terms_days": supplier.terms,
                    "amount": round(amount, 2),
                    "outstanding": round(amount, 2),
                    "days_overdue": days_overdue,
                    "days_to_due": due_in_days,
                    "due_week": max(0, min(CALENDAR_WEEKS, (due_in_days + 6) // 7)),
                    "aging_bucket": bucket_key,
                    "aging_label": bucket_label,
                    "status": "overdue" if days_overdue > 0 else "scheduled",
                    "discount_pct": supplier.discount_pct,
                    # An early-payment discount is only still available while
                    # the bill is inside its terms.
                    "discount_available": supplier.discount_pct > 0 and days_overdue < 0,
                }
            )

    return bills


def _memo(metric: str, label: str, amount: float) -> dict:
    """A per-period aggregate. Same columns as a bill so the shape is flat."""
    return {
        "kind": "memo",
        "metric": metric,
        "metric_label": label,
        "amount": round(amount, 4),
        "supplier": "",
        "supplier_name": "",
        "category": "",
        "country": "",
        "bill_ref": "",
        "received_date": "",
        "due_date": "",
        "payment_terms_days": 0,
        "outstanding": 0.0,
        "days_overdue": 0,
        "days_to_due": 0,
        "due_week": 0,
        "aging_bucket": "memo",
        "aging_label": "Memo",
        "status": "memo",
        "discount_pct": 0.0,
        "discount_available": False,
    }


def _build_records(entity_id: str, balance_sheet: dict, cash_flow: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    periods = _payables_by_period(balance_sheet)
    cost_base = _cost_base_by_period(cash_flow)

    records: list[dict] = []
    balances = [balance for _, _, _, balance in periods]

    for index, (period, scenario, scenario_year, payables) in enumerate(periods):
        period_end = date.fromisoformat(period)
        common = {
            "period": period,
            "scenario": scenario,
            "scenario_year": scenario_year,
            "organization_slug": entity_id,
        }

        # --- open bills: the supplier book always sums back to the BS line.
        shares = _split(payables, [supplier.weight for supplier in SUPPLIERS])
        sequence = 0
        for supplier, balance in zip(SUPPLIERS, shares):
            bills = _supplier_bills(rng, supplier, period_end, balance, sequence)
            sequence += len(bills)
            for bill in bills:
                records.append({**common, **bill})

        # --- memo: the flows behind the balance.
        purchased = cost_base.get(period, 0.0)
        if index > 0:
            opening = balances[index - 1]
        elif len(balances) > 1 and balances[1] > 0:
            opening = balances[0] ** 2 / balances[1]
        else:
            opening = balances[0]
        paid = opening + purchased - payables

        window = [
            cost_base.get(periods[i][0], 0.0)
            for i in range(max(0, index - DPO_TRAILING_MONTHS + 1), index + 1)
        ]
        window_purchases = sum(window)
        dpo = (
            payables / window_purchases * (len(window) * DAYS_PER_MONTH)
            if window_purchases > 0
            else 0.0
        )

        for metric, label, amount in (
            ("purchased", "Purchased", purchased),
            ("paid", "Paid", paid),
            ("payables", "Trade payables", payables),
            ("dpo", "DPO (days)", dpo),
        ):
            records.append({**common, **_memo(metric, label, amount)})

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
    pages[AP_PAGE_ID] = [AP_RELATIVE_PATH]
    manifest["data_version"] = data_version
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entities_with_sources() -> list[str]:
    out: list[str] = []
    for manifest_path in glob.glob(os.path.join(ENTITIES_DIR, "*", "manifest.json")):
        entity_dir = os.path.dirname(manifest_path)
        if os.path.exists(os.path.join(entity_dir, BS_RELATIVE_PATH)) and os.path.exists(
            os.path.join(entity_dir, CF_RELATIVE_PATH)
        ):
            out.append(os.path.basename(entity_dir))
    return sorted(out)


def main() -> None:
    data_version = datetime.now().strftime("%Y-%m-%d %H:%M")
    entities = _entities_with_sources()
    if not entities:
        raise SystemExit(
            "No balance sheet / cash flow found — run scripts/performance/balance_sheet.py "
            "and scripts/performance/cash_flow.py first."
        )
    print(f"Generating fake payables books for {len(entities)} entity(ies)…")

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
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "payables")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "payables.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):6d} records")

    print("Done.")


if __name__ == "__main__":
    main()
