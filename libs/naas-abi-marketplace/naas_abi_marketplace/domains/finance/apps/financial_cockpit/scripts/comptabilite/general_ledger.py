#!/usr/bin/env python3
"""Generate the **fake** General Ledger demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/balance_sheet.py → performance/cash_flow.py → this script

Answers "what happened in the accounting records?". The cash flow's memo P&L
fixes revenue and the cost base each month; this script turns them into the
double-entry record that would have produced them — sales invoices, supplier
invoices, payroll, bank movements and the miscellaneous journal, posted line by
line against a chart of accounts.

Every entry balances (total debit == total credit, to the cent), the sales
journal's revenue accounts sum back to the memo P&L revenue, and the purchase
and payroll journals sum back to the cost base. That is what keeps this page
agreeing with the Income Statement and with Expenses.

A period is **closed** once its books are locked; ``CLOSED_THROUGH`` is the last
locked month, so anything after it counts as an open period and stays editable.
Manual entries (``source: "manual"``) are the ones a human keyed into the
miscellaneous journal — they are the input of the Journal Entries page, which
reads this file back.

Record kinds (`kind` discriminator):
  - ``line`` — one posting line (a **flow**: aggregate it over the window).
  - ``memo`` — per-period aggregates: ``revenue``, ``cost_base``,
    ``open_period`` (1 when the month is still open).

Run from the app root (after the two scripts above):
    python scripts/comptabilite/general_ledger.py
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

GL_PAGE_ID = "general-ledger"
GL_RELATIVE_PATH = "accounting/general_ledger.json"
CF_RELATIVE_PATH = os.path.join("cash_flow", "cash_flow.json")
SCHEMA_VERSION = "1.0"

# Last month whose books are locked. Later months are still open.
CLOSED_THROUGH = "2026-06-30"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

VAT_RATE = 0.20

# Share of the cost base that is payroll — it never goes through the purchase
# journal, which is why it is carved out before the supplier invoices.
PAYROLL_SHARE = 0.34
# Employer social charges, as a share of the payroll cost.
SOCIAL_CHARGE_SHARE = 0.31

# Entries raised per month, per journal. Kept modest so the ledger stays a
# readable demo rather than a stress test.
SALES_ENTRIES = 12
PURCHASE_ENTRIES = 22
COLLECTION_ENTRIES = 10
PAYMENT_ENTRIES = 10
MANUAL_ENTRIES = (3, 7)
# Share of manual entries keyed after the close deadline (period end + 6 days,
# see comptabilite/journal_entries.py).
LATE_POSTING_RATE = 0.18

# Share of the month's invoiced / purchased gross that settles in the same
# month. The rest is what leaves a receivable or a payable behind.
COLLECTION_SHARE = 0.94
SETTLEMENT_SHARE = 0.92

# Monthly depreciation charge, as a share of the month's cost base.
DEPRECIATION_SHARE = 0.055


@dataclass(frozen=True)
class Account:
    number: str
    label: str
    # asset | liability | equity | income | expense
    type: str


ACCOUNTS = {
    account.number: account
    for account in (
        Account("205000", "Software & licences", "asset"),
        Account("218000", "Equipment & fixtures", "asset"),
        Account("281000", "Accumulated depreciation", "asset"),
        Account("401000", "Trade payables", "liability"),
        Account("411000", "Trade receivables", "asset"),
        Account("421000", "Payroll liabilities", "liability"),
        Account("445660", "Deductible VAT", "asset"),
        Account("445710", "Collected VAT", "liability"),
        Account("486000", "Prepaid expenses", "asset"),
        Account("487000", "Deferred income", "liability"),
        Account("512000", "Bank", "asset"),
        Account("601000", "Raw materials", "expense"),
        Account("604000", "Subcontracting", "expense"),
        Account("606100", "Energy & utilities", "expense"),
        Account("613000", "Rent & leases", "expense"),
        Account("615000", "Maintenance & repairs", "expense"),
        Account("622000", "Professional fees", "expense"),
        Account("623000", "Marketing & advertising", "expense"),
        Account("624000", "Freight & logistics", "expense"),
        Account("626000", "Telecom & IT", "expense"),
        Account("641000", "Wages & salaries", "expense"),
        Account("645000", "Social charges", "expense"),
        Account("681000", "Depreciation charge", "expense"),
        Account("701000", "Product sales", "income"),
        Account("706000", "Services revenue", "income"),
    )
}

JOURNALS = {
    "sales": ("VE", "Sales"),
    "purchases": ("AC", "Purchases"),
    "bank": ("BQ", "Bank"),
    "payroll": ("PA", "Payroll"),
    "misc": ("OD", "Miscellaneous"),
}

# Expense accounts the purchase journal posts to, and their share of it.
PURCHASE_ACCOUNTS = (
    ("601000", 0.255),
    ("604000", 0.155),
    ("624000", 0.115),
    ("626000", 0.105),
    ("622000", 0.095),
    ("623000", 0.090),
    ("613000", 0.075),
    ("615000", 0.060),
    ("606100", 0.050),
)

# Split of revenue between the two income accounts.
REVENUE_ACCOUNTS = (("701000", 0.63), ("706000", 0.37))

CUSTOMERS = (
    "Groupe Atlantique", "Aurore Distribution", "Borealis Retail",
    "Cassiopea Media", "Delta Marine Services", "Helios Energy Group",
    "Kestrel Aviation", "Méridien Santé", "Montclair Immobilier",
    "Nordwind Logistics", "Novaterra Agro", "Polaris Consulting",
    "Silvergate Partners", "Vertex Manufacturing",
)

SUPPLIERS = (
    "EuroTech Components", "LogiFret Transport", "CloudScale Hosting",
    "Acier du Nord", "Mercure Facility Services", "Lexmont & Associés",
    "Prima Packaging", "NordFleet Leasing", "Atelier Métal",
    "GreenPower Utilities", "Adverto Media Buying", "Consultis Partners",
    "Ibercom Telecom", "Veolia Eau", "Manutan",
)

# Who keys the entries. Imported ones carry the integration's name instead.
ACCOUNTANTS = ("M. Delcourt", "S. Roussel", "A. Fabre", "K. Nyström", "P. Ollier")
INTEGRATION_USER = "integration"

# Miscellaneous-journal adjustments: (label, debit account, credit account) and
# the size of the entry as a share of the month's cost base.
MANUAL_TEMPLATES = (
    ("Accrued expenses", "622000", "401000", (0.004, 0.020)),
    ("Prepaid expense reversal", "613000", "486000", (0.003, 0.014)),
    ("Deferred revenue release", "487000", "706000", (0.005, 0.022)),
    ("Cut-off reclassification", "604000", "601000", (0.002, 0.012)),
    ("Cost reclassification", "626000", "622000", (0.002, 0.010)),
    ("Provision for risks", "615000", "401000", (0.003, 0.016)),
    ("Payroll accrual", "641000", "421000", (0.004, 0.018)),
    ("Bank reconciliation plug", "622000", "512000", (0.001, 0.006)),
    ("VAT adjustment", "445660", "445710", (0.002, 0.009)),
)


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"gl-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _pnl_by_period(cash_flow: dict) -> list[tuple[str, str, str, float, float]]:
    """``(period, scenario, scenario_year, revenue, cost_base)`` sorted by period."""
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
            revenue.get(period, 0.0),
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


class LedgerBuilder:
    """Accumulates balanced entries for one entity."""

    def __init__(self, rng: random.Random, entity_id: str) -> None:
        self.rng = rng
        self.entity_id = entity_id
        self.records: list[dict] = []
        self.sequence = 0

    def entry(
        self,
        *,
        common: dict,
        journal: str,
        entry_date: date,
        posted_date: date,
        label: str,
        third_party: str,
        source: str,
        user: str,
        # (account, debit, credit) — must balance.
        lines: list[tuple[str, float, float]],
    ) -> None:
        self.sequence += 1
        period_end = date.fromisoformat(common["period"])
        code, journal_label = JOURNALS[journal]
        entry_ref = f"{code}-{period_end.year}{period_end.month:02d}-{self.sequence:04d}"

        # The last line absorbs the rounding so the entry balances to the cent.
        rounded = [(number, round(debit, 2), round(credit, 2)) for number, debit, credit in lines]
        drift = round(
            sum(debit for _, debit, _ in rounded) - sum(credit for _, _, credit in rounded),
            2,
        )
        if drift:
            number, debit, credit = rounded[-1]
            if credit > 0:
                rounded[-1] = (number, debit, round(credit + drift, 2))
            else:
                rounded[-1] = (number, round(debit - drift, 2), credit)

        for line_no, (number, debit, credit) in enumerate(rounded, start=1):
            account = ACCOUNTS[number]
            self.records.append(
                {
                    **common,
                    "kind": "line",
                    "entry_ref": entry_ref,
                    "line_no": line_no,
                    "entry_date": entry_date.isoformat(),
                    "posted_date": posted_date.isoformat(),
                    "journal": journal,
                    "journal_code": code,
                    "journal_label": journal_label,
                    "account": number,
                    "account_label": account.label,
                    "account_type": account.type,
                    "label": label,
                    "third_party": third_party,
                    "debit": debit,
                    "credit": credit,
                    "amount": round(debit - credit, 2),
                    "source": source,
                    "user": user,
                }
            )


def _dates(rng: random.Random, period_end: date, post_lag: tuple[int, int]) -> tuple[date, date]:
    """A transaction date inside the month, and when it was posted."""
    entry_date = period_end - timedelta(days=rng.randint(0, period_end.day - 1))
    return entry_date, entry_date + timedelta(days=rng.randint(*post_lag))


def _build_records(entity_id: str, cash_flow: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    builder = LedgerBuilder(rng, entity_id)

    for period, scenario, scenario_year, revenue, cost_base in _pnl_by_period(cash_flow):
        period_end = date.fromisoformat(period)
        common = {
            "period": period,
            "scenario": scenario,
            "scenario_year": scenario_year,
            "organization_slug": entity_id,
        }
        builder.sequence = 0

        # --- Sales journal: the month's revenue, invoiced ------------------
        weights = [0.5 + rng.random() for _ in range(SALES_ENTRIES)]
        for net in _split(revenue, weights):
            if net <= 1.0:
                continue
            entry_date, posted = _dates(rng, period_end, (0, 3))
            customer = CUSTOMERS[rng.randrange(len(CUSTOMERS))]
            vat = net * VAT_RATE
            account = (
                REVENUE_ACCOUNTS[0][0]
                if rng.random() < REVENUE_ACCOUNTS[0][1]
                else REVENUE_ACCOUNTS[1][0]
            )
            builder.entry(
                common=common,
                journal="sales",
                entry_date=entry_date,
                posted_date=posted,
                label=f"Customer invoice — {customer}",
                third_party=customer,
                source="imported",
                user=INTEGRATION_USER,
                lines=[
                    ("411000", net + vat, 0.0),
                    (account, 0.0, net),
                    ("445710", 0.0, vat),
                ],
            )

        # --- Purchase journal: the cost base, minus payroll ----------------
        payroll = cost_base * PAYROLL_SHARE
        purchases = cost_base - payroll
        account_totals = _split(purchases, [share for _, share in PURCHASE_ACCOUNTS])
        per_account = max(1, PURCHASE_ENTRIES // len(PURCHASE_ACCOUNTS))
        for (number, _), account_total in zip(PURCHASE_ACCOUNTS, account_totals):
            weights = [0.5 + rng.random() for _ in range(per_account)]
            for net in _split(account_total, weights):
                if net <= 1.0:
                    continue
                entry_date, posted = _dates(rng, period_end, (1, 6))
                supplier = SUPPLIERS[rng.randrange(len(SUPPLIERS))]
                vat = net * VAT_RATE
                builder.entry(
                    common=common,
                    journal="purchases",
                    entry_date=entry_date,
                    posted_date=posted,
                    label=f"Supplier invoice — {supplier}",
                    third_party=supplier,
                    source="imported",
                    user=INTEGRATION_USER,
                    lines=[
                        (number, net, 0.0),
                        ("445660", vat, 0.0),
                        ("401000", 0.0, net + vat),
                    ],
                )

        # --- Payroll journal ----------------------------------------------
        wages = payroll / (1.0 + SOCIAL_CHARGE_SHARE)
        social = payroll - wages
        payroll_date = period_end - timedelta(days=rng.randint(2, 6))
        for label, number, amount in (
            ("Monthly payroll", "641000", wages),
            ("Employer social charges", "645000", social),
        ):
            builder.entry(
                common=common,
                journal="payroll",
                entry_date=payroll_date,
                posted_date=payroll_date + timedelta(days=rng.randint(0, 2)),
                label=label,
                third_party="Payroll",
                source="imported",
                user=INTEGRATION_USER,
                lines=[(number, amount, 0.0), ("421000", 0.0, amount)],
            )
        builder.entry(
            common=common,
            journal="payroll",
            entry_date=payroll_date,
            posted_date=payroll_date + timedelta(days=1),
            label="Payroll settlement",
            third_party="Payroll",
            source="imported",
            user=INTEGRATION_USER,
            lines=[("421000", payroll, 0.0), ("512000", 0.0, payroll)],
        )

        # --- Bank journal: what actually settled in the month ---------------
        collected = revenue * (1.0 + VAT_RATE) * COLLECTION_SHARE
        weights = [0.5 + rng.random() for _ in range(COLLECTION_ENTRIES)]
        for amount in _split(collected, weights):
            if amount <= 1.0:
                continue
            entry_date, posted = _dates(rng, period_end, (0, 1))
            customer = CUSTOMERS[rng.randrange(len(CUSTOMERS))]
            builder.entry(
                common=common,
                journal="bank",
                entry_date=entry_date,
                posted_date=posted,
                label=f"Customer payment — {customer}",
                third_party=customer,
                source="imported",
                user=INTEGRATION_USER,
                lines=[("512000", amount, 0.0), ("411000", 0.0, amount)],
            )

        settled = purchases * (1.0 + VAT_RATE) * SETTLEMENT_SHARE
        weights = [0.5 + rng.random() for _ in range(PAYMENT_ENTRIES)]
        for amount in _split(settled, weights):
            if amount <= 1.0:
                continue
            entry_date, posted = _dates(rng, period_end, (0, 1))
            supplier = SUPPLIERS[rng.randrange(len(SUPPLIERS))]
            builder.entry(
                common=common,
                journal="bank",
                entry_date=entry_date,
                posted_date=posted,
                label=f"Supplier payment — {supplier}",
                third_party=supplier,
                source="imported",
                user=INTEGRATION_USER,
                lines=[("401000", amount, 0.0), ("512000", 0.0, amount)],
            )

        # --- Miscellaneous journal: depreciation, then the manual entries ---
        depreciation = cost_base * DEPRECIATION_SHARE
        builder.entry(
            common=common,
            journal="misc",
            entry_date=period_end,
            posted_date=period_end + timedelta(days=rng.randint(1, 4)),
            label="Monthly depreciation charge",
            third_party="",
            source="imported",
            user=INTEGRATION_USER,
            lines=[("681000", depreciation, 0.0), ("281000", 0.0, depreciation)],
        )

        for _ in range(rng.randint(*MANUAL_ENTRIES)):
            label, debit_account, credit_account, size = MANUAL_TEMPLATES[
                rng.randrange(len(MANUAL_TEMPLATES))
            ]
            amount = cost_base * (size[0] + rng.random() * (size[1] - size[0]))
            if amount <= 1.0:
                continue
            # Manual entries are keyed during the close, so they land after the
            # month end. Most make the deadline; the minority that drift past it
            # are what the Journal Entries page reports as late.
            posted = period_end + timedelta(
                days=rng.randint(7, 19) if rng.random() < LATE_POSTING_RATE
                else rng.randint(1, 6)
            )
            builder.entry(
                common=common,
                journal="misc",
                entry_date=period_end,
                posted_date=posted,
                label=label,
                third_party="",
                source="manual",
                user=ACCOUNTANTS[rng.randrange(len(ACCOUNTANTS))],
                lines=[(debit_account, amount, 0.0), (credit_account, 0.0, amount)],
            )

        # --- Memos -----------------------------------------------------------
        for metric, metric_label, amount in (
            ("revenue", "Revenue", revenue),
            ("cost_base", "Cost base", cost_base),
            ("open_period", "Open period", 1.0 if period > CLOSED_THROUGH else 0.0),
        ):
            builder.records.append(
                {
                    **common,
                    "kind": "memo",
                    "metric": metric,
                    "metric_label": metric_label,
                    "entry_ref": "",
                    "line_no": 0,
                    "entry_date": period,
                    "posted_date": period,
                    "journal": "memo",
                    "journal_code": "",
                    "journal_label": "Memo",
                    "account": "",
                    "account_label": "",
                    "account_type": "memo",
                    "label": metric_label,
                    "third_party": "",
                    "debit": 0.0,
                    "credit": 0.0,
                    "amount": round(amount, 2),
                    "source": "memo",
                    "user": "",
                }
            )

    return builder.records


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
    pages[GL_PAGE_ID] = [GL_RELATIVE_PATH]
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
        raise SystemExit("No cash flow found — run scripts/performance/cash_flow.py first.")
    print(f"Generating fake general ledgers for {len(entities)} entity(ies)…")

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
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "accounting")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "general_ledger.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):6d} records")

    print("Done.")


if __name__ == "__main__":
    main()
