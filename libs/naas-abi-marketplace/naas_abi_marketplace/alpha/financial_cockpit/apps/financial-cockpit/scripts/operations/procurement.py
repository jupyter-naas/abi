#!/usr/bin/env python3
"""Generate the **fake** Procurement demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/balance_sheet.py → performance/cash_flow.py → this script

Answers "are purchases under control?". The cash flow's memo P&L fixes the
monthly cost base (revenue − EBITDA); this script carves out the share of it
that goes through a **purchase order** and turns that into an order book — who
requested it, who approved it and how long that took, which supplier won it,
and what was negotiated off the reference quote. The orders always sum back to
that share, so the page agrees with the P&L and with Expenses.

Suppliers are the payables book and departments are the Cost Centers roster, so
the three Operations pages name the same counterparties.

Each order walks a fixed pipeline

    requested → approved → ordered → received → invoiced

and this script emits the **date each milestone is reached**, not the stage the
order sits at. The stage is a function of when you look: an order raised in
July is in flight if you are looking at July and long since invoiced if you are
looking at December. Deriving it in the model against the window's closing
month is what keeps Open Orders and Commitments right in every scenario —
baking a stage in here would zero them out on any past month.

A small share of orders **stall**: they sit at one stage for weeks past the
normal lead time. Without them every order would clear on schedule and the
approval funnel would have no drop-off to show.

Record kinds (`kind` discriminator):
  - ``order`` — one purchase order (a **flow**: aggregate it over the window).
  - ``memo``  — per-period aggregates: ``cost_base``, ``procurement_spend``.

Run from the app root (after the two scripts above):
    python scripts/operations/procurement.py
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

PROCUREMENT_PAGE_ID = "procurement"
PROCUREMENT_RELATIVE_PATH = "procurement/purchase_orders.json"
CF_RELATIVE_PATH = os.path.join("cash_flow", "cash_flow.json")
SCHEMA_VERSION = "1.0"

# Share of the monthly cost base that is raised through a purchase order. The
# rest is payroll, rent and other spend that never sees a PO.
PO_SHARE = 0.42

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Days from ordering to invoicing, on top of the category lead time.
ORDER_LAG_DAYS = (1, 4)
INVOICE_LAG_DAYS = (6, 21)

# Share of orders that stall, and how long they sit stuck.
STALL_RATE = 0.09
STALL_DAYS = (25, 95)

DEPARTMENTS = {
    "operations": ("Operations", "Operations"),
    "supply_chain": ("Supply Chain", "Operations"),
    "engineering": ("Engineering", "Product & Technology"),
    "infrastructure": ("Infrastructure", "Product & Technology"),
    "marketing": ("Marketing", "Commercial"),
    "sales": ("Sales", "Commercial"),
    "facilities": ("Facilities", "Corporate"),
    "finance": ("Finance", "Corporate"),
    "people": ("People & Culture", "Corporate"),
}


@dataclass(frozen=True)
class ProcurementCategoryDef:
    key: str
    label: str
    # Share of PO-covered spend.
    weight: float
    departments: tuple[str, ...]
    suppliers: tuple[str, ...]
    # Typical order size relative to the category's monthly budget: a low value
    # means many small orders, a high one means a handful of large ones.
    order_size: float
    # Negotiating room against the reference quote, as a fraction.
    savings_range: tuple[float, float]
    # Typical lead time from order to delivery, in days.
    lead_time: int


CATEGORIES = [
    ProcurementCategoryDef(
        "raw_materials", "Raw Materials", 0.285,
        ("supply_chain", "operations"),
        ("EuroTech Components", "Acier du Nord", "Prima Packaging"),
        0.24, (0.01, 0.055), 21,
    ),
    ProcurementCategoryDef(
        "subcontracting", "Subcontracting", 0.165,
        ("operations", "engineering"),
        ("Atelier Métal", "Consultis Partners", "Studio Kessel"),
        0.20, (0.005, 0.04), 30,
    ),
    ProcurementCategoryDef(
        "logistics", "Logistics & Freight", 0.135,
        ("supply_chain", "operations"),
        ("LogiFret Transport", "NordFleet Leasing", "DB Schenker"),
        0.16, (0.01, 0.045), 10,
    ),
    ProcurementCategoryDef(
        "it_software", "IT & Software", 0.125,
        ("infrastructure", "engineering", "finance"),
        ("CloudScale Hosting", "Dell Technologies", "EuroTech Components",
         "Atlassian"),
        0.18, (0.02, 0.09), 14,
    ),
    ProcurementCategoryDef(
        "marketing_services", "Marketing Services", 0.105,
        ("marketing", "sales"),
        ("Adverto Media Buying", "Studio Kessel", "Salon Pro Expo"),
        0.22, (0.015, 0.075), 25,
    ),
    ProcurementCategoryDef(
        "facilities", "Facilities & Energy", 0.085,
        ("facilities", "operations"),
        ("Mercure Facility Services", "GreenPower Utilities", "Veolia Eau"),
        0.19, (0.005, 0.035), 18,
    ),
    ProcurementCategoryDef(
        "professional_services", "Professional Services", 0.065,
        ("finance", "people", "operations"),
        ("Lexmont & Associés", "Mazars", "Cabinet Hertz"),
        0.26, (0.0, 0.05), 20,
    ),
    ProcurementCategoryDef(
        "consumables", "Consumables & Workwear", 0.035,
        ("operations", "people", "facilities"),
        ("Sanitas Workwear", "LDLC Pro", "Manutan"),
        0.14, (0.01, 0.06), 12,
    ),
]

REQUESTERS = (
    "C. Aubert", "M. Lindqvist", "S. Benali", "J. Whitcombe", "L. Moreau",
    "P. Ferreira", "A. Kowalski", "N. Dubois", "T. Ricci", "E. Vasquez",
)

APPROVERS = ("H. Vasseur", "G. Lombardi", "I. Sørensen", "B. Chevalier")

# Approval takes longer the bigger the order — the threshold above which a
# second signature is needed, and the extra days that costs.
DUAL_SIGNATURE_THRESHOLD = 75_000.0


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"po-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _cost_base_by_period(cash_flow: dict) -> list[tuple[str, str, str, float]]:
    """``(period, scenario, scenario_year, revenue − EBITDA)`` sorted by period."""
    periods: dict[str, tuple[str, str]] = {}
    revenue: dict[str, float] = {}
    ebitda: dict[str, float] = {}
    for record in cash_flow.get("records", []):
        if record.get("activity") != "memo":
            continue
        category = record.get("category")
        if category not in ("Revenue", "EBITDA"):
            continue
        period = record["period"]
        periods[period] = (record["scenario"], record["scenario_year"])
        if category == "Revenue":
            revenue[period] = float(record["amount"])
        else:
            ebitda[period] = float(record["amount"])
    return [
        (
            period,
            *periods[period],
            max(0.0, revenue.get(period, 0.0) - ebitda.get(period, 0.0)),
        )
        for period in sorted(periods)
    ]


def _split(total: float, weights: list[float]) -> list[float]:
    """Split ``total`` by ``weights`` so the parts sum back to it exactly."""
    weight_sum = sum(weights)
    if weight_sum <= 0 or not weights:
        return [0.0] * len(weights)
    parts = [total * weight / weight_sum for weight in weights[:-1]]
    parts.append(total - sum(parts))
    return parts


def _milestones(
    rng: random.Random,
    requested: date,
    approval_days: int,
    lead_time: int,
) -> tuple[str, str, str, str, int]:
    """The date each pipeline stage is reached, plus the stall it suffered.

    One stage is picked to stall so the drop-off in the approval funnel lands
    somewhere specific rather than smeared evenly across the pipeline.
    """
    stall = rng.randint(*STALL_DAYS) if rng.random() < STALL_RATE else 0
    stalled_at = rng.randrange(3) if stall else -1

    approved = requested + timedelta(days=approval_days + (stall if stalled_at == 0 else 0))
    ordered = approved + timedelta(
        days=rng.randint(*ORDER_LAG_DAYS) + (stall if stalled_at == 1 else 0)
    )
    received = ordered + timedelta(
        days=max(1, lead_time + rng.randint(-3, 7)) + (stall if stalled_at == 2 else 0)
    )
    invoiced = received + timedelta(days=rng.randint(*INVOICE_LAG_DAYS))
    return (
        approved.isoformat(),
        ordered.isoformat(),
        received.isoformat(),
        invoiced.isoformat(),
        stall,
    )


def _build_records(entity_id: str, cash_flow: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    periods = _cost_base_by_period(cash_flow)

    records: list[dict] = []

    for period, scenario, scenario_year, cost_base in periods:
        period_end = date.fromisoformat(period)
        month_spend = cost_base * PO_SHARE
        common = {
            "period": period,
            "scenario": scenario,
            "scenario_year": scenario_year,
            "organization_slug": entity_id,
        }

        category_totals = _split(
            month_spend, [category.weight for category in CATEGORIES]
        )
        sequence = 0
        for category, category_total in zip(CATEGORIES, category_totals):
            if category_total <= 0:
                continue
            # order_size is the typical order as a fraction of the category's
            # month, so a small fraction means many orders.
            count = max(1, round(1.0 / category.order_size) + rng.choice((-1, 0, 1)))
            shares = [0.45 + rng.random() * 1.3 for _ in range(count)]
            for amount in _split(category_total, shares):
                if amount <= 1.0:
                    continue
                sequence += 1
                requested = period_end - timedelta(days=rng.randint(2, 27))
                # Bigger orders need a second signature, which costs days.
                base_days = rng.randint(1, 6)
                approval_days = (
                    base_days + rng.randint(2, 9)
                    if amount >= DUAL_SIGNATURE_THRESHOLD
                    else base_days
                )
                approved, ordered, received, invoiced, stall = _milestones(
                    rng, requested, approval_days, category.lead_time
                )

                low, high = category.savings_range
                savings_rate = low + rng.random() * (high - low)
                # The reference quote is what the order would have cost before
                # negotiation; savings are the gap down to what was agreed.
                baseline = amount / (1.0 - savings_rate)

                department = category.departments[
                    rng.randrange(len(category.departments))
                ]
                department_label, division_label = DEPARTMENTS[department]

                records.append(
                    {
                        **common,
                        "kind": "order",
                        "po_ref": f"PO-{period_end.year}{period_end.month:02d}-{sequence:04d}",
                        "supplier": category.suppliers[
                            rng.randrange(len(category.suppliers))
                        ],
                        "category": category.key,
                        "category_label": category.label,
                        "department": department,
                        "department_label": department_label,
                        "division_label": division_label,
                        "requester": REQUESTERS[rng.randrange(len(REQUESTERS))],
                        "approver": APPROVERS[rng.randrange(len(APPROVERS))],
                        # The stage is derived in the model by comparing these
                        # against the closing month of the window on screen.
                        "requested_date": requested.isoformat(),
                        "approved_date": approved,
                        "ordered_date": ordered,
                        "received_date": received,
                        "invoiced_date": invoiced,
                        "approval_days": approval_days,
                        "stall_days": stall,
                        "amount": round(amount, 2),
                        "baseline_amount": round(baseline, 2),
                        "savings": round(baseline - amount, 2),
                        "requires_dual_signature": amount >= DUAL_SIGNATURE_THRESHOLD,
                    }
                )

        for metric, label, amount in (
            ("cost_base", "Cost base", cost_base),
            ("procurement_spend", "PO-covered spend", month_spend),
        ):
            records.append(
                {
                    **common,
                    "kind": "memo",
                    "metric": metric,
                    "metric_label": label,
                    "po_ref": "",
                    "supplier": "",
                    "category": "memo",
                    "category_label": "Memo",
                    "department": "memo",
                    "department_label": "Memo",
                    "division_label": "Memo",
                    "requester": "",
                    "approver": "",
                    "requested_date": "",
                    "approved_date": "",
                    "ordered_date": "",
                    "received_date": "",
                    "invoiced_date": "",
                    "approval_days": None,
                    "stall_days": 0,
                    "amount": round(amount, 2),
                    "baseline_amount": 0.0,
                    "savings": 0.0,
                    "requires_dual_signature": False,
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
    pages[PROCUREMENT_PAGE_ID] = [PROCUREMENT_RELATIVE_PATH]
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
            "No cash flow found — run scripts/performance/cash_flow.py first."
        )
    print(f"Generating fake procurement books for {len(entities)} entity(ies)…")

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
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "procurement")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "purchase_orders.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):6d} records")

    print("Done.")


if __name__ == "__main__":
    main()
