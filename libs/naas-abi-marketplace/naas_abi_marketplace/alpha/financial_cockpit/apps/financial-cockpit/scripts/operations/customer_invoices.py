#!/usr/bin/env python3
"""Generate the **fake** Accounts Receivable demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/balance_sheet.py → performance/cash_flow.py → this script

Answers "are customers paying on time?". The balance sheet already states how
much is owed by customers each month; this script only decides **who owes it
and how late they are** — splitting the Trade receivables line across a
customer book by fixed weights, then cutting each customer's balance into open
invoices whose ages follow that customer's payment behaviour. The invoices
always sum back to the balance sheet.

Invoiced and collected are derived from the receivables identity

    closing AR = opening AR + invoiced − collected

with invoiced taken from the cash flow's memo revenue, so collections are exact
rather than invented and the Collection Rate KPI reconciles month over month.

Record kinds (`kind` discriminator):
  - ``invoice`` — one open invoice, per period-end snapshot (a **stock**).
  - ``memo``    — per-period aggregates the invoice rows cannot carry:
                  ``revenue``, ``invoiced``, ``collected``, ``dso``.

Run from the app root (after the two scripts above):
    python scripts/operations/customer_invoices.py
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

AR_PAGE_ID = "customer-invoices"
AR_RELATIVE_PATH = "receivables/receivables.json"
BS_RELATIVE_PATH = os.path.join("balance_sheet", "balance_sheet.json")
CF_RELATIVE_PATH = os.path.join("cash_flow", "cash_flow.json")
SCHEMA_VERSION = "1.0"

RECEIVABLES_LINE = "Trade receivables"

# Trailing window used for the DSO denominator, in months. Three months smooths
# the seasonality out of a metric that is otherwise dominated by it.
DSO_TRAILING_MONTHS = 3
DAYS_PER_MONTH = 30.4375

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Aging buckets, in days past due. The last one is open-ended.
AGING_BUCKETS = (
    ("current", "Not yet due", -10**6, 0),
    ("d1_30", "1–30 days", 1, 30),
    ("d31_60", "31–60 days", 31, 60),
    ("d61_90", "61–90 days", 61, 90),
    ("d90_plus", "90+ days", 91, 10**6),
)


@dataclass(frozen=True)
class CustomerDef:
    key: str
    name: str
    segment: str
    country: str
    # Share of the Trade receivables line. Normalized across the book.
    weight: float
    # Contractual payment terms, in days.
    terms: int
    # How the customer's balance spreads across the aging buckets — the
    # payment behaviour that drives every late-payment KPI on the page.
    # (not yet due, 1–30, 31–60, 61–90, 90+)
    aging_profile: tuple[float, float, float, float, float]
    # Typical invoice count for this customer; the balance is cut into this
    # many open invoices (± 1).
    invoices: int
    disputed: bool = False


CUSTOMERS = [
    CustomerDef(
        "nordwind", "Nordwind Logistics", "Enterprise", "DE", 0.150, 60,
        (0.79, 0.14, 0.05, 0.015, 0.005), 6,
    ),
    CustomerDef(
        "helios", "Helios Energy Group", "Enterprise", "ES", 0.128, 60,
        (0.62, 0.20, 0.10, 0.05, 0.03), 5, disputed=True,
    ),
    CustomerDef(
        "atlantique", "Groupe Atlantique", "Enterprise", "FR", 0.112, 45,
        (0.85, 0.11, 0.03, 0.007, 0.003), 5,
    ),
    CustomerDef(
        "vertex", "Vertex Manufacturing", "Mid-market", "FR", 0.094, 45,
        (0.73, 0.17, 0.07, 0.025, 0.005), 4,
    ),
    CustomerDef(
        "borealis", "Borealis Retail", "Mid-market", "SE", 0.081, 30,
        (0.55, 0.20, 0.13, 0.08, 0.04), 4, disputed=True,
    ),
    CustomerDef(
        "meridien", "Méridien Santé", "Public", "FR", 0.075, 60,
        (0.50, 0.19, 0.15, 0.09, 0.07), 4,
    ),
    CustomerDef(
        "cassiopea", "Cassiopea Media", "Mid-market", "IT", 0.068, 30,
        (0.77, 0.15, 0.05, 0.02, 0.01), 3,
    ),
    CustomerDef(
        "polaris", "Polaris Consulting", "Mid-market", "BE", 0.058, 30,
        (0.86, 0.10, 0.03, 0.007, 0.003), 3,
    ),
    CustomerDef(
        "delta_marine", "Delta Marine Services", "Mid-market", "NL", 0.052, 45,
        (0.67, 0.19, 0.09, 0.04, 0.01), 3,
    ),
    CustomerDef(
        "aurore", "Aurore Distribution", "SMB", "FR", 0.047, 30,
        (0.81, 0.13, 0.04, 0.015, 0.005), 3,
    ),
    CustomerDef(
        "kestrel", "Kestrel Aviation", "Enterprise", "UK", 0.043, 60,
        (0.69, 0.18, 0.08, 0.04, 0.01), 3,
    ),
    CustomerDef(
        "montclair", "Montclair Immobilier", "SMB", "FR", 0.036, 30,
        (0.58, 0.19, 0.13, 0.06, 0.04), 2,
    ),
    CustomerDef(
        "silvergate", "Silvergate Partners", "SMB", "UK", 0.030, 30,
        (0.84, 0.12, 0.03, 0.007, 0.003), 2,
    ),
    CustomerDef(
        "novaterra", "Novaterra Agro", "SMB", "PT", 0.026, 45,
        (0.46, 0.19, 0.16, 0.11, 0.08), 2,
    ),
]


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"ar-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _receivables_by_period(balance_sheet: dict) -> list[tuple[str, str, str, float]]:
    """``(period, scenario, scenario_year, trade receivables)`` sorted by period."""
    periods: dict[str, tuple[str, str]] = {}
    amounts: dict[str, float] = {}
    for record in balance_sheet.get("records", []):
        if record.get("category") != RECEIVABLES_LINE:
            continue
        period = record["period"]
        periods[period] = (record["scenario"], record["scenario_year"])
        amounts[period] = amounts.get(period, 0.0) + float(record["amount"])
    return [(period, *periods[period], amounts[period]) for period in sorted(periods)]


def _revenue_by_period(cash_flow: dict) -> dict[str, float]:
    """The memo P&L revenue every downstream generator agrees on."""
    revenue: dict[str, float] = {}
    for record in cash_flow.get("records", []):
        if record.get("activity") == "memo" and record.get("category") == "Revenue":
            revenue[record["period"]] = revenue.get(record["period"], 0.0) + float(
                record["amount"]
            )
    return revenue


def _bucket_for(days_overdue: int) -> tuple[str, str]:
    for key, label, low, high in AGING_BUCKETS:
        if low <= days_overdue <= high:
            return key, label
    return AGING_BUCKETS[-1][0], AGING_BUCKETS[-1][1]


def _split(total: float, weights: list[float]) -> list[float]:
    """Split ``total`` by ``weights`` so the parts sum back to it exactly."""
    weight_sum = sum(weights)
    if weight_sum <= 0 or not weights:
        return [0.0] * len(weights)
    parts = [total * weight / weight_sum for weight in weights[:-1]]
    parts.append(total - sum(parts))
    return parts


def _customer_invoices(
    rng: random.Random,
    customer: CustomerDef,
    period_end: date,
    balance: float,
    sequence: int,
) -> list[dict]:
    """Cut one customer's closing balance into open invoices."""
    if balance <= 0:
        return []

    count = max(1, customer.invoices + rng.choice((-1, 0, 0, 1)))
    # Spread the balance across buckets by the behaviour profile, then cut each
    # bucket's share into invoices. Buckets are drawn first so the aging shape
    # stays stable while the individual invoices vary.
    bucket_amounts = _split(balance, list(customer.aging_profile))

    invoices: list[dict] = []
    for (bucket_key, bucket_label, low, high), bucket_total, weight in zip(
        AGING_BUCKETS, bucket_amounts, customer.aging_profile
    ):
        if bucket_total <= 1.0:
            continue
        # Invoice count follows the money: the bucket holding most of the
        # balance holds most of the invoices. Splitting the count evenly would
        # leave the (large) not-yet-due bucket with one giant invoice, and then
        # whole weeks with nothing falling due.
        n = max(1, round(count * weight))
        shares = [0.6 + rng.random() for _ in range(n)]
        for amount in _split(bucket_total, shares):
            if amount <= 0.5:
                continue
            if bucket_key == "current":
                # Not yet due: somewhere between tomorrow and the full term.
                days_overdue = -rng.randint(1, max(2, customer.terms))
            else:
                floor = max(low, 1)
                ceiling = min(high, floor + 120)
                days_overdue = rng.randint(floor, ceiling)

            due = period_end - timedelta(days=days_overdue)
            issue = due - timedelta(days=customer.terms)
            sequence += 1
            invoices.append(
                {
                    "kind": "invoice",
                    "customer": customer.key,
                    "customer_name": customer.name,
                    "segment": customer.segment,
                    "country": customer.country,
                    "invoice_ref": f"INV-{period_end.year}{period_end.month:02d}-{sequence:04d}",
                    "issue_date": issue.isoformat(),
                    "due_date": due.isoformat(),
                    "payment_terms_days": customer.terms,
                    # Demo book: nothing is part-paid, so the open amount is the
                    # invoice amount. Kept as two fields because a real ledger
                    # has both and the table shows them side by side.
                    "amount": round(amount, 2),
                    "outstanding": round(amount, 2),
                    "days_overdue": days_overdue,
                    "aging_bucket": bucket_key,
                    "aging_label": bucket_label,
                    "status": "overdue" if days_overdue > 0 else "current",
                    # Disputes sit in the oldest bucket — that is what makes them
                    # old in the first place.
                    "is_disputed": customer.disputed and bucket_key == "d90_plus",
                }
            )

    return invoices


def _memo(metric: str, label: str, amount: float) -> dict:
    """A per-period aggregate. Same columns as an invoice so the shape is flat."""
    return {
        "kind": "memo",
        "metric": metric,
        "metric_label": label,
        "amount": round(amount, 4),
        "customer": "",
        "customer_name": "",
        "segment": "",
        "country": "",
        "invoice_ref": "",
        "issue_date": "",
        "due_date": "",
        "payment_terms_days": 0,
        "outstanding": 0.0,
        "days_overdue": 0,
        "aging_bucket": "memo",
        "aging_label": "Memo",
        "status": "memo",
        "is_disputed": False,
    }


def _build_records(entity_id: str, balance_sheet: dict, cash_flow: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    periods = _receivables_by_period(balance_sheet)
    revenue_by_period = _revenue_by_period(cash_flow)

    weight_total = sum(customer.weight for customer in CUSTOMERS)
    records: list[dict] = []
    balances = [balance for _, _, _, balance in periods]

    for index, (period, scenario, scenario_year, receivables) in enumerate(periods):
        period_end = date.fromisoformat(period)
        common = {
            "period": period,
            "scenario": scenario,
            "scenario_year": scenario_year,
            "organization_slug": entity_id,
        }

        # --- open invoices: the customer book always sums back to the BS line.
        shares = _split(receivables, [customer.weight for customer in CUSTOMERS])
        sequence = 0
        not_yet_due = 0.0
        for customer, balance in zip(CUSTOMERS, shares):
            invoices = _customer_invoices(rng, customer, period_end, balance, sequence)
            sequence += len(invoices)
            for invoice in invoices:
                if invoice["aging_bucket"] == "current":
                    not_yet_due += invoice["outstanding"]
                records.append({**common, **invoice})

        # --- memo: the flows behind the balance.
        # closing AR = opening AR + invoiced − collected, so collections fall
        # out of the identity instead of being drawn.
        invoiced = revenue_by_period.get(period, 0.0)
        if index > 0:
            opening = balances[index - 1]
        elif len(balances) > 1 and balances[1] > 0:
            # No prior month to open from: extrapolate backwards along the same
            # month-over-month step, so the first Collection Rate is not 100%.
            opening = balances[0] ** 2 / balances[1]
        else:
            opening = balances[0]
        collected = opening + invoiced - receivables

        # DSO on a trailing revenue window — a single month is too seasonal.
        window = [
            revenue_by_period.get(periods[i][0], 0.0)
            for i in range(max(0, index - DSO_TRAILING_MONTHS + 1), index + 1)
        ]
        window_revenue = sum(window)
        dso = (
            receivables / window_revenue * (len(window) * DAYS_PER_MONTH)
            if window_revenue > 0
            else 0.0
        )

        # Collection Effectiveness Index denominator: everything that *could*
        # have been collected in the month — the opening book plus what was
        # billed, less the part of the closing book that is not due yet.
        # Summing both sides over the window keeps the ratio exact for any
        # scenario, which averaging per-month rates would not.
        collectible = opening + invoiced - not_yet_due

        for metric, label, amount in (
            ("revenue", "Revenue", invoiced),
            ("invoiced", "Invoiced", invoiced),
            ("collected", "Collected", collected),
            ("collectible", "Collectible", collectible),
            ("receivables", "Trade receivables", receivables),
            ("dso", "DSO (days)", dso),
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
    pages[AR_PAGE_ID] = [AR_RELATIVE_PATH]
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
    print(f"Generating fake receivables books for {len(entities)} entity(ies)…")

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
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "receivables")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "receivables.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):6d} records")

    print("Done.")


if __name__ == "__main__":
    main()
