"""Load personnel demo inputs from ``data/demo/person/*/index.json``.

The JSON files are the committed source of truth for the demo graph: each
folder holds one person, their HR ``roster`` block, and their process records
(``ActOfWorking`` / ``ActOfStudying``).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from naas_abi_marketplace.domains.personnel.paths import DEMO_SOURCE_DIR

SOURCE_DIR = DEMO_SOURCE_DIR


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def load_person_sources(source_dir: Path | None = None) -> list[dict]:
    root = source_dir or SOURCE_DIR
    payloads: list[dict] = []
    for path in sorted(root.glob("*/index.json")):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    if not payloads:
        raise FileNotFoundError(f"No person sources under {root}/<slug>/index.json")
    return payloads


def sources_to_employees(payloads: list[dict]) -> list[dict]:
    """Roster rows (one per person) from the ``roster`` block of each payload."""
    seen: set[tuple[str, str]] = set()
    employees: list[dict] = []
    for payload in payloads:
        person = payload["person"]
        key = (person["first_name"], person["last_name"])
        if key in seen:
            continue
        roster = payload.get("roster")
        if not roster:
            continue
        seen.add(key)
        employees.append(
            {
                "first": key[0],
                "last": key[1],
                "employee_id": roster["employee_id"],
                "job_title": roster["job_title"],
                "job_family": roster["job_family"],
                "hire_date": _parse_date(roster["hire_date"]),
                "termination_date": _parse_date(roster.get("termination_date")),
                "status": roster["status"],
                "remuneration": roster.get("remuneration_amount"),
            }
        )
    return employees


def sources_to_profile_urls(payloads: list[dict]) -> dict[str, str]:
    urls: dict[str, str] = {}
    for payload in payloads:
        person = payload["person"]
        full_name = person["full_name"]
        url = person.get("linkedin_profile_url")
        if full_name and url:
            urls[full_name] = url
    return urls


def sources_to_experiences(payloads: list[dict]) -> list[dict]:
    experiences: list[dict] = []
    for payload in payloads:
        person = payload["person"]
        person_tuple = (person["first_name"], person["last_name"])
        for record in payload.get("records") or []:
            process_type = record.get("process_type")
            if process_type == "ActOfStudying":
                experiences.append(
                    {
                        "kind": "studying",
                        "person": person_tuple,
                        "organization": record["organization"],
                        "program": record["program"],
                        "site": record["site"],
                        "start": _parse_date(record["start"]),
                        "end": _parse_date(record.get("end")),
                        "duration": record.get("duration"),
                        "source": record.get("source"),
                        "skills": list(record.get("skills") or []),
                        "activities": record.get("activities"),
                    }
                )
                continue
            if process_type != "ActOfWorking":
                continue
            experiences.append(
                {
                    "kind": "working",
                    "person": person_tuple,
                    "organization": record["organization"],
                    "title": record["title"],
                    "contract_type": record.get("contract_type"),
                    "site": record["site"],
                    "start": _parse_date(record["start"]),
                    "end": _parse_date(record.get("end")),
                    "duration": record.get("duration"),
                    "mission_label": record["mission_label"],
                    "mission": record["mission"],
                    "skills": list(record.get("skills") or []),
                    "remuneration_amount": record.get("remuneration_amount"),
                    "remuneration_currency": record.get("remuneration_currency") or "EUR",
                }
            )
    return experiences
