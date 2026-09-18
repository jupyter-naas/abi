"""Tests for the graph → datasets export.

The privacy gate is the part worth guarding: a directory that publishes phone
numbers is a different, worse thing than a directory.
"""

from __future__ import annotations

from typing import Any

import pytest
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import load_config
from naas_abi_marketplace.domains.personnel.apps.people.scripts import (
    export_people_from_graph as export,
)
from naas_abi_marketplace.domains.personnel.paths import DEMO_GRAPH_FILE
from rdflib import Graph

CONFIG = load_config()


class TestPrivacyGate:
    @pytest.mark.parametrize(
        "value",
        [
            "alice.dupont@example.com",
            "Write to alice.dupont@demo.example for more",
            "+33 1 23 45 67 89",
            "Tel. 0612345678",
        ],
    )
    def test_contact_details_are_refused(self, value: str) -> None:
        with pytest.raises(export.PrivacyError):
            export.check_privacy(value, where="people[0].about", config=CONFIG)

    @pytest.mark.parametrize(
        "value",
        [
            "2018-2021",
            "Partner since 2019, 12 years of experience",
            "https://demo.example/profiles/alice_dupont",
            "Certified in 2019 · expires 2026",
            "",
            None,
        ],
    )
    def test_ordinary_profile_text_passes(self, value: Any) -> None:
        assert (
            export.check_privacy(value, where="people[0].about", config=CONFIG) == value
        )

    def test_the_error_says_where_it_was_found(self) -> None:
        with pytest.raises(export.PrivacyError, match=r"people\[3\].about"):
            export.check_privacy("a@b.com", where="people[3].about", config=CONFIG)

    def test_the_gate_can_be_turned_off_per_rule(self) -> None:
        """A client whose directory is internal may want phone numbers in it."""
        config = {
            **CONFIG,
            "privacy": {"reject_emails": True, "reject_long_digit_runs": False},
        }
        assert export.check_privacy("+33 1 23 45 67 89", where="x", config=config)
        with pytest.raises(export.PrivacyError):
            export.check_privacy("a@b.com", where="x", config=config)


class TestQueries:
    def test_every_query_the_exporter_needs_exists(self) -> None:
        queries = export.load_queries()
        for name in (
            "find_people_directory",
            "find_person_skills",
            "find_certifications",
            "find_languages",
            "find_recommendations",
            "find_interests",
            "find_working_processes",
            "find_acts_of_studying",
        ):
            assert name in queries, name

    def test_the_named_graph_wrapper_is_stripped_for_file_queries(self) -> None:
        sparql = export.load_queries()["find_people_directory"]
        assert "GRAPH <http://ontology.naas.ai/graph/personnel>" in sparql
        assert "GRAPH <" not in export._strip_named_graph(sparql)


class TestBuildRowsFromTheDemoGraph:
    @pytest.fixture(scope="class")
    def tables(self) -> dict[str, list[dict[str, Any]]]:
        graph = Graph().parse(DEMO_GRAPH_FILE, format="turtle")
        return export.build_rows(graph, CONFIG)

    def test_it_produces_a_row_per_person(self, tables) -> None:
        assert len(tables["people"]) == 8
        assert {row["slug"] for row in tables["people"]} >= {
            "alice_dupont",
            "hugo_girard",
        }

    def test_every_table_in_the_schema_is_produced(self, tables) -> None:
        from naas_abi_marketplace.domains.personnel.apps.people import datasets as ds

        assert set(tables) == set(ds.TABLES)

    def test_a_person_carries_their_place_and_line(self, tables) -> None:
        alice = next(row for row in tables["people"] if row["slug"] == "alice_dupont")
        assert alice["country_code"] == "FR"
        assert alice["service_line"] == "Operations"
        assert alice["grade"] == "Partner"
        assert alice["years_of_experience"] == 12

    def test_search_text_is_folded(self, tables) -> None:
        alice = next(row for row in tables["people"] if row["slug"] == "alice_dupont")
        assert "alice" in alice["search_text"].split()
        assert alice["search_text"] == alice["search_text"].lower()

    def test_portrait_paths_become_urls_the_app_serves(self, tables) -> None:
        alice = next(row for row in tables["people"] if row["slug"] == "alice_dupont")
        assert alice["photo_url"] == "assets/portraits/alice_dupont.svg"

    def test_roles_at_one_employer_share_a_group(self, tables) -> None:
        rows = [row for row in tables["experience"] if row["slug"] == "alice_dupont"]
        assert rows
        assert len({row["group_seq"] for row in rows}) == len(
            {row["organization"] for row in rows}
        )

    def test_sections_nobody_has_data_for_stay_empty(self, tables) -> None:
        """Absence is exported as absence, never as a placeholder row."""
        david_rows = [
            row for row in tables["certifications"] if row["slug"] == "david_leroy"
        ]
        assert david_rows == []

    def test_the_whole_export_passes_the_privacy_gate(self, tables) -> None:
        for table_name, rows in tables.items():
            for index, row in enumerate(rows):
                for column, value in row.items():
                    export.check_privacy(
                        value, where=f"{table_name}[{index}].{column}", config=CONFIG
                    )
