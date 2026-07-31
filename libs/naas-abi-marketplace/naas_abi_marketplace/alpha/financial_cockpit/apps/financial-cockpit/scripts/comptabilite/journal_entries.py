#!/usr/bin/env python3
"""Generate the **fake** Journal Entries demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/cash_flow.py → comptabilite/general_ledger.py → this script

Answers "which accounting adjustments were made?". It invents no entry of its
own: it reads the general ledger back, keeps the lines a human keyed
(``source: "manual"``), and folds each entry's lines into a single row carrying
the review workflow around it — what kind of adjustment it is, who prepared it,
who validated it and when, and whether it landed after the close deadline.

Because the rows are the ledger's own manual entries, the Manual Entries KPI
here equals the one on the General Ledger page by construction.

An entry is **late** when it was posted more than ``CLOSE_DEADLINE_DAYS`` after
the period end — the window the close allows for keying adjustments. Entries in
a period whose books are already locked are settled (approved or rejected);
entries in an open period can still be sitting in validation.

Record kinds (`kind` discriminator):
  - ``entry`` — one manual journal entry (a **flow**: aggregate over the window).
  - ``memo``  — per-period aggregates: ``ledger_entries`` (all entries posted
    that month, manual or not), giving the manual share a denominator.

Run from the app root (after the two scripts above):
    python scripts/comptabilite/journal_entries.py
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import random
from datetime import date, datetime, timedelta

# web/data mirrors the R2 layout the Next.js app reads from.
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_ROOT = os.path.join(APP_ROOT, "web", "data")
ENTITIES_DIR = os.path.join(DATA_ROOT, "entities")

JE_PAGE_ID = "journal-entries"
JE_RELATIVE_PATH = "accounting/journal_entries.json"
GL_RELATIVE_PATH = os.path.join("accounting", "general_ledger.json")
SCHEMA_VERSION = "1.0"

# Last month whose books are locked — must match comptabilite/general_ledger.py.
CLOSED_THROUGH = "2026-06-30"

# Days after the period end an adjustment may still be keyed before it counts
# as late.
CLOSE_DEADLINE_DAYS = 6

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# The ledger's manual labels, mapped onto the adjustment taxonomy the page
# reports on. Anything unmapped falls back to a plain adjustment.
ENTRY_TYPES = {
    "adjustment": "Adjustment",
    "plug": "Plug",
    "reclassification": "Reclassification",
    "accrual": "Accrual",
    "provision": "Provision",
}

LABEL_TYPES = {
    "Accrued expenses": "accrual",
    "Payroll accrual": "accrual",
    "Cut-off reclassification": "reclassification",
    "Cost reclassification": "reclassification",
    "Provision for risks": "provision",
    "Bank reconciliation plug": "plug",
    "Prepaid expense reversal": "adjustment",
    "Deferred revenue release": "adjustment",
    "VAT adjustment": "adjustment",
}

STATUS_LABELS = {
    "approved": "Approved",
    "pending": "Pending validation",
    "rejected": "Rejected",
}

# Validation outcomes, by whether the period is still open. A locked period has
# nothing left in validation — that is what locking it means.
CLOSED_OUTCOMES = (("approved", 0.94), ("rejected", 1.0))
OPEN_OUTCOMES = (("approved", 0.52), ("pending", 0.95), ("rejected", 1.0))

REVIEWERS = ("H. Vasseur", "C. Lemaire", "I. Sørensen", "B. Chevalier")

# Days the reviewer takes, once the entry is submitted.
REVIEW_DAYS = (0, 7)


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"je-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _pick(rng: random.Random, outcomes: tuple[tuple[str, float], ...]) -> str:
    draw = rng.random()
    for value, ceiling in outcomes:
        if draw <= ceiling:
            return value
    return outcomes[-1][0]


def _build_records(entity_id: str, ledger: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))

    # Fold the ledger's manual lines into one row per entry, in ledger order.
    entries: dict[str, dict] = {}
    ledger_entries: dict[str, set[str]] = {}
    period_scenarios: dict[str, tuple[str, str]] = {}
    for line in ledger.get("records", []):
        if line.get("kind") != "line":
            continue
        ledger_entries.setdefault(line["period"], set()).add(line["entry_ref"])
        period_scenarios[line["period"]] = (line["scenario"], line["scenario_year"])
        if line.get("source") != "manual":
            continue
        entry = entries.setdefault(
            line["entry_ref"],
            {
                "period": line["period"],
                "scenario": line["scenario"],
                "scenario_year": line["scenario_year"],
                "organization_slug": line.get("organization_slug", entity_id),
                "entry_ref": line["entry_ref"],
                "entry_date": line["entry_date"],
                "posted_date": line["posted_date"],
                "journal": line["journal"],
                "journal_label": line["journal_label"],
                "label": line["label"],
                "preparer": line["user"],
                "amount": 0.0,
                "line_count": 0,
                "debit_account": "",
                "debit_account_label": "",
                "credit_account": "",
                "credit_account_label": "",
            },
        )
        entry["amount"] += float(line["debit"])
        entry["line_count"] += 1
        if line["debit"] > 0 and not entry["debit_account"]:
            entry["debit_account"] = line["account"]
            entry["debit_account_label"] = line["account_label"]
        if line["credit"] > 0 and not entry["credit_account"]:
            entry["credit_account"] = line["account"]
            entry["credit_account_label"] = line["account_label"]

    records: list[dict] = []
    for entry in entries.values():
        period_end = date.fromisoformat(entry["period"])
        posted = date.fromisoformat(entry["posted_date"])
        deadline = period_end + timedelta(days=CLOSE_DEADLINE_DAYS)
        days_late = max(0, (posted - deadline).days)

        is_open = entry["period"] > CLOSED_THROUGH
        status = _pick(rng, OPEN_OUTCOMES if is_open else CLOSED_OUTCOMES)
        approval_days = rng.randint(*REVIEW_DAYS)
        approved_date = (
            (posted + timedelta(days=approval_days)).isoformat()
            if status != "pending"
            else ""
        )
        entry_type = LABEL_TYPES.get(entry["label"], "adjustment")

        records.append(
            {
                "period": entry["period"],
                "scenario": entry["scenario"],
                "scenario_year": entry["scenario_year"],
                "organization_slug": entry["organization_slug"],
                "kind": "entry",
                "entry_ref": entry["entry_ref"],
                "entry_date": entry["entry_date"],
                "posted_date": entry["posted_date"],
                "journal": entry["journal"],
                "journal_label": entry["journal_label"],
                "label": entry["label"],
                "entry_type": entry_type,
                "entry_type_label": ENTRY_TYPES[entry_type],
                "debit_account": entry["debit_account"],
                "debit_account_label": entry["debit_account_label"],
                "credit_account": entry["credit_account"],
                "credit_account_label": entry["credit_account_label"],
                "line_count": entry["line_count"],
                "amount": round(entry["amount"], 2),
                "preparer": entry["preparer"],
                "approver": (
                    REVIEWERS[rng.randrange(len(REVIEWERS))] if status != "pending" else ""
                ),
                "status": status,
                "status_label": STATUS_LABELS[status],
                "approved_date": approved_date,
                "approval_days": approval_days if status != "pending" else None,
                "deadline_date": deadline.isoformat(),
                "is_late": days_late > 0,
                "days_late": days_late,
                "is_open_period": is_open,
            }
        )

    records.sort(key=lambda record: (record["period"], record["entry_ref"]))

    # Memo: how many entries the ledger posted that month in total, so the
    # manual share has a denominator that matches the General Ledger page.
    for period in sorted(ledger_entries):
        scenario, scenario_year = period_scenarios[period]
        records.append(
            {
                "period": period,
                "scenario": scenario,
                "scenario_year": scenario_year,
                "organization_slug": entity_id,
                "kind": "memo",
                "metric": "ledger_entries",
                "metric_label": "Ledger entries",
                "entry_ref": "",
                "entry_date": period,
                "posted_date": period,
                "journal": "memo",
                "journal_label": "Memo",
                "label": "Ledger entries",
                "entry_type": "memo",
                "entry_type_label": "Memo",
                "debit_account": "",
                "debit_account_label": "",
                "credit_account": "",
                "credit_account_label": "",
                "line_count": 0,
                "amount": float(len(ledger_entries[period])),
                "preparer": "",
                "approver": "",
                "status": "memo",
                "status_label": "Memo",
                "approved_date": "",
                "approval_days": None,
                "deadline_date": "",
                "is_late": False,
                "days_late": 0,
                "is_open_period": period > CLOSED_THROUGH,
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
    pages[JE_PAGE_ID] = [JE_RELATIVE_PATH]
    manifest["data_version"] = data_version
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _entities_with_sources() -> list[str]:
    out: list[str] = []
    for manifest_path in glob.glob(os.path.join(ENTITIES_DIR, "*", "manifest.json")):
        entity_dir = os.path.dirname(manifest_path)
        if os.path.exists(os.path.join(entity_dir, GL_RELATIVE_PATH)):
            out.append(os.path.basename(entity_dir))
    return sorted(out)


def main() -> None:
    data_version = datetime.now().strftime("%Y-%m-%d %H:%M")
    entities = _entities_with_sources()
    if not entities:
        raise SystemExit(
            "No general ledger found — run scripts/comptabilite/general_ledger.py first."
        )
    print(f"Generating fake journal entries for {len(entities)} entity(ies)…")

    for entity_id in entities:
        ledger = _load(entity_id, GL_RELATIVE_PATH)
        if ledger is None:
            continue
        records = _build_records(entity_id, ledger)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "data_version": data_version,
            "entity_id": entity_id,
            "scenarios": _scenarios(ledger, records),
            "records": records,
        }
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "accounting")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "journal_entries.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):6d} records")

    print("Done.")


if __name__ == "__main__":
    main()
