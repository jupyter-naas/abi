"""Tests for the search facets: every hit is in exactly one tab."""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.apps.people.scripts.search_payload import (
    facet_counts,
    facet_value,
)

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
