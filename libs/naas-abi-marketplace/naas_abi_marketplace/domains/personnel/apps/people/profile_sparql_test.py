"""Profile section SPARQL provenance."""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.apps.people import sparql_queries as sq
from naas_abi_marketplace.domains.personnel.apps.people.profile_sparql import (
    SECTION_QUERY_NAMES,
    competency_queries_for_profile,
    section_sparql,
)


def test_format_query_label() -> None:
    assert sq.format_query_label("find_active_employees") == "Find Active Employees"


def test_every_registered_section_has_a_query_mapping() -> None:
    for section_id in (
        "about",
        "experience",
        "education",
        "skills",
        "certifications",
        "languages",
        "recommendations",
        "interests",
        "sources",
    ):
        assert section_id in SECTION_QUERY_NAMES


def test_section_query_includes_slug_filter_for_bulk_queries() -> None:
    payload = section_sparql("experience", "alice_dupont")
    assert payload["label"] == "Find Working Processes"
    assert "alice_dupont" in payload["text"]
    assert "?__profileSlug" in payload["text"]
    assert "GRAPH <" not in payload["text"]


def test_about_uses_profile_header_query() -> None:
    payload = section_sparql("about", "alice_dupont")
    assert payload["label"] == "Find Profile Header"
    assert 'LCASE("alice_dupont")' in payload["text"]


def test_competency_queries_are_deduped_per_profile() -> None:
    queries = competency_queries_for_profile("alice_dupont")
    names = [entry["name"] for entry in queries]
    assert names == sorted(set(names), key=names.index)
    assert "find_profile_header" in names
    assert "find_working_processes" in names
    assert len(names) == 8
    assert queries[0]["label"] == "Find Profile Header"


def test_sources_lists_both_queries() -> None:
    payload = section_sparql("sources", "alice_dupont")
    assert payload["label"] == "Find Profile Header · Find Working Processes"
    assert "# find_profile_header" in payload["text"]
    assert "# find_working_processes" in payload["text"]
