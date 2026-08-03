#!/usr/bin/env python3
"""Generate the **fake** Administration settings datasets for Financial Cockpit.

Standalone (plain stdlib, no ABI runtime). Last link of the demo-data chain:

    comptabilite/general_ledger.py ─┐
    pilotage/cost_centers.py   ─┼→ this script
    treasury/cash_position.py  ─┘

Administration is *configuration*, not finance, so these datasets are
**global** (``globals/admin/*.json``) rather than per-entity: they describe how
the instance is set up, not what a perimeter earned.

Nothing here is invented twice. Everything that already exists elsewhere is
read back rather than re-imagined, which is what keeps the settings pages
agreeing with the finance pages:

- Chart of Accounts, Journals, Fiscal Years and Accounting Periods are derived
  from the general ledger (accounts actually posted to, entries actually
  booked, periods actually locked).
- Business Units and Cost Centers are the Cost Centers roster, so the
  organization is named identically on both pages.
- Banking connectors are the Cash Position bank accounts, so the banks match.

Only the parts with no upstream — roles, permissions, workflows, API clients,
logs — are fabricated, and those are seeded so re-running is stable.

Run from the app root (after the three scripts above):
    python scripts/administration/settings.py
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta

# web/data mirrors the R2 layout the Next.js app reads from.
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_ROOT = os.path.join(APP_ROOT, "web", "data")
ENTITIES_DIR = os.path.join(DATA_ROOT, "entities")
ADMIN_DIR = os.path.join(DATA_ROOT, "globals", "admin")

DEMO_ENTITY = "_demo"
SCHEMA_VERSION = "1.0"
SEED = 20260731

# Mirrors comptabilite/general_ledger.py — the last month whose books are locked.
CLOSED_THROUGH = "2026-06-30"
# "Today" for the fabricated logs, aligned with the first open period.
NOW = datetime(2026, 7, 31, 18, 30)

YES = "✓"
NO = "—"

# French PCG account classes, keyed by the account number's leading digit.
ACCOUNT_CLASSES = {
    "1": "1 — Equity & provisions",
    "2": "2 — Fixed assets",
    "3": "3 — Inventory",
    "4": "4 — Third parties",
    "5": "5 — Financial accounts",
    "6": "6 — Expenses",
    "7": "7 — Income",
}

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# --------------------------------------------------------------------------
# IO helpers
# --------------------------------------------------------------------------

def _load_entity(relative_path: str) -> dict | None:
    path = os.path.join(ENTITIES_DIR, DEMO_ENTITY, relative_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(name: str, records: list[dict], data_version: str) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "data_version": data_version,
        "records": records,
    }
    os.makedirs(ADMIN_DIR, exist_ok=True)
    out_path = os.path.join(ADMIN_DIR, f"{name}.json")
    tmp = f"{out_path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, out_path)
    print(f"  {name:22s} {len(records):4d} records")


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M")


def _round(value: float) -> float:
    return round(value + 0.0, 2)


# --------------------------------------------------------------------------
# Organizations — read back from the Cost Centers roster
# --------------------------------------------------------------------------

BU_MANAGERS = {
    "commercial": "Camille Fournier",
    "product": "Adrien Lemaitre",
    "operations": "Nadia Berger",
    "corporate": "Hélène Vasseur",
}

CC_OWNERS = {
    "sales": "Camille Fournier",
    "marketing": "Yanis Roux",
    "customer_success": "Léa Moreau",
    "engineering": "Adrien Lemaitre",
    "product": "Sofia Marchetti",
    "infrastructure": "Thomas Klein",
    "operations": "Nadia Berger",
    "supply_chain": "Marc Delaunay",
    "finance": "Hélène Vasseur",
    "people": "Inès Bakker",
    "legal": "Julien Perrot",
}


def _cost_center_facts(cost_centers: dict) -> tuple[list[dict], list[dict]]:
    """Latest-month roster + fiscal-year totals, per cost center and per BU."""
    records = [r for r in cost_centers.get("records", []) if r.get("cost_center")]
    if not records:
        return [], []

    fiscal_year = max(r["period"][:4] for r in records)
    latest_period = max(r["period"] for r in records if r["period"][:4] == fiscal_year)

    per_cc: dict[str, dict] = {}
    for record in records:
        key = record["cost_center"]
        slot = per_cc.setdefault(
            key,
            {
                "label": record["cost_center_label"],
                "division": record["division"],
                "division_label": record["division_label"],
                "budget": 0.0,
                "actual": 0.0,
                "headcount": 0,
            },
        )
        if record["period"][:4] == fiscal_year:
            slot["budget"] += record.get("budget", 0.0)
            slot["actual"] += record.get("actual", 0.0)
        if record["period"] == latest_period:
            slot["headcount"] = int(record.get("headcount", 0))

    cc_rows: list[dict] = []
    for index, (key, slot) in enumerate(sorted(per_cc.items(), key=lambda kv: kv[1]["label"])):
        cc_rows.append(
            {
                "code": f"CC-{1000 + index * 10}",
                "label": slot["label"],
                "business_unit": slot["division_label"],
                "owner": CC_OWNERS.get(key, "—"),
                "headcount": slot["headcount"],
                "annual_budget": _round(slot["budget"]),
                "annual_actual": _round(slot["actual"]),
                "fiscal_year": fiscal_year,
                "status": "Active",
            }
        )

    per_bu: dict[str, dict] = {}
    for key, slot in per_cc.items():
        bu = per_bu.setdefault(
            slot["division"],
            {
                "label": slot["division_label"],
                "budget": 0.0,
                "actual": 0.0,
                "headcount": 0,
                "cost_centers": 0,
            },
        )
        bu["budget"] += slot["budget"]
        bu["actual"] += slot["actual"]
        bu["headcount"] += slot["headcount"]
        bu["cost_centers"] += 1

    bu_rows: list[dict] = []
    for index, (key, slot) in enumerate(sorted(per_bu.items(), key=lambda kv: kv[1]["label"])):
        bu_rows.append(
            {
                "code": f"BU-{100 + index * 10}",
                "label": slot["label"],
                "parent": "Demo Company",
                "manager": BU_MANAGERS.get(key, "—"),
                "cost_centers": slot["cost_centers"],
                "headcount": slot["headcount"],
                "annual_budget": _round(slot["budget"]),
                "annual_actual": _round(slot["actual"]),
                "fiscal_year": fiscal_year,
                "status": "Active",
            }
        )
    return bu_rows, cc_rows


# --------------------------------------------------------------------------
# Users & Roles
# --------------------------------------------------------------------------

PERMISSIONS = [
    ("page.view", "View pages", "Data", "Open the perimeters and pages granted to the user"),
    ("data.export", "Export data", "Data", "Download any visible table as CSV or Excel"),
    ("invoice.annotate", "Annotate invoices", "Data", "Attach comments and follow-up notes to invoices"),
    ("pnl.adjust", "Post adjustment entries", "Accounting", "Create and edit income-statement adjustments"),
    ("budget.edit", "Edit budgets", "Planning", "Enter and revise budget lines"),
    ("journal.validate", "Validate journal entries", "Accounting", "Approve manual entries before posting"),
    ("close.run", "Run the financial close", "Accounting", "Tick close tasks and lock an accounting period"),
    ("entity.manage", "Manage entities", "Administration", "Create, rename and archive perimeters"),
    ("user.manage", "Manage users", "Administration", "Invite users and set their scope"),
    ("role.manage", "Manage roles", "Administration", "Define roles and their permission set"),
    ("integration.manage", "Manage integrations", "Administration", "Connect and reconfigure external systems"),
    ("audit.read", "Read audit logs", "Audit", "Consult activity, system and synchronization logs"),
    ("theme.edit", "Edit the theme", "Administration", "Change colours, typography and branding"),
]

ROLES = [
    ("owner", "Owner", "Global", "Root identity declared in config.yaml — full access, never editable from the app.", "all"),
    ("admin", "Admin", "Global", "Full access to every perimeter and every administration screen.", "all"),
    ("finance_manager", "Finance Manager", "Perimeter", "Owns the numbers: closes periods, validates entries, revises budgets.", [
        "page.view", "data.export", "invoice.annotate", "pnl.adjust", "budget.edit",
        "journal.validate", "close.run", "audit.read",
    ]),
    ("controller", "Controller", "Perimeter", "Steers budget and forecast without touching the ledger lock.", [
        "page.view", "data.export", "invoice.annotate", "pnl.adjust", "budget.edit",
    ]),
    ("accountant", "Accountant", "Perimeter", "Prepares entries and the close checklist; validation sits above.", [
        "page.view", "data.export", "invoice.annotate", "pnl.adjust", "close.run",
    ]),
    ("analyst", "Analyst", "Perimeter", "Reads and extracts; changes nothing.", [
        "page.view", "data.export",
    ]),
    ("viewer", "Viewer", "Perimeter", "Reads the pages explicitly granted to them.", [
        "page.view",
    ]),
    ("auditor", "Auditor", "Global", "Read-only across every perimeter, plus the audit trail.", [
        "page.view", "data.export", "audit.read",
    ]),
]

ROLE_USER_COUNTS = {
    "owner": 1,
    "admin": 2,
    "finance_manager": 3,
    "controller": 4,
    "accountant": 5,
    "analyst": 7,
    "viewer": 12,
    "auditor": 2,
}


def _granted(role_permissions, permission: str) -> bool:
    return role_permissions == "all" or permission in role_permissions


def _roles_and_permissions() -> tuple[list[dict], list[dict]]:
    all_permissions = [p[0] for p in PERMISSIONS]

    role_rows = []
    for key, label, scope, description, permissions in ROLES:
        granted = all_permissions if permissions == "all" else permissions
        role_rows.append(
            {
                "role": label,
                "key": key,
                "scope": scope,
                "description": description,
                "permissions": len(granted),
                "users": ROLE_USER_COUNTS.get(key, 0),
                "managed_in": "config.yaml" if key == "owner" else "Application",
                "status": "Protected" if key == "owner" else "Active",
            }
        )

    permission_rows = []
    for key, label, category, description in PERMISSIONS:
        row = {
            "permission": key,
            "label": label,
            "category": category,
            "description": description,
        }
        granted_to = 0
        for role_key, role_label, _scope, _desc, role_permissions in ROLES:
            allowed = _granted(role_permissions, key)
            row[role_key] = YES if allowed else NO
            granted_to += 1 if allowed else 0
        row["roles"] = granted_to
        permission_rows.append(row)

    return role_rows, permission_rows


# --------------------------------------------------------------------------
# Accounting settings — read back from the general ledger
# --------------------------------------------------------------------------

JOURNAL_TYPES = {
    "VE": ("Sales", "Automatic"),
    "AC": ("Purchases", "Automatic"),
    "PA": ("Payroll", "Automatic"),
    "BQ": ("Bank", "Automatic"),
    "OD": ("Miscellaneous", "Manual"),
}


def _accounting_from_ledger(ledger: dict) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    lines = [r for r in ledger.get("records", []) if r.get("kind") == "line"]

    accounts: dict[str, dict] = {}
    journals: dict[str, dict] = {}
    periods: dict[str, dict] = {}

    for line in lines:
        account = accounts.setdefault(
            line["account"],
            {
                "label": line["account_label"],
                "type": line["account_type"],
                "debit": 0.0,
                "credit": 0.0,
                "lines": 0,
                "journals": set(),
                "last_entry": "",
            },
        )
        account["debit"] += line.get("debit", 0.0)
        account["credit"] += line.get("credit", 0.0)
        account["lines"] += 1
        account["journals"].add(line["journal_code"])
        account["last_entry"] = max(account["last_entry"], line["entry_date"])

        journal = journals.setdefault(
            line["journal_code"],
            {
                "label": line["journal_label"],
                "debit": 0.0,
                "credit": 0.0,
                "lines": 0,
                "entries": set(),
                "accounts": set(),
                "last_entry": "",
            },
        )
        journal["debit"] += line.get("debit", 0.0)
        journal["credit"] += line.get("credit", 0.0)
        journal["lines"] += 1
        journal["entries"].add(line["entry_ref"])
        journal["accounts"].add(line["account"])
        journal["last_entry"] = max(journal["last_entry"], line["entry_date"])

        period = periods.setdefault(
            line["period"],
            {"debit": 0.0, "credit": 0.0, "lines": 0, "entries": set(), "manual": set()},
        )
        period["debit"] += line.get("debit", 0.0)
        period["credit"] += line.get("credit", 0.0)
        period["lines"] += 1
        period["entries"].add(line["entry_ref"])
        if line.get("source") == "manual":
            period["manual"].add(line["entry_ref"])

    account_rows = []
    for number in sorted(accounts):
        slot = accounts[number]
        account_rows.append(
            {
                "account": number,
                "label": slot["label"],
                "account_class": ACCOUNT_CLASSES.get(number[0], "—"),
                "account_type": slot["type"].capitalize(),
                "journals": ", ".join(sorted(slot["journals"])),
                "lines": slot["lines"],
                "debit": _round(slot["debit"]),
                "credit": _round(slot["credit"]),
                "balance": _round(slot["debit"] - slot["credit"]),
                "last_entry": slot["last_entry"],
                "status": "Active",
            }
        )

    journal_rows = []
    for code in sorted(journals):
        slot = journals[code]
        journal_type, posting = JOURNAL_TYPES.get(code, (slot["label"], "Automatic"))
        journal_rows.append(
            {
                "journal_code": code,
                "label": slot["label"],
                "journal_type": journal_type,
                "posting": posting,
                "accounts": len(slot["accounts"]),
                "entries": len(slot["entries"]),
                "lines": slot["lines"],
                "debit": _round(slot["debit"]),
                "credit": _round(slot["credit"]),
                "last_entry": slot["last_entry"],
                "status": "Active",
            }
        )

    period_rows = []
    for period in sorted(periods):
        slot = periods[period]
        year, month = period[:4], int(period[5:7])
        closed = period <= CLOSED_THROUGH
        period_rows.append(
            {
                "period": period[:7],
                "label": f"{MONTH_LABELS[month]} {year}",
                "fiscal_year": year,
                "start_date": f"{year}-{month:02d}-01",
                "end_date": period,
                "entries": len(slot["entries"]),
                "lines": slot["lines"],
                "manual_entries": len(slot["manual"]),
                "debit": _round(slot["debit"]),
                "status": "Closed" if closed else "Open",
                "locked_on": period if closed else "—",
            }
        )

    year_rows = []
    for year in sorted({row["fiscal_year"] for row in period_rows}):
        months = [row for row in period_rows if row["fiscal_year"] == year]
        closed_months = [row for row in months if row["status"] == "Closed"]
        year_rows.append(
            {
                "fiscal_year": year,
                "start_date": f"{year}-01-01",
                "end_date": f"{year}-12-31",
                "periods": len(months),
                "closed_periods": len(closed_months),
                "entries": sum(row["entries"] for row in months),
                "lines": sum(row["lines"] for row in months),
                "debit": _round(sum(row["debit"] for row in months)),
                "status": "Closed" if len(closed_months) == len(months) else "Open",
                "closed_on": max((row["end_date"] for row in closed_months), default="—"),
            }
        )

    return account_rows, year_rows, period_rows, journal_rows


# --------------------------------------------------------------------------
# Workflows
# --------------------------------------------------------------------------

APPROVAL_FLOWS = [
    ("Supplier invoice approval", "Supplier invoice", "Invoice received", 5_000, 2,
     "Cost center owner → Finance Manager", 3, "Yes", "Active"),
    ("Supplier invoice — high value", "Supplier invoice", "Amount above threshold", 50_000, 3,
     "Cost center owner → Finance Manager → CFO", 5, "Yes", "Active"),
    ("Purchase order release", "Purchase order", "Order submitted", 10_000, 2,
     "Business unit manager → Procurement", 2, "Yes", "Active"),
    ("Expense claim", "Expense claim", "Claim submitted", 0, 1,
     "Line manager", 5, "No", "Active"),
    ("Manual journal entry", "Journal entry", "Entry prepared", 0, 1,
     "Finance Manager", 1, "Yes", "Active"),
    ("Payment run release", "Payment run", "Run prepared", 0, 2,
     "Treasurer → CFO", 1, "No", "Active"),
    ("Budget revision", "Budget", "Revision submitted", 25_000, 2,
     "Controller → CFO", 5, "No", "Active"),
    ("Period lock", "Accounting period", "Close checklist complete", 0, 1,
     "Finance Manager", 2, "No", "Draft"),
]

NOTIFICATIONS = [
    ("Invoice awaiting approval", "Approval requested", "Email", "Assigned approver", "Immediate", "Active"),
    ("Approval overdue", "SLA breached", "Email + in-app", "Approver, Finance Manager", "Daily at 08:00", "Active"),
    ("Payment run released", "Payment run approved", "Email", "Treasury team", "Immediate", "Active"),
    ("Bank feed failure", "Synchronization failed", "Email + in-app", "Administrators", "Immediate", "Active"),
    ("Period ready to close", "Close checklist complete", "In-app", "Finance Manager", "Immediate", "Active"),
    ("Close deadline approaching", "Two business days to deadline", "Email", "Close owners", "Daily at 08:00", "Active"),
    ("Unbalanced entry rejected", "Validation rule blocked a posting", "In-app", "Preparer", "Immediate", "Active"),
    ("Weekly cash digest", "Scheduled report", "Email", "CFO, Treasury team", "Monday at 07:00", "Active"),
    ("Monthly management report", "Scheduled report", "Email", "Executive committee", "5th business day", "Active"),
    ("New user invited", "User created", "Email", "Invited user", "Immediate", "Active"),
    ("Role changed", "Permissions updated", "In-app", "Administrators", "Immediate", "Paused"),
]

VALIDATION_RULES = [
    ("Entry must balance", "Journal entry", "Blocking", "Total debit ≠ total credit", "Reject the posting", 0, "Active"),
    ("Closed period is locked", "Journal entry", "Blocking", "Entry date falls in a closed period", "Reject the posting", 4, "Active"),
    ("Account must be active", "Journal entry", "Blocking", "Account is archived in the chart of accounts", "Reject the posting", 1, "Active"),
    ("Cost center required on expenses", "Journal entry", "Blocking", "Class 6 line without a cost center", "Reject the posting", 12, "Active"),
    ("Invoice needs a purchase order", "Supplier invoice", "Warning", "Amount above €10,000 with no matching PO", "Warn and route for approval", 7, "Active"),
    ("Duplicate invoice number", "Supplier invoice", "Blocking", "Same supplier and invoice number already booked", "Reject the import", 2, "Active"),
    ("VAT rate consistency", "Supplier invoice", "Warning", "VAT amount deviates from the rate by more than 1%", "Warn the preparer", 9, "Active"),
    ("Budget overrun", "Budget", "Warning", "Committed spend above 100% of the annual budget", "Warn and notify the controller", 5, "Active"),
    ("Bank reconciliation gap", "Bank statement", "Warning", "Statement balance ≠ ledger balance", "Raise a close task", 3, "Active"),
    ("Payment above mandate", "Payment run", "Blocking", "Payment exceeds the signatory mandate", "Escalate to the CFO", 1, "Draft"),
]


def _workflow_rows() -> tuple[list[dict], list[dict], list[dict]]:
    flows = [
        {
            "flow": flow,
            "object": obj,
            "trigger": trigger,
            "threshold": threshold,
            "steps": steps,
            "approvers": approvers,
            "sla_days": sla,
            "auto_escalation": escalation,
            "status": status,
        }
        for flow, obj, trigger, threshold, steps, approvers, sla, escalation, status in APPROVAL_FLOWS
    ]
    notifications = [
        {
            "notification": name,
            "event": event,
            "channel": channel,
            "recipients": recipients,
            "frequency": frequency,
            "status": status,
        }
        for name, event, channel, recipients, frequency, status in NOTIFICATIONS
    ]
    rules = [
        {
            "rule": rule,
            "scope": scope,
            "severity": severity,
            "condition": condition,
            "action": action,
            "triggered_30d": triggered,
            "status": status,
        }
        for rule, scope, severity, condition, action, triggered, status in VALIDATION_RULES
    ]
    return flows, notifications, rules


# --------------------------------------------------------------------------
# Integrations
# --------------------------------------------------------------------------

ERP_CONNECTORS = [
    ("Pennylane — General ledger", "Pennylane", "Production", "Journal entries, chart of accounts", "Inbound", "Every hour"),
    ("Pennylane — Supplier invoices", "Pennylane", "Production", "Supplier invoices, payment status", "Inbound", "Every hour"),
    ("Pennylane — Customer invoices", "Pennylane", "Production", "Customer invoices, collections", "Inbound", "Every hour"),
    ("Payfit — Payroll journal", "Payfit", "Production", "Payroll entries, headcount", "Inbound", "Monthly"),
    ("Spendesk — Expense claims", "Spendesk", "Production", "Expense claims, card spend", "Inbound", "Every 4 hours"),
    ("NetSuite — Fixed assets", "NetSuite", "Sandbox", "Asset register, depreciation", "Inbound", "Daily at 02:00"),
    ("Cockpit → Data warehouse", "BigQuery", "Production", "All published datasets", "Outbound", "Daily at 05:00"),
]

API_CLIENTS = [
    ("Data warehouse loader", "fc_live_7f2a", "read:datasets", "Production", 600),
    ("Executive mobile app", "fc_live_b41c", "read:datasets, read:entities", "Production", 300),
    ("Close automation bot", "fc_live_c93d", "read:datasets, write:close", "Production", 120),
    ("Budget import job", "fc_live_1e88", "write:budget", "Production", 60),
    ("Partner sandbox", "fc_test_a057", "read:datasets", "Sandbox", 60),
    ("Legacy reporting script", "fc_live_44be", "read:datasets", "Production", 60),
]

IMPORT_EXPORT_JOBS = [
    ("Budget import", "Import", "Excel (.xlsx)", "Budget lines", "On demand"),
    ("Adjustment entries import", "Import", "CSV", "Income statement adjustments", "On demand"),
    ("Bank statement import", "Import", "CAMT.053", "Bank accounts", "Daily at 07:00"),
    ("Supplier master import", "Import", "CSV", "Suppliers referential", "Weekly on Monday"),
    ("General ledger export", "Export", "CSV", "Data warehouse", "Daily at 05:00"),
    ("Trial balance export", "Export", "Excel (.xlsx)", "Statutory auditor", "Monthly on the 5th"),
    ("FEC export", "Export", "FEC (tax authority)", "Statutory archive", "Yearly"),
    ("Management report pack", "Export", "PDF", "Executive committee", "Monthly on the 5th"),
]


def _integration_rows(bank_accounts: dict | None, rng: random.Random) -> tuple[
    list[dict], list[dict], list[dict], list[dict]
]:
    erp = []
    for index, (name, system, env, scope, direction, frequency) in enumerate(ERP_CONNECTORS):
        failed = name.startswith("NetSuite")
        last_sync = NOW - timedelta(hours=rng.randint(1, 30) + index)
        erp.append(
            {
                "connector": name,
                "system": system,
                "environment": env,
                "scope": scope,
                "direction": direction,
                "frequency": frequency,
                "last_sync": _iso(last_sync),
                "records_30d": rng.randint(1_200, 48_000),
                "status": "Error" if failed else "Connected",
            }
        )

    banking = []
    if bank_accounts:
        seen: dict[tuple[str, str, str], dict] = {}
        for record in bank_accounts.get("records", []):
            bank = record.get("bank")
            if not bank or record.get("kind") == "memo":
                continue
            key = (bank, record.get("country_label", ""), record.get("currency", ""))
            slot = seen.setdefault(key, {"accounts": set(), "country": record.get("country_label", "")})
            slot["accounts"].add(record.get("account"))
        for index, (key, slot) in enumerate(sorted(seen.items())):
            bank, country, currency = key
            stale = bank == "Revolut"
            banking.append(
                {
                    "connector": f"{bank} — {currency}",
                    "bank": bank,
                    "country": country,
                    "currency": currency,
                    "protocol": "EBICS T" if bank in {"BNP Paribas", "Société Générale"} else "Open Banking API",
                    "accounts": len(slot["accounts"]),
                    "frequency": "Every 4 hours" if not stale else "Daily at 06:00",
                    "last_sync": _iso(NOW - timedelta(hours=rng.randint(2, 8) if not stale else 51)),
                    "status": "Stale" if stale else "Connected",
                }
            )

    api = []
    for name, prefix, scopes, env, rate_limit in API_CLIENTS:
        idle = name.startswith("Legacy")
        api.append(
            {
                "client": name,
                "key_prefix": f"{prefix}••••",
                "scopes": scopes,
                "environment": env,
                "rate_limit_per_min": rate_limit,
                "created_on": _iso(NOW - timedelta(days=rng.randint(90, 700)))[:10],
                "last_used": _iso(NOW - timedelta(days=rng.randint(120, 200) if idle else 0,
                                                 hours=rng.randint(1, 20))),
                "calls_30d": 0 if idle else rng.randint(2_000, 190_000),
                "status": "Idle" if idle else "Active",
            }
        )

    jobs = []
    for name, direction, fmt, target, schedule in IMPORT_EXPORT_JOBS:
        rows = rng.randint(40, 9_000)
        failed = name.startswith("Supplier master")
        jobs.append(
            {
                "job": name,
                "direction": direction,
                "format": fmt,
                "target": target,
                "schedule": schedule,
                "last_run": _iso(NOW - timedelta(hours=rng.randint(2, 96))),
                "rows": rows,
                "duration_s": round(rng.uniform(1.5, 95.0), 1),
                "status": "Failed" if failed else "Succeeded",
            }
        )

    return erp, banking, api, jobs


# --------------------------------------------------------------------------
# Audit logs
# --------------------------------------------------------------------------

LOG_EVENTS = [
    ("INFO", "scheduler", "job.completed", "Scheduled job '{job}' completed"),
    ("INFO", "datastore", "dataset.published", "Dataset '{dataset}' published for perimeter demo"),
    ("INFO", "auth", "session.created", "Session opened for {actor}"),
    ("INFO", "api", "request.served", "GET /api/entities/demo/data served"),
    ("WARN", "connector", "sync.retried", "Connector '{job}' retried after a timeout"),
    ("WARN", "datastore", "cache.miss", "Manifest cache miss for perimeter demo"),
    ("ERROR", "connector", "sync.failed", "Connector '{job}' failed: upstream returned 502"),
    ("INFO", "close", "period.locked", "Accounting period locked"),
    ("INFO", "theme", "theme.saved", "Theme configuration saved by {actor}"),
    ("WARN", "auth", "login.rejected", "Rejected sign-in attempt"),
]

LOG_JOBS = [
    "Pennylane — General ledger",
    "Bank statement import",
    "General ledger export",
    "NetSuite — Fixed assets",
    "Cockpit → Data warehouse",
    "Payfit — Payroll journal",
]

LOG_DATASETS = [
    "accounting/general_ledger",
    "cash_flow/cash_flow",
    "balance_sheet/balance_sheet",
    "cost_centers/cost_centers",
    "financial_close/financial_close",
]

LOG_ACTORS = [
    "demo@financial-cockpit.local",
    "camille.fournier@demo.local",
    "helene.vasseur@demo.local",
    "system",
    "integration",
]


def _log_rows(rng: random.Random) -> tuple[list[dict], list[dict]]:
    system_logs = []
    moment = NOW
    for _ in range(160):
        level, component, event, template = rng.choice(LOG_EVENTS)
        actor = "system" if component in {"scheduler", "connector", "datastore"} else rng.choice(LOG_ACTORS)
        message = template.format(
            job=rng.choice(LOG_JOBS),
            dataset=rng.choice(LOG_DATASETS),
            actor=actor,
        )
        system_logs.append(
            {
                "timestamp": _iso(moment),
                "level": level,
                "component": component,
                "event": event,
                "message": message,
                "actor": actor,
                "duration_ms": rng.randint(4, 9_400),
            }
        )
        moment -= timedelta(minutes=rng.randint(11, 190))

    connectors = (
        [name for name, *_ in ERP_CONNECTORS]
        + ["BNP Paribas — EUR", "Société Générale — EUR", "HSBC — GBP", "Revolut — EUR"]
        + [job for job, *_ in IMPORT_EXPORT_JOBS]
    )
    sync_history = []
    moment = NOW
    for _ in range(120):
        connector = rng.choice(connectors)
        direction = "Outbound" if "→" in connector or "export" in connector.lower() else "Inbound"
        records = rng.randint(0, 12_000)
        failed = rng.random() < 0.08
        errors = rng.randint(1, 40) if failed else 0
        created = 0 if failed else int(records * rng.uniform(0.02, 0.25))
        updated = 0 if failed else records - created
        sync_history.append(
            {
                "started_at": _iso(moment),
                "connector": connector,
                "sync_type": "Full" if rng.random() < 0.12 else "Incremental",
                "direction": direction,
                "records": 0 if failed else records,
                "created": created,
                "updated": updated,
                "errors": errors,
                "duration_s": round(rng.uniform(0.8, 320.0), 1),
                "status": "Failed" if failed else "Succeeded",
            }
        )
        moment -= timedelta(minutes=rng.randint(25, 260))

    return system_logs, sync_history


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> None:
    rng = random.Random(SEED)
    data_version = datetime.now().strftime("%Y-%m-%d %H:%M")

    ledger = _load_entity(os.path.join("accounting", "general_ledger.json"))
    cost_centers = _load_entity(os.path.join("cost_centers", "cost_centers.json"))
    bank_accounts = _load_entity(os.path.join("cash_position", "bank_accounts.json"))

    if ledger is None or cost_centers is None:
        raise SystemExit(
            "Missing upstream demo data — run comptabilite/general_ledger.py and "
            "pilotage/cost_centers.py first (or `make demo-data`)."
        )

    print("Generating fake administration settings…")

    business_units, cc_rows = _cost_center_facts(cost_centers)
    _write("business_units", business_units, data_version)
    _write("cost_centers", cc_rows, data_version)

    roles, permissions = _roles_and_permissions()
    _write("roles", roles, data_version)
    _write("permissions", permissions, data_version)

    accounts, fiscal_years, periods, journals = _accounting_from_ledger(ledger)
    _write("chart_of_accounts", accounts, data_version)
    _write("fiscal_years", fiscal_years, data_version)
    _write("accounting_periods", periods, data_version)
    _write("journals", journals, data_version)

    flows, notifications, rules = _workflow_rows()
    _write("approval_flows", flows, data_version)
    _write("notifications", notifications, data_version)
    _write("validation_rules", rules, data_version)

    erp, banking, api, jobs = _integration_rows(bank_accounts, rng)
    _write("integrations_erp", erp, data_version)
    _write("integrations_banking", banking, data_version)
    _write("integrations_api", api, data_version)
    _write("imports_exports", jobs, data_version)

    system_logs, sync_history = _log_rows(rng)
    _write("system_logs", system_logs, data_version)
    _write("sync_history", sync_history, data_version)

    print("Done.")


if __name__ == "__main__":
    main()
