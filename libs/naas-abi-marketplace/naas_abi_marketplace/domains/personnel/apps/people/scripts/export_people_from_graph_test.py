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
            # An image CDN path carrying a long numeric id: digits, not a number
            # anyone can call.
            "https://example.com/media/photo/57309031-1-eng-GB/6af7db652949-A-B.jpg",
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

    def test_an_email_inside_a_url_is_still_refused(self) -> None:
        """Exempting URLs from the digit rule does not exempt them from the rest."""
        with pytest.raises(export.PrivacyError):
            export.check_privacy(
                "https://demo.example/?to=alice.dupont@example.com",
                where="people[0].public_profile_url",
                config=CONFIG,
            )

    def test_the_gate_can_be_turned_off_per_rule(self) -> None:
        """A client whose directory is internal may want phone numbers in it."""
        config = {
            **CONFIG,
            "privacy": {"reject_emails": True, "reject_long_digit_runs": False},
        }
        assert export.check_privacy("+33 1 23 45 67 89", where="x", config=config)
        with pytest.raises(export.PrivacyError):
            export.check_privacy("a@b.com", where="x", config=config)


class TestContactColumns:
    """Contact details have one way out: their own columns, well-formed, opted in."""

    OPTED_IN = {"privacy": {"publish_contact_details": True}}

    @pytest.mark.parametrize(
        ("column", "value"),
        [
            ("email", "alice.dupont@demo.example"),
            ("phone", "+33 1 99 00 00 01"),
            ("linkedin_url", "https://www.linkedin.com/in/alice-dupont-demo"),
        ],
    )
    def test_a_well_formed_detail_is_published(self, column: str, value: str) -> None:
        assert (
            export.check_contact(column, value, where="w", config=self.OPTED_IN)
            == value
        )

    @pytest.mark.parametrize(
        ("column", "value"),
        [
            ("email", "call me on +33 1 99 00 00 01"),
            ("phone", "alice.dupont@demo.example"),
            ("linkedin_url", "https://demo.example/profiles/alice_dupont"),
            ("linkedin_url", "http://www.linkedin.com/in/alice"),
        ],
    )
    def test_anything_else_in_a_contact_column_stops_the_export(
        self, column: str, value: str
    ) -> None:
        with pytest.raises(export.PrivacyError, match=f"not a well-formed {column}"):
            export.check_contact(column, value, where="w", config=self.OPTED_IN)

    def test_without_the_opt_in_the_column_is_exported_empty(self) -> None:
        assert (
            export.check_contact(
                "email", "alice.dupont@demo.example", where="w", config={}
            )
            is None
        )

    def test_the_gate_still_refuses_an_email_anywhere_else(self) -> None:
        with pytest.raises(export.PrivacyError):
            export.check_privacy(
                "Reach me at alice.dupont@demo.example",
                where="people[0].headline",
                config=self.OPTED_IN,
            )


class TestGateRows:
    def test_years_folded_into_search_text_are_not_a_phone_number(self) -> None:
        """A biography that lists years must not stop the export for everyone."""
        about = "Joined in 2010, moved in 2011, led from 2015 and 2018."
        tables = {
            "people": [
                {
                    "slug": "a",
                    "about": about,
                    # what search_text() makes of it: punctuation gone, words unique
                    "search_text": "joined in 2010 moved 2011 led from 2015 and 2018",
                }
            ]
        }
        export.gate_rows(tables, CONFIG)  # does not raise

    def test_the_source_field_is_still_gated(self) -> None:
        tables = {"people": [{"slug": "a", "about": "Call 0612345678", "search_text": ""}]}
        with pytest.raises(export.PrivacyError, match=r"people\[0\]\.about"):
            export.gate_rows(tables, CONFIG)

    def test_search_text_is_the_only_exemption(self) -> None:
        tables = {"people_skills": [{"slug": "a", "search_text": "0612345678"}]}
        with pytest.raises(export.PrivacyError):
            export.gate_rows(tables, CONFIG)


class TestNothingIsSilentlyCut:
    def test_the_export_is_not_capped_at_the_interactive_limit(self) -> None:
        from naas_abi_marketplace.domains.personnel.apps.people.scripts import (
            sparql_queries as sq,
        )

        assert export.ROW_LIMIT > sq.DEFAULT_ROW_LIMIT

    def test_a_query_that_hits_its_limit_stops_the_export(self) -> None:
        graph = Graph()
        graph.parse(DEMO_GRAPH_FILE, format="turtle")
        skills = export.load_queries()["find_person_skills"]

        assert len(export.run_query(graph, skills, limit=export.ROW_LIMIT)) > 1
        with pytest.raises(export.TruncatedExportError):
            export.run_query(graph, skills, limit=1)


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
            "find_working_experiences",
            "find_educations",
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
        from naas_abi_marketplace.domains.personnel.apps.people.scripts import datasets as ds

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

    def test_contact_details_reach_the_people_row(self, tables) -> None:
        people = {row["slug"]: row for row in tables["people"]}
        alice = people["alice_dupont"]
        assert alice["email"] == "alice.dupont@demo.example"
        assert alice["phone"] == "+33 1 99 00 00 01"
        assert alice["linkedin_url"] == "https://www.linkedin.com/in/alice-dupont-demo"

    def test_a_missing_contact_detail_stays_missing(self, tables) -> None:
        people = {row["slug"]: row for row in tables["people"]}
        assert people["grace_lambert"]["phone"] is None
        assert people["emma_petit"]["email"] is None
        hugo = people["hugo_girard"]
        assert (hugo["email"], hugo["phone"], hugo["linkedin_url"]) == (None,) * 3

    def test_contact_details_are_not_searchable(self, tables) -> None:
        alice = next(row for row in tables["people"] if row["slug"] == "alice_dupont")
        assert "demo.example" not in alice["search_text"]
        assert "99 00 00" not in alice["search_text"]

    def test_an_instance_that_does_not_opt_in_publishes_no_contact(self) -> None:
        graph = Graph().parse(DEMO_GRAPH_FILE, format="turtle")
        config = {**CONFIG, "privacy": {**CONFIG["privacy"]}}
        config["privacy"]["publish_contact_details"] = False
        people = export.build_rows(graph, config)["people"]
        for row in people:
            assert (row["email"], row["phone"], row["linkedin_url"]) == (None,) * 3

    def test_the_whole_export_passes_the_privacy_gate(self, tables) -> None:
        for table_name, rows in tables.items():
            for index, row in enumerate(rows):
                for column, value in row.items():
                    if table_name == "people" and column in export.CONTACT_COLUMNS:
                        continue
                    export.check_privacy(
                        value, where=f"{table_name}[{index}].{column}", config=CONFIG
                    )
