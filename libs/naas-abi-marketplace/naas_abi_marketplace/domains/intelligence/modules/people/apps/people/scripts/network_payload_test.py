"""Tests for the search network: the people found and what ties them together."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.config_loader import (
    load_config,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    datasets as ds,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.network_payload import (
    network,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.text import (
    search_text,
)


def _person(slug: str, name: str) -> dict[str, Any]:
    return {
        "slug": slug,
        "full_name": name,
        "headline": None,
        "about": None,
        "quote": None,
        "photo_url": f"/portraits/{slug}.png",
        "organization": "Firm",
        "office": None,
        "city": None,
        "country": None,
        "country_code": None,
        "years_of_experience": None,
        "public_profile_url": None,
        "email": None,
        "phone": None,
        "linkedin_url": None,
        "search_text": search_text({"name": [name]}),
    }


def _experience(
    slug: str, seq: int, organization: str, client: str | None = None
) -> dict:
    return {
        "slug": slug,
        "seq": seq,
        "group_seq": seq,
        "organization": organization,
        "client": client,
        "location": None,
        "title": "Consultant",
        "context": None,
        "description": None,
        "start_date": None,
        "end_date": None,
        "duration_label": None,
    }


def _education(slug: str, seq: int, school: str) -> dict:
    return {
        "slug": slug,
        "seq": seq,
        "school": school,
        "degree": None,
        "field_of_study": None,
        "description": None,
        "start_date": None,
        "end_date": None,
    }


@pytest.fixture
def setup(tmp_path: Path) -> tuple[DatasetService, dict[str, Any]]:
    config = load_config()
    namespace = "people"
    config["data"]["namespace"] = namespace
    warehouse = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "data")
    )
    rows = {
        "people": [
            _person("ada", "Ada Lovelace"),
            _person("grace", "Grace Hopper"),
            _person("alan", "Alan Turing"),
        ],
        "experience": [
            _experience("ada", 1, "Firm", client="Bank"),
            _experience("grace", 1, "Firm", client="Bank"),
            _experience("alan", 1, "Lab"),
        ],
        "education": [
            _education("ada", 1, "Uni"),
            _education("alan", 1, "Uni"),
            _education("grace", 1, "College"),
        ],
    }
    for logical in ds.TABLES:
        spec = ds.dataset_spec(
            logical, table=config["data"]["tables"][logical], namespace=namespace
        )
        ds.replace_rows(warehouse, spec, rows.get(logical, []))
    return warehouse, config


def _ids(payload: dict, kind: str) -> set[str]:
    return {node["id"] for node in payload["nodes"] if node["kind"] == kind}


def test_every_person_found_is_a_node(setup) -> None:
    payload = network(*setup)
    assert _ids(payload, "person") == {"person:ada", "person:grace", "person:alan"}
    ada = next(node for node in payload["nodes"] if node["id"] == "person:ada")
    assert ada["slug"] == "ada" and ada["photo_url"] == "/portraits/ada.png"


def test_only_organizations_that_tie_two_people_are_kept(setup) -> None:
    payload = network(*setup)
    assert _ids(payload, "organization") == {"organization:firm", "organization:bank"}
    assert _ids(payload, "school") == {"school:uni"}
    edges = {(e["source"], e["target"], e["relation"]) for e in payload["edges"]}
    assert ("person:ada", "organization:bank", "client_of") in edges
    assert ("person:alan", "school:uni", "studied_at") in edges
    assert not any(target == "organization:lab" for _, target, _ in edges)


def test_the_network_follows_the_search(setup) -> None:
    payload = network(*setup, query="alan")
    assert _ids(payload, "person") == {"person:alan"}
    # Nothing ties one person to anyone else: every tie is shown instead.
    assert _ids(payload, "organization") == {"organization:lab"}
    assert _ids(payload, "school") == {"school:uni"}
