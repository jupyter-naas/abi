"""Tests for the search facets: every hit is in exactly one tab."""

from __future__ import annotations

from pathlib import Path

from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import load_config
from naas_abi_marketplace.domains.personnel.apps.people.scripts import (
    datasets as ds,
    search_payload,
)
from naas_abi_marketplace.domains.personnel.apps.people.scripts.search_payload import (
    facet_counts,
    facet_value,
)
from naas_abi_marketplace.domains.personnel.apps.people.scripts.text import search_text

NONE = "Not specified"


def hit(service_line: str | None) -> dict:
    return {"person": {"service_line": service_line}}


def test_people_without_a_value_are_counted_not_dropped() -> None:
    hits = [hit("Audit"), hit(None), hit(""), hit("Audit"), hit("Tax")]

    assert facet_counts(hits, "service_line", NONE) == [
        {"value": "Audit", "count": 2},
        {"value": "Tax", "count": 1},
        {"value": NONE, "count": 2},
    ]


def test_the_counts_add_up_to_the_matched_set() -> None:
    """The UI's "All" tab is the sum of the counts."""
    hits = [hit("Audit")] + [hit(None)] * 9

    assert sum(f["count"] for f in facet_counts(hits, "service_line", NONE)) == len(hits)


def test_the_catch_all_is_last_even_when_it_is_the_biggest() -> None:
    hits = [hit("Audit")] + [hit(None)] * 9

    assert [f["value"] for f in facet_counts(hits, "service_line", NONE)] == ["Audit", NONE]


def test_no_catch_all_tab_when_everyone_has_a_value() -> None:
    assert facet_counts([hit("Audit"), hit("Tax")], "service_line", NONE) == [
        {"value": "Audit", "count": 1},
        {"value": "Tax", "count": 1},
    ]


def test_a_person_falls_under_the_label_the_tab_shows() -> None:
    assert facet_value({"service_line": None}, "service_line", NONE) == NONE
    assert facet_value({"service_line": "Tax"}, "service_line", NONE) == "Tax"


def test_a_directory_bigger_than_the_old_candidate_cap_is_fully_searchable(
    tmp_path: Path,
) -> None:
    """Search once fetched 500 people alphabetically and ranked only those.

    Anyone after the 500th name was in the datasets and on the profile page but
    never in a result, and "All" counted 500. This directory is larger.
    """
    config = load_config()
    warehouse = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "data")
    )
    count = 700
    rows = []
    for i in range(count):
        name = f"Person {i:04d}"
        rows.append(
            {
                "slug": f"person_{i:04d}",
                "full_name": name,
                "headline": None, "about": None, "quote": None, "photo_url": None,
                "organization": "Demo", "office": None, "city": None,
                "country": None, "country_code": None,
                "service_line": "Audit" if i % 2 else None,
                "grade": None, "years_of_experience": None,
                "public_profile_url": None,
                "email": None, "phone": None, "linkedin_url": None,
                "search_text": search_text({"name": [name]}),
            }
        )
    namespace = "personnel"
    for logical in ds.TABLES:
        spec = ds.dataset_spec(logical, table=config["data"]["tables"][logical], namespace=namespace)
        ds.replace_rows(warehouse, spec, rows if logical == "people" else [])
    config["data"]["namespace"] = namespace
    config["search"]["page_size"] = 20

    everyone = search_payload.search(warehouse, config)
    assert everyone["total"] == count
    assert sum(f["count"] for f in everyone["facets"]) == count

    last = search_payload.search(warehouse, config, query="person 0699")
    assert [hit["slug"] for hit in last["results"]] == ["person_0699"]

    # Paging by 100 walks the whole directory once, in order, with nobody lost.
    config["search"]["page_size"] = 100
    seen: list[str] = []
    for page in range(1, 8):
        payload = search_payload.search(warehouse, config, page=page)
        assert (payload["page"], payload["pages"], payload["total"]) == (page, 7, count)
        assert len(payload["results"]) == 100
        seen += [hit["slug"] for hit in payload["results"]]
    assert seen == [f"person_{i:04d}" for i in range(count)]

    # A page past the end is the last page, not an empty one.
    beyond = search_payload.search(warehouse, config, page=99)
    assert beyond["page"] == 7 and len(beyond["results"]) == 100
    assert search_payload.search(warehouse, config, page=0)["page"] == 1
