#!/usr/bin/env python3
"""Export per-person source JSON for the personnel cockpit graph pipeline."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from naas_abi_marketplace.domains.personnel.sandbox.linkedin_experience import (
    EDUCATION,
    EMPLOYEES,
    EXPERIENCES,
    LINKEDIN_EDUCATION_URLS,
    LINKEDIN_PROFILE_URLS,
)

COCKPIT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = COCKPIT_ROOT / "data" / "source" / "person"


def _person_slug(first: str, last: str) -> str:
    return f"{first.strip().lower()}_{last.strip().lower()}".replace(" ", "_")


def _iso(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _roster_for(first: str, last: str) -> dict | None:
    for emp in EMPLOYEES:
        if emp["first"] == first and emp["last"] == last:
            return {
                "employee_id": emp["employee_id"],
                "job_title": emp["job_title"],
                "job_family": emp["job_family"],
                "hire_date": _iso(emp["hire_date"]),
                "termination_date": _iso(emp.get("termination_date")),
                "status": emp["status"],
                "remuneration_amount": emp.get("remuneration"),
                "remuneration_currency": "EUR",
            }
    return None


def _working_record(exp: dict, roster: dict | None, *, source: str | None) -> dict:
    row: dict = {
        "process_type": "ActOfWorking",
        "source": source,
        "organization": exp["organization"],
        "title": exp["title"],
        "contract_type": exp.get("contract_type"),
        "site": exp["site"],
        "start": _iso(exp["start"]),
        "end": _iso(exp.get("end")),
        "duration": exp.get("duration"),
        "mission_label": exp["mission_label"],
        "mission": exp["mission"],
        "skills": list(exp.get("skills") or []),
    }
    if roster and exp["organization"].lower().startswith("naas"):
        if roster.get("remuneration_amount") is not None:
            row["remuneration_amount"] = roster["remuneration_amount"]
            row["remuneration_currency"] = roster.get("remuneration_currency", "EUR")
    return row


def _studying_record(study: dict, *, source: str | None) -> dict:
    return {
        "process_type": "ActOfStudying",
        "source": source,
        "organization": study["organization"],
        "program": study["program"],
        "site": study["site"],
        "start": _iso(study["start"]),
        "end": _iso(study.get("end")),
        "duration": study.get("duration"),
        "skills": list(study.get("skills") or []),
        "activities": study.get("activities"),
    }


def build_person_payload(first: str, last: str) -> dict:
    full_name = f"{first} {last}"
    roster = _roster_for(first, last)
    profile_url = LINKEDIN_PROFILE_URLS.get(full_name)

    records: list[dict] = []
    for exp in EXPERIENCES:
        if exp["person"] != (first, last):
            continue
        records.append(_working_record(exp, roster, source=profile_url))

    education_url = LINKEDIN_EDUCATION_URLS.get(full_name)
    for study in EDUCATION:
        if study["person"] != (first, last):
            continue
        records.append(_studying_record(study, source=education_url))

    records.sort(key=lambda row: row.get("start") or "", reverse=True)

    return {
        "schema_version": "1.0",
        "data_version": datetime.now(UTC).strftime("%Y-%m-%d %H:%M"),
        "person": {
            "first_name": first,
            "last_name": last,
            "full_name": full_name,
            "linkedin_profile_url": profile_url,
        },
        "employment": roster,
        "records": records,
    }


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)

    for legacy in SOURCE_DIR.glob("*.json"):
        legacy.unlink()

    people: dict[tuple[str, str], None] = {}
    for exp in EXPERIENCES:
        people[exp["person"]] = None
    for study in EDUCATION:
        people[study["person"]] = None

    written: list[str] = []
    for first, last in sorted(people, key=lambda pair: (pair[1], pair[0])):
        payload = build_person_payload(first, last)
        slug = _person_slug(first, last)
        person_dir = SOURCE_DIR / slug
        person_dir.mkdir(parents=True, exist_ok=True)
        path = person_dir / "index.json"
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(f"{slug}/index.json ({len(payload['records'])} processes)")

    print(f"Wrote {len(written)} folders under {SOURCE_DIR.relative_to(COCKPIT_ROOT)}/")
    for line in written:
        print(f"  {line}")


if __name__ == "__main__":
    main()
