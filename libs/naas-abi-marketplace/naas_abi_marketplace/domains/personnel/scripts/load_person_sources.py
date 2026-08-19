"""Load personnel demo inputs from ``apps/cockpit/data/source/person/*/index.json``."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

PERSONNEL_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PERSONNEL_ROOT / "apps" / "cockpit" / "data" / "source" / "person"


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
    employees: list[dict] = []
    for payload in payloads:
        employment = payload.get("employment")
        person = payload["person"]
        if not employment:
            continue
        employees.append(
            {
                "first": person["first_name"],
                "last": person["last_name"],
                "employee_id": employment["employee_id"],
                "job_title": employment["job_title"],
                "job_family": employment["job_family"],
                "hire_date": _parse_date(employment["hire_date"]),
                "termination_date": _parse_date(employment.get("termination_date")),
                "status": employment["status"],
                "remuneration": employment.get("remuneration_amount"),
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
