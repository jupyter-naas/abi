#!/usr/bin/env python3
"""Generate the **fake** Financial Close demo dataset for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Part of the demo-data chain:

    performance/cash_flow.py → comptabilite/general_ledger.py → this script

Answers "are we ready to close the period?". It reads the general ledger to
learn which months are locked and which are still open, then lays the monthly
close checklist over each of them: the same ~18 tasks, each owned by someone,
each planned to run between two **business days after the period end**, and
each with the day it was actually signed off.

That is what makes the page's three time axes agree:

- a **locked** month has every task done, a handful of them late, and its
  issues resolved — its close duration is the business day the last task landed;
- the month whose close is **in progress** (the first one after the ledger's
  last locked month) is cut at ``PROGRESS_DAY``: anything planned to end before
  it is done, anything spanning it is running or blocked, the rest has not
  started;
- later months carry the plan only, so the checklist reads as the work still
  ahead rather than as failure.

Record kinds (`kind` discriminator):
  - ``task``  — one checklist task for one month.
  - ``issue`` — one issue raised during that month's close.
  - ``memo``  — per-period aggregates: ``close_duration_days``,
    ``planned_duration_days``, ``open_period``.

Run from the app root (after the two scripts above):
    python scripts/comptabilite/financial_close.py
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

CLOSE_PAGE_ID = "financial-close"
CLOSE_RELATIVE_PATH = "financial_close/financial_close.json"
GL_RELATIVE_PATH = os.path.join("accounting", "general_ledger.json")
SCHEMA_VERSION = "1.0"

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Business days into the close of the month currently being closed.
PROGRESS_DAY = 4

# Share of tasks that overrun their planned end date, in a month that closed.
LATE_TASK_RATE = 0.16
# Share of completed tasks that a reviewer has signed off on.
VALIDATION_RATE = 0.88
# Of the tasks that should already be done in the in-progress close, the share
# that is stuck instead.
BLOCKED_RATE = 0.12

# Issues raised per close.
ISSUES_PER_CLOSE = (1, 4)

AREAS = {
    "bank": "Bank & cash",
    "receivables": "Receivables",
    "payables": "Payables",
    "payroll": "Payroll",
    "fixed_assets": "Fixed assets",
    "inventory": "Inventory",
    "accruals": "Accruals & provisions",
    "tax": "Tax",
    "intercompany": "Intercompany",
    "reporting": "Reporting",
}

OWNERS = (
    "M. Delcourt", "S. Roussel", "A. Fabre", "K. Nyström", "P. Ollier",
    "C. Lemaire",
)

VALIDATORS = ("H. Vasseur", "I. Sørensen", "B. Chevalier")


@dataclass(frozen=True)
class TaskDef:
    key: str
    label: str
    area: str
    owner: str
    # Planned window, in business days after the period end.
    start_day: int
    end_day: int


# The checklist, in the order the close actually runs: sub-ledgers first, then
# the accounting judgements, then tax and reporting on top of them.
TASKS = [
    TaskDef("bank_rec", "Bank reconciliations", "bank", "S. Roussel", 1, 2),
    TaskDef("cash_pool", "Cash pooling confirmation", "bank", "S. Roussel", 1, 2),
    TaskDef("ar_ledger", "AR sub-ledger reconciliation", "receivables", "A. Fabre", 1, 3),
    TaskDef("ar_provision", "Bad-debt provision review", "receivables", "A. Fabre", 3, 5),
    TaskDef("ap_ledger", "AP sub-ledger reconciliation", "payables", "K. Nyström", 1, 3),
    TaskDef("gr_accrual", "Goods-received accrual", "payables", "K. Nyström", 2, 4),
    TaskDef("payroll_post", "Payroll posting & reconciliation", "payroll", "P. Ollier", 1, 3),
    TaskDef("social_accrual", "Social charges accrual", "payroll", "P. Ollier", 3, 4),
    TaskDef("inventory_count", "Inventory count & valuation", "inventory", "M. Delcourt", 2, 5),
    TaskDef("depreciation", "Depreciation run", "fixed_assets", "C. Lemaire", 2, 3),
    TaskDef("capex_review", "Capex capitalisation review", "fixed_assets", "C. Lemaire", 3, 5),
    TaskDef("accruals", "Accruals & prepayments", "accruals", "M. Delcourt", 4, 6),
    TaskDef("provisions", "Provision review", "accruals", "M. Delcourt", 5, 7),
    TaskDef("intercompany", "Intercompany reconciliation", "intercompany", "A. Fabre", 4, 6),
    TaskDef("vat_return", "VAT return preparation", "tax", "S. Roussel", 5, 7),
    TaskDef("tax_accrual", "Corporate tax accrual", "tax", "K. Nyström", 6, 8),
    TaskDef("trial_balance", "Trial balance review", "reporting", "P. Ollier", 7, 9),
    TaskDef("reporting_pack", "Management reporting pack", "reporting", "C. Lemaire", 8, 10),
]

STATUS_LABELS = {
    "done": "Done",
    "in_progress": "In progress",
    "blocked": "Blocked",
    "not_started": "Not started",
}

SEVERITY_LABELS = {"high": "High", "medium": "Medium", "low": "Low"}

# Issues the close actually turns up, by area.
ISSUE_TEMPLATES = (
    ("bank", "Unreconciled bank line", "medium"),
    ("bank", "Missing cash confirmation", "low"),
    ("receivables", "Unapplied customer payment", "medium"),
    ("receivables", "Disputed invoice pending write-off", "high"),
    ("payables", "Supplier invoice without purchase order", "medium"),
    ("payables", "Goods received not invoiced", "medium"),
    ("payroll", "Payroll variance above threshold", "high"),
    ("inventory", "Stock count variance", "high"),
    ("inventory", "Obsolete stock not provisioned", "medium"),
    ("fixed_assets", "Capex charged to expense", "medium"),
    ("accruals", "Accrual without supporting evidence", "low"),
    ("tax", "VAT mismatch against the ledger", "high"),
    ("intercompany", "Intercompany balance out of sync", "high"),
    ("reporting", "Late management commentary", "low"),
)


def _seed_for(entity_id: str) -> int:
    return int.from_bytes(hashlib.md5(f"close-{entity_id}".encode()).digest()[:4], "big")


def _load(entity_id: str, relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, entity_id, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _periods(ledger: dict) -> list[tuple[str, str, str, bool]]:
    """``(period, scenario, scenario_year, is_open)`` sorted by period."""
    meta: dict[str, tuple[str, str]] = {}
    open_flag: dict[str, bool] = {}
    for record in ledger.get("records", []):
        period = record.get("period")
        if not period:
            continue
        meta[period] = (record["scenario"], record["scenario_year"])
        if record.get("kind") == "memo" and record.get("metric") == "open_period":
            open_flag[period] = float(record["amount"]) > 0
    return [
        (period, *meta[period], open_flag.get(period, False)) for period in sorted(meta)
    ]


def _business_day(period_end: date, day: int) -> date:
    """The ``day``-th business day after ``period_end`` (weekends skipped)."""
    current = period_end
    remaining = max(1, day)
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _build_records(entity_id: str, ledger: dict) -> list[dict]:
    rng = random.Random(_seed_for(entity_id))
    periods = _periods(ledger)
    # The close currently running is the first month whose books are still open.
    in_progress = next(
        (period for period, _, _, is_open in periods if is_open), None
    )

    records: list[dict] = []

    for period, scenario, scenario_year, is_open in periods:
        period_end = date.fromisoformat(period)
        common = {
            "period": period,
            "scenario": scenario,
            "scenario_year": scenario_year,
            "organization_slug": entity_id,
        }
        # closed → everything ran; running → cut at PROGRESS_DAY; ahead → plan only.
        phase = "closed" if not is_open else ("running" if period == in_progress else "ahead")

        planned_duration = max(task.end_day for task in TASKS)
        actual_last_day = 0

        for task in TASKS:
            planned_start = _business_day(period_end, task.start_day)
            planned_end = _business_day(period_end, task.end_day)

            status = "not_started"
            actual_start = ""
            actual_end = ""
            actual_end_day = 0
            is_validated = False
            validator = ""

            if phase == "closed":
                status = "done"
                overrun = (
                    rng.randint(1, 3) if rng.random() < LATE_TASK_RATE else 0
                )
                actual_end_day = task.end_day + overrun
                actual_start = _business_day(period_end, task.start_day).isoformat()
                actual_end = _business_day(period_end, actual_end_day).isoformat()
                is_validated = rng.random() < VALIDATION_RATE
                validator = VALIDATORS[rng.randrange(len(VALIDATORS))] if is_validated else ""
            elif phase == "running":
                if task.end_day <= PROGRESS_DAY:
                    blocked = rng.random() < BLOCKED_RATE
                    status = "blocked" if blocked else "done"
                    if status == "done":
                        actual_end_day = task.end_day
                        actual_start = planned_start.isoformat()
                        actual_end = _business_day(period_end, actual_end_day).isoformat()
                        is_validated = rng.random() < VALIDATION_RATE
                        validator = (
                            VALIDATORS[rng.randrange(len(VALIDATORS))]
                            if is_validated
                            else ""
                        )
                    else:
                        actual_start = planned_start.isoformat()
                elif task.start_day <= PROGRESS_DAY:
                    status = "blocked" if rng.random() < BLOCKED_RATE else "in_progress"
                    actual_start = planned_start.isoformat()

            actual_last_day = max(actual_last_day, actual_end_day)
            days_late = max(0, actual_end_day - task.end_day) if actual_end else 0

            records.append(
                {
                    **common,
                    "kind": "task",
                    "task_ref": f"{period_end.year}{period_end.month:02d}-{task.key}",
                    "task": task.key,
                    "task_label": task.label,
                    "area": task.area,
                    "area_label": AREAS[task.area],
                    "owner": task.owner,
                    "planned_start_day": task.start_day,
                    "planned_end_day": task.end_day,
                    "planned_start_date": planned_start.isoformat(),
                    "planned_end_date": planned_end.isoformat(),
                    "actual_start_date": actual_start,
                    "actual_end_date": actual_end,
                    "actual_end_day": actual_end_day,
                    "status": status,
                    "status_label": STATUS_LABELS[status],
                    "is_done": status == "done",
                    "is_late": days_late > 0
                    or (phase == "running" and status != "done" and task.end_day < PROGRESS_DAY),
                    "days_late": days_late,
                    "is_validated": is_validated,
                    "validator": validator,
                    "severity": "",
                    "severity_label": "",
                    "title": task.label,
                    "raised_date": "",
                    "resolved_date": "",
                    "is_resolved": False,
                    # One task — so a plain sum over the window counts them.
                    "amount": 1.0,
                }
            )

        # --- issues raised during this close ---------------------------------
        if phase != "ahead":
            for index in range(rng.randint(*ISSUES_PER_CLOSE)):
                area, title, severity = ISSUE_TEMPLATES[
                    rng.randrange(len(ISSUE_TEMPLATES))
                ]
                raised = _business_day(period_end, rng.randint(1, 6))
                # A locked month has nothing left open; the running close still
                # has some of its findings on the table.
                resolved = phase == "closed" or rng.random() < 0.35
                records.append(
                    {
                        **common,
                        "kind": "issue",
                        "task_ref": f"{period_end.year}{period_end.month:02d}-issue-{index + 1:02d}",
                        "task": "issue",
                        "task_label": title,
                        "area": area,
                        "area_label": AREAS[area],
                        "owner": OWNERS[rng.randrange(len(OWNERS))],
                        "planned_start_day": 0,
                        "planned_end_day": 0,
                        "planned_start_date": "",
                        "planned_end_date": "",
                        "actual_start_date": "",
                        "actual_end_date": "",
                        "actual_end_day": 0,
                        "status": "resolved" if resolved else "open",
                        "status_label": "Resolved" if resolved else "Open",
                        "is_done": resolved,
                        "is_late": False,
                        "days_late": 0,
                        "is_validated": False,
                        "validator": "",
                        "severity": severity,
                        "severity_label": SEVERITY_LABELS[severity],
                        "title": title,
                        "raised_date": raised.isoformat(),
                        "resolved_date": (
                            _business_day(period_end, rng.randint(6, 12)).isoformat()
                            if resolved
                            else ""
                        ),
                        "is_resolved": resolved,
                        "amount": 1.0,
                    }
                )

        # --- memos -------------------------------------------------------------
        for metric, label, amount in (
            (
                "close_duration_days",
                "Close duration",
                float(actual_last_day) if phase == "closed" else 0.0,
            ),
            ("planned_duration_days", "Planned duration", float(planned_duration)),
            ("open_period", "Open period", 1.0 if is_open else 0.0),
        ):
            records.append(
                {
                    **common,
                    "kind": "memo",
                    "metric": metric,
                    "metric_label": label,
                    "task_ref": "",
                    "task": "memo",
                    "task_label": label,
                    "area": "memo",
                    "area_label": "Memo",
                    "owner": "",
                    "planned_start_day": 0,
                    "planned_end_day": 0,
                    "planned_start_date": "",
                    "planned_end_date": "",
                    "actual_start_date": "",
                    "actual_end_date": "",
                    "actual_end_day": 0,
                    "status": "memo",
                    "status_label": "Memo",
                    "is_done": False,
                    "is_late": False,
                    "days_late": 0,
                    "is_validated": False,
                    "validator": "",
                    "severity": "",
                    "severity_label": "",
                    "title": label,
                    "raised_date": "",
                    "resolved_date": "",
                    "is_resolved": False,
                    "amount": amount,
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
    pages[CLOSE_PAGE_ID] = [CLOSE_RELATIVE_PATH]
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
    print(f"Generating fake close checklists for {len(entities)} entity(ies)…")

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
        out_dir = os.path.join(ENTITIES_DIR, entity_id, "financial_close")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "financial_close.json")
        tmp = f"{out_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, out_path)
        _patch_manifest(entity_id, data_version)
        print(f"  {entity_id:12s} {len(records):6d} records")

    print("Done.")


if __name__ == "__main__":
    main()
