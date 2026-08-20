"""Build dashboard roster rows from graph query results.

The preferred source is HR employment records (``find_employee_roster``).
A graph built from process data alone has none, so the roster is then derived
from the acts of working recorded for the organization: one row per person,
titled by their most recent act, active while any act is still open-ended.
"""

from __future__ import annotations

ROSTER_FIELDS = (
    "personLabel",
    "employee_id",
    "job_title",
    "job_family",
    "role",
    "hire_date",
    "status_value",
    "organizationLabel",
)


def _is_org_row(row: dict, org_label: str) -> bool:
    return org_label.strip().lower() in (row.get("orgLabel") or "").strip().lower()


def _sort_key(row: dict) -> tuple[int, str]:
    """Most recent act first: still running beats ended, then latest start."""
    return (0 if row.get("temporalEnd") else 1, str(row.get("temporalStart") or ""))


def derive_roster_rows(working_rows: list[dict], *, org_label: str) -> list[dict]:
    """One roster row per person holding an act of working at *org_label*."""
    by_person: dict[str, list[dict]] = {}
    for row in working_rows:
        person = row.get("personLabel")
        if not person or not _is_org_row(row, org_label):
            continue
        by_person.setdefault(person, []).append(row)

    roster: list[dict] = []
    for person, rows in sorted(by_person.items()):
        current = max(rows, key=_sort_key)
        starts = [row.get("temporalStart") for row in rows if row.get("temporalStart")]
        roster.append(
            {
                "personLabel": person,
                "employee_id": None,
                "job_title": current.get("jobTitle") or current.get("roleLabel"),
                "job_family": None,
                "role": current.get("role"),
                "hire_date": min(starts) if starts else None,
                "status_value": (
                    "active"
                    if any(not row.get("temporalEnd") for row in rows)
                    else "terminated"
                ),
                "organizationLabel": current.get("orgLabel"),
            }
        )
    return roster


def build_roster_rows(
    employment_rows: list[dict],
    working_rows: list[dict],
    *,
    org_label: str,
) -> tuple[list[dict], str]:
    """Return ``(rows, source)`` — HR records when the graph has them."""
    if employment_rows:
        return employment_rows, "employment_records"
    return derive_roster_rows(working_rows, org_label=org_label), "acts_of_working"
