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
                        "organization": record.get("organization"),
                        "program": record["program"],
                        "site": record.get("site"),
                        "start": _parse_date(record.get("start")),
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
                    "site": record.get("site"),
                    "start": _parse_date(record.get("start")),
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


def payload_to_profile_source_parameters(payload: dict) -> object:
    """Build ``ProfileFromSourcePipelineParameters`` from one demo ``index.json``."""
    from naas_abi_marketplace.domains.personnel.pipelines.PersonProfilePipeline import (
        CertificationInput,
        InterestInput,
        LanguageInput,
        RecommendationInput,
    )
    from naas_abi_marketplace.domains.personnel.pipelines.profile_from_source import (
        ProfileBlockInput,
        ProfileFromSourcePipelineParameters,
        SourcePersonInput,
        StudyingRecordInput,
        WorkingRecordInput,
    )

    person = payload["person"]
    records: list[WorkingRecordInput | StudyingRecordInput] = []
    for record in payload.get("records") or []:
        process_type = record.get("process_type")
        # A source that does not state when a record began still describes a
        # real role or course of study, so `start` is read like any other
        # optional field rather than required.
        start = _parse_date(record.get("start"))
        end = _parse_date(record.get("end"))
        if process_type == "ActOfStudying":
            records.append(
                StudyingRecordInput(
                    organization=record.get("organization"),
                    program=record["program"],
                    site=record.get("site"),
                    start=start,
                    end=end,
                    duration=record.get("duration"),
                    skills=list(record.get("skills") or []),
                    activities=record.get("activities"),
                    source=record.get("source"),
                )
            )
            continue
        if process_type == "ActOfWorking":
            records.append(
                WorkingRecordInput(
                    organization=record["organization"],
                    title=record["title"],
                    site=record.get("site"),
                    start=start,
                    end=end,
                    duration=record.get("duration"),
                    mission_label=record["mission_label"],
                    mission=record["mission"],
                    contract_type=record.get("contract_type"),
                    skills=list(record.get("skills") or []),
                    source=record.get("source"),
                    remuneration_amount=record.get("remuneration_amount"),
                    remuneration_currency=record.get("remuneration_currency") or "EUR",
                )
            )

    profile_block = None
    raw_profile = payload.get("profile")
    if raw_profile:
        location = raw_profile.get("location") or {}
        profile_block = ProfileBlockInput(
            slug=raw_profile.get("slug"),
            headline=raw_profile.get("headline"),
            about=raw_profile.get("about"),
            quote=raw_profile.get("quote"),
            years_of_experience=raw_profile.get("years_of_experience"),
            organization=raw_profile.get("organization"),
            service_line=raw_profile.get("service_line"),
            grade=raw_profile.get("grade"),
            office=location.get("office"),
            city=location.get("city"),
            country=location.get("country"),
            country_code=location.get("country_code"),
            photo_url=raw_profile.get("photo_url"),
            photo_path=raw_profile.get("photo_path"),
            skills=list(raw_profile.get("skills") or []),
            certifications=[
                CertificationInput.model_validate(item)
                for item in (raw_profile.get("certifications") or [])
            ],
            languages=[
                LanguageInput.model_validate(item)
                for item in (raw_profile.get("languages") or [])
            ],
            interests=[
                InterestInput.model_validate(item)
                for item in (raw_profile.get("interests") or [])
            ],
            recommendations=[
                RecommendationInput.model_validate(item)
                for item in (raw_profile.get("recommendations") or [])
            ],
        )

    return ProfileFromSourcePipelineParameters(
        person=SourcePersonInput(
            first_name=person["first_name"],
            last_name=person["last_name"],
            linkedin_profile_url=person.get("linkedin_profile_url"),
            email=person.get("email"),
            phone=person.get("phone"),
            linkedin_url=person.get("linkedin_url"),
        ),
        records=records,
        profile=profile_block,
    )


def sources_to_profiles(payloads: list[dict]) -> list[dict]:
    """Person-level profile blocks, one per person that carries a ``profile``.

    A person with no ``profile`` block yields nothing: the directory then shows
    them with their name and whatever their acts of working say, which is what
    the source supports. Sections absent from the block stay absent - an empty
    list here means the source says there are none, and the app says so.
    """
    profiles: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for payload in payloads:
        person = payload["person"]
        key = (person["first_name"], person["last_name"])
        profile = payload.get("profile")
        if not profile or key in seen:
            continue
        seen.add(key)
        location = profile.get("location") or {}
        profiles.append(
            {
                "first": key[0],
                "last": key[1],
                "slug": profile.get("slug"),
                "email": person.get("email"),
                "phone": person.get("phone"),
                "linkedin_url": person.get("linkedin_url"),
                "headline": profile.get("headline"),
                "about": profile.get("about"),
                "quote": profile.get("quote"),
                "years_of_experience": profile.get("years_of_experience"),
                "organization": profile.get("organization"),
                "service_line": profile.get("service_line"),
                "grade": profile.get("grade"),
                "office": location.get("office"),
                "city": location.get("city"),
                "country": location.get("country"),
                "country_code": location.get("country_code"),
                "photo_url": profile.get("photo_url"),
                "photo_path": profile.get("photo_path"),
                "skills": list(profile.get("skills") or []),
                "source_url": person.get("linkedin_profile_url"),
                "certifications": list(profile.get("certifications") or []),
                "languages": list(profile.get("languages") or []),
                "interests": list(profile.get("interests") or []),
                "recommendations": list(profile.get("recommendations") or []),
            }
        )
    return profiles
