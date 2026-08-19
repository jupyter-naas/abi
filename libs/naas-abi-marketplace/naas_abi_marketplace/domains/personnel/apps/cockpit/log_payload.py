"""Build process-ledger rows for the Cockpit Logs page.

Each act of working or studying becomes one row: person, process, organization,
title, site, dates, and source URL. The UI renders these as a single table.
"""

from __future__ import annotations

from typing import Any

from naas_abi_marketplace.domains.personnel.individual_uri import compact_personnel

PROCESS_WORKING = "ActOfWorking"
PROCESS_STUDYING = "ActOfStudying"


def _compact(uri: str | None) -> str | None:
    if not uri:
        return None
    return compact_personnel(str(uri)) or str(uri)


def _row(
    *,
    person_label: str | None,
    process_type: str,
    process_uri: str | None,
    organization: str | None,
    title: str | None,
    site: str | None,
    start: str | None,
    end: str | None,
    duration: str | None,
    source: str | None,
) -> dict[str, Any]:
    return {
        "person_label": person_label,
        "process_type": process_type,
        "process_uri": process_uri,
        "organization": organization,
        "title": title,
        "site": site,
        "start": start,
        "end": end,
        "duration": duration,
        "source": source,
    }


def _from_working(work: dict) -> dict[str, Any] | None:
    person = work.get("personLabel")
    process_uri = _compact(work.get("working"))
    if not person or not process_uri:
        return None
    title = work.get("jobTitle") or work.get("job_title") or work.get("roleLabel")
    return _row(
        person_label=person,
        process_type=PROCESS_WORKING,
        process_uri=process_uri,
        organization=work.get("orgLabel"),
        title=title,
        site=work.get("siteLabel"),
        start=work.get("temporalStart"),
        end=work.get("temporalEnd"),
        duration=work.get("durationLabel"),
        source=work.get("sourceUrl"),
    )


def _from_studying(study: dict) -> dict[str, Any] | None:
    person = study.get("personLabel")
    process_uri = _compact(study.get("studying"))
    if not person or not process_uri:
        return None
    title = study.get("programName") or study.get("roleLabel")
    return _row(
        person_label=person,
        process_type=PROCESS_STUDYING,
        process_uri=process_uri,
        organization=study.get("orgLabel"),
        title=title,
        site=study.get("siteLabel"),
        start=study.get("temporalStart"),
        end=study.get("temporalEnd"),
        duration=None,
        source=None,
    )


def build_ledger_log_rows(
    working_rows: list[dict] | None = None,
    studying_rows: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """One ledger row per act of working or studying, newest first."""
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in working_rows or []:
        row = _from_working(item)
        if not row or row["process_uri"] in seen:
            continue
        seen.add(row["process_uri"])
        rows.append(row)
    for item in studying_rows or []:
        row = _from_studying(item)
        if not row or row["process_uri"] in seen:
            continue
        seen.add(row["process_uri"])
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row.get("start") or "",
            row.get("person_label") or "",
            row.get("title") or "",
        ),
        reverse=True,
    )
    return rows


build_ledger_log_entries = build_ledger_log_rows
