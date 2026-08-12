#!/usr/bin/env python3
"""Generate the **fake** Expenses demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/balance_sheet.py → performance/cash_flow.py → this script

Answers "where is money being spent?". The cash flow's memo P&L already fixes
the monthly cost base (revenue − EBITDA); this script carves the **controllable
overhead** slice out of it — the discretionary spend a controller actually
steers, as opposed to payroll and cost of sales — and attributes every euro to
a category, a department and a vendor. The lines always sum back to that slice,
so the page agrees with Cost Centers and the P&L.

Departments are the Cost Centers roster, so "Top Departments" here and the
department ranking there name the same organization.

Record kinds (`kind` discriminator):
  - ``expense`` — one expense line (a **flow**: aggregate it over the window).
  - ``memo``    — per-period aggregates the lines cannot carry:
                  ``cost_base``, ``expenses``, ``prior_month_expenses``.
    The last one is what makes Expense Growth defined even when the window is a
    single month, since the server pre-filters records by scenario.

Run from the app root (after the two scripts above):
    python scripts/operations/expenses.py
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

EXPENSES_PAGE_ID = "expenses"
EXPENSES_RELATIVE_PATH = "expenses/expenses.json"
CF_RELATIVE_PATH = os.path.join("cash_flow", "cash_flow.json")
SCHEMA_VERSION = "1.0"

# Share of the monthly cost base that is controllable overhead. The rest is
# payroll and cost of sales, which this page deliberately does not cover.
OVERHEAD_SHARE = 0.185

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

DEPARTMENTS = {
    "sales": ("Sales", "Commercial"),
    "marketing": ("Marketing", "Commercial"),
    "customer_success": ("Customer Success", "Commercial"),
    "engineering": ("Engineering", "Product & Technology"),
    "product": ("Product", "Product & Technology"),
    "infrastructure": ("Infrastructure", "Product & Technology"),
    "operations": ("Operations", "Operations"),
    "supply_chain": ("Supply Chain", "Operations"),
    "finance": ("Finance", "Corporate"),
    "people": ("People & Culture", "Corporate"),
    "legal": ("Legal & Compliance", "Corporate"),
}


@dataclass(frozen=True)
class CategoryDef:
    key: str
    label: str
    # Share of controllable overhead.
    weight: float
    # Which departments spend it, and in what proportion.
    departments: dict[str, float]
    vendors: tuple[str, ...]
    # Multiplier applied in the month's peak season (see SEASONALITY).
    seasonal: bool
    # Typical number of lines per department per month.
    lines: int


CATEGORIES = [
    CategoryDef(
        "software", "Software & Subscriptions", 0.215,
        {
            "engineering": 0.30, "infrastructure": 0.22, "product": 0.12,
            "sales": 0.14, "marketing": 0.08, "finance": 0.06,
            "operations": 0.05, "people": 0.03,
        },
        ("CloudScale Hosting", "Atlassian", "Figma", "Datadog", "Salesforce",
         "Notion Labs", "GitHub", "Zoom"),
        False, 2,
    ),
    CategoryDef(
        "marketing", "Marketing & Advertising", 0.205,
        {"marketing": 0.78, "sales": 0.16, "customer_success": 0.06},
        ("Adverto Media Buying", "Google Ads", "LinkedIn Ads", "Salon Pro Expo",
         "Studio Kessel", "Meta Ads"),
        True, 3,
    ),
    CategoryDef(
        "travel", "Travel & Accommodation", 0.165,
        {
            "sales": 0.42, "customer_success": 0.14, "operations": 0.12,
            "engineering": 0.10, "supply_chain": 0.08, "marketing": 0.07,
            "finance": 0.04, "legal": 0.03,
        },
        ("Air France", "SNCF Voyageurs", "Accor Hotels", "Europcar",
         "Booking.com", "Eurostar"),
        True, 3,
    ),
    CategoryDef(
        "facilities", "Facilities & Utilities", 0.135,
        {"operations": 0.46, "people": 0.22, "engineering": 0.18, "finance": 0.14},
        ("Mercure Facility Services", "GreenPower Utilities", "Regus",
         "Veolia Eau", "Sécuritas"),
        False, 2,
    ),
    CategoryDef(
        "professional_fees", "Professional Fees", 0.105,
        {"legal": 0.38, "finance": 0.34, "people": 0.16, "operations": 0.12},
        ("Lexmont & Associés", "Deloitte", "Cabinet Perrin", "Mazars",
         "Consultis Partners"),
        False, 1,
    ),
    CategoryDef(
        "equipment", "IT Equipment", 0.075,
        {
            "engineering": 0.34, "infrastructure": 0.20, "operations": 0.16,
            "sales": 0.14, "people": 0.09, "product": 0.07,
        },
        ("Apple France", "Dell Technologies", "LDLC Pro", "EuroTech Components"),
        False, 2,
    ),
    CategoryDef(
        "training", "Training & Recruitment", 0.055,
        {"people": 0.52, "engineering": 0.20, "sales": 0.16, "operations": 0.12},
        ("Welcome to the Jungle", "OpenClassrooms", "Cabinet Hertz",
         "Formation Continue Pro"),
        True, 1,
    ),
    CategoryDef(
        "telecom", "Telecom & Connectivity", 0.030,
        {"infrastructure": 0.44, "operations": 0.26, "sales": 0.18, "people": 0.12},
        ("Ibercom Telecom", "Orange Business", "Free Pro"),
        False, 1,
    ),
    CategoryDef(
        "entertainment", "Client Entertainment", 0.015,
        {"sales": 0.58, "customer_success": 0.22, "marketing": 0.20},
        ("Le Comptoir", "Traiteur Belmont", "Brasserie Lipp"),
        True, 2,
    ),
]

# Month-of-year multiplier for seasonal categories: trade-show season in spring
# and autumn, near-nothing in August.
SEASONALITY = [
    0.0, 0.86, 0.94, 1.18, 1.12, 1.24, 1.06, 0.72, 0.48, 1.22, 1.16, 1.04, 0.98,
]

REQUESTERS = (
    "C. Aubert", "M. Lindqvist", "S. Benali", "J. Whitcombe", "L. Moreau",
    "P. Ferreira", "A. Kowalski", "N. Dubois", "T. Ricci", "E. Vasquez",
    "R. Haugen", "F. Bertrand", "K. Osei", "D. Marchetti",
)

PAYMENT_METHODS = (
    ("corporate_card", "Corporate card", 0.46),
    ("supplier_invoice", "Supplier invoice", 0.40),
    ("expense_claim", "Expense claim", 0.14),
)

# Status is a function of how long ago the line was booked, so recent months
# still have items in flight while old ones are settled.
STATUS_LABELS = {
    "settled": "Settled",
    "approved": "Approved",
    "pending": "Pending approval",
}


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"exp-{entity_id}".encode()).digest()[:4], "big")


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


def _pick(rng: random.Random, options: tuple[tuple[str, str, float], ...]) -> tuple[str, str]:
    roll = rng.random()
    cumulative = 0.0
    for key, label, weight in options:
        cumulative += weight
        if roll <= cumulative:
            return key, label
    return options[-1][0], options[-1][1]


def _monthly_totals(periods: list[tuple[str, str, str, float]]) -> dict[str, float]:
    """Controllable overhead per period, with seasonality kept budget-neutral.

    The seasonal categories move spend *between* months, they do not create it:
    every month's total is still ``OVERHEAD_SHARE`` of that month's cost base.
    Seasonality is applied inside the month, across categories.
    """
    return {period: cost_base * OVERHEAD_SHARE for period, _, _, cost_base in periods}


def _build_records(entity_id: str, cash_flow: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    periods = _cost_base_by_period(cash_flow)
    totals = _monthly_totals(periods)

    records: list[dict] = []
    previous_total = 0.0

    for index, (period, scenario, scenario_year, cost_base) in enumerate(periods):
        period_end = date.fromisoformat(period)
        month_total = totals[period]
        common = {
            "period": period,
            "scenario": scenario,
            "scenario_year": scenario_year,
            "organization_slug": entity_id,
        }

        # Seasonality reshuffles the mix between categories; the month's total
        # is then renormalized so it still ties back to the cost base.
        season = SEASONALITY[period_end.month]
        category_weights = [
            category.weight * (season if category.seasonal else 1.0)
            for category in CATEGORIES
        ]
        category_totals = _split(month_total, category_weights)

        sequence = 0
        for category, category_total in zip(CATEGORIES, category_totals):
            if category_total <= 0:
                continue
            department_keys = list(category.departments)
            department_totals = _split(
                category_total, [category.departments[key] for key in department_keys]
            )
            for department_key, department_total in zip(department_keys, department_totals):
                if department_total <= 1.0:
                    continue
                department_label, division_label = DEPARTMENTS[department_key]
                count = max(1, category.lines + rng.choice((-1, 0, 0, 1)))
                shares = [0.5 + rng.random() for _ in range(count)]
                for amount in _split(department_total, shares):
                    if amount <= 0.5:
                        continue
                    sequence += 1
                    booked = period_end - timedelta(days=rng.randint(0, 27))
                    method_key, method_label = _pick(rng, PAYMENT_METHODS)
                    # Older months are fully settled; the closing month still
                    # has claims working their way through approval.
                    months_old = len(periods) - 1 - index
                    if months_old >= 2:
                        status = "settled"
                    elif months_old == 1:
                        status = "settled" if rng.random() < 0.85 else "approved"
                    else:
                        roll = rng.random()
                        status = (
                            "settled" if roll < 0.55
                            else "approved" if roll < 0.86
                            else "pending"
                        )
                    records.append(
                        {
                            **common,
                            "kind": "expense",
                            "expense_ref": f"EXP-{period_end.year}{period_end.month:02d}-{sequence:04d}",
                            "expense_date": booked.isoformat(),
                            "category": category.key,
                            "category_label": category.label,
                            "department": department_key,
                            "department_label": department_label,
                            "division_label": division_label,
                            "vendor": category.vendors[
                                rng.randrange(len(category.vendors))
                            ],
                            "requester": REQUESTERS[rng.randrange(len(REQUESTERS))],
                            "amount": round(amount, 2),
                            "payment_method": method_key,
                            "payment_method_label": method_label,
                            "status": status,
                            "status_label": STATUS_LABELS[status],
                            # Missing receipts are the classic expense-policy
                            # exception; only claims and cards can lack one.
                            "has_receipt": method_key == "supplier_invoice"
                            or rng.random() > 0.07,
                        }
                    )

        # --- memo: the context a single expense line cannot carry.
        for metric, label, amount in (
            ("cost_base", "Cost base", cost_base),
            ("expenses", "Controllable expenses", month_total),
            ("prior_month_expenses", "Prior month expenses", previous_total),
        ):
            records.append(
                {
                    **common,
                    "kind": "memo",
                    "metric": metric,
                    "metric_label": label,
                    "expense_ref": "",
                    "expense_date": "",
                    "category": "memo",
                    "category_label": "Memo",
                    "department": "memo",
                    "department_label": "Memo",
                    "division_label": "Memo",
                    "vendor": "",
                    "requester": "",
                    "amount": round(amount, 2),
                    "payment_method": "",
                    "payment_method_label": "",
                    "status": "memo",
                    "status_label": "Memo",
                    "has_receipt": True,
                }
            )

        previous_total = month_total

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
    pages[EXPENSES_PAGE_ID] = [EXPENSES_RELATIVE_PATH]
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
    print(f"Generating fake expense books for {len(entities)} entity(ies)…")

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
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "expenses")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "expenses.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):6d} records")

    print("Done.")


if __name__ == "__main__":
    main()
