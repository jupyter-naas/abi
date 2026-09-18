"""Tests for the dataset layer, search ranking and profile assembly.

These run against a real DuckLake warehouse in a temporary directory: the
tables, the SQL and the flush are the thing being tested, and a fake store
would not exercise any of them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetPort import DatasetSpec
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_marketplace.domains.personnel.apps.people.scripts import (
    datasets as ds,
    profile_payload,
    search_payload,
)
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import load_config
from naas_abi_marketplace.domains.personnel.apps.people.scripts.text import search_text

NAMESPACE = "personnel"


def person_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "slug": "alice_dupont",
        "full_name": "Alice Dupont",
        "headline": "COO, Demo",
        "about": "Runs platform operations. Was a data engineer before that.",
        "quote": None,
        "photo_url": None,
        "organization": "Demo",
        "office": "Paris La Défense",
        "city": "Paris",
        "country": "France",
        "country_code": "FR",
        "service_line": "Operations",
        "grade": "Partner",
        "years_of_experience": 12,
        "public_profile_url": "https://demo.example/alice",
        "search_text": "",
    }
    row.update(overrides)
    return row


@pytest.fixture
def warehouse(tmp_path: Path) -> DatasetService:
    return DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "data")
    )


@pytest.fixture
def config() -> dict[str, Any]:
    return load_config()


def publish(
    service: DatasetService, config: dict[str, Any], tables: dict[str, list]
) -> None:
    for logical in ds.TABLES:
        spec = ds.dataset_spec(
            logical, table=config["data"]["tables"][logical], namespace=NAMESPACE
        )
        ds.replace_rows(service, spec, tables.get(logical, []))


@pytest.fixture(scope="module")
def seeded(tmp_path_factory) -> DatasetService:
    tmp_path = tmp_path_factory.mktemp("seeded")
    warehouse = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "data")
    )
    config = load_config()
    alice = person_row()
    alice["search_text"] = search_text(
        {
            "name": [alice["full_name"]],
            "headline": [alice["headline"]],
            "about": [alice["about"]],
            "place": [alice["office"], alice["country"]],
            "line": [alice["service_line"], alice["grade"]],
            "skills": ["Kubernetes", "Python"],
            # The exporter folds every searchable section in here; a section
            # left out of search_text is a section nobody can search for.
            "languages": ["Spanish"],
        }
    )
    cedric = person_row(
        slug="cedric_laumont",
        full_name="Cédric Laumont",
        headline="Associé Audit",
        about="Audite des groupes cotés.",
        service_line="Audit",
        grade="Partner",
        office="Lyon",
        city="Lyon",
        years_of_experience=None,
    )
    cedric["search_text"] = search_text(
        {
            "name": [cedric["full_name"]],
            "headline": [cedric["headline"]],
            "about": [cedric["about"]],
            "place": [cedric["office"]],
            "line": [cedric["service_line"], cedric["grade"]],
        }
    )
    publish(
        warehouse,
        config,
        {
            "people": [alice, cedric],
            "skills": [
                {"slug": "alice_dupont", "skill_name": "Kubernetes"},
                {"slug": "alice_dupont", "skill_name": "Python"},
            ],
            "experience": [
                {
                    "slug": "alice_dupont",
                    "seq": 0,
                    "group_seq": 0,
                    "organization": "Demo",
                    "location": "Paris",
                    "title": "COO",
                    "description": "Leads platform operations.",
                    "start_date": "2023-04-01",
                    "end_date": None,
                    "duration_label": "3 yrs",
                },
                {
                    "slug": "alice_dupont",
                    "seq": 1,
                    "group_seq": 0,
                    "organization": "Demo",
                    "location": "Paris",
                    "title": "Head of Data",
                    "description": None,
                    "start_date": "2021-01-01",
                    "end_date": "2023-03-31",
                    "duration_label": "2 yrs",
                },
                {
                    "slug": "alice_dupont",
                    "seq": 2,
                    "group_seq": 1,
                    "organization": "Acme Consulting",
                    "location": "Remote",
                    "title": "Data Engineer",
                    "description": None,
                    "start_date": "2019-10-01",
                    "end_date": "2020-12-31",
                    "duration_label": "1 yr",
                },
            ],
            "languages": [
                {
                    "slug": "alice_dupont",
                    "seq": 0,
                    "name": "Spanish",
                    "proficiency": "Native or bilingual",
                }
            ],
        },
    )
    return warehouse


class TestSpecs:
    def test_every_table_has_a_spec(self, config: dict[str, Any]) -> None:
        for logical in ds.TABLES:
            spec = ds.dataset_spec(
                logical, table=config["data"]["tables"][logical], namespace=NAMESPACE
            )
            assert isinstance(spec, DatasetSpec)
            assert spec.primary_key

    def test_unknown_table_names_what_is_known(self, config: dict[str, Any]) -> None:
        with pytest.raises(KeyError, match="Unknown table"):
            ds.dataset_spec("publications", table="x", namespace=NAMESPACE)

    def test_config_covers_exactly_the_tables_that_exist(
        self, config: dict[str, Any]
    ) -> None:
        assert set(config["data"]["tables"]) == set(ds.TABLES)


class TestWriting:
    def test_rebuild_replaces_rows_without_dropping_the_table(
        self, warehouse: DatasetService, config: dict[str, Any]
    ) -> None:
        spec = ds.dataset_spec("people", table="people", namespace=NAMESPACE)
        ds.replace_rows(warehouse, spec, [person_row()])
        ds.replace_rows(
            warehouse, spec, [person_row(slug="bob_martin", full_name="Bob")]
        )

        rows = warehouse.query("SELECT slug FROM people", namespace=NAMESPACE).rows
        assert [row["slug"] for row in rows] == ["bob_martin"]
        assert warehouse.list_snapshots()

    def test_missing_table_says_how_to_build_it(
        self, warehouse: DatasetService, config: dict[str, Any]
    ) -> None:
        with pytest.raises(ds.DatasetsMissingError) as error:
            ds.fetch_people(warehouse, namespace=NAMESPACE, table="people")
        assert "make people-datasets" in error.value.as_detail()["command"]

    def test_sql_literal_escapes_quotes(self) -> None:
        assert ds.sql_literal("O'Brien") == "'O''Brien'"


class TestSearch:
    def test_empty_query_returns_everyone(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = search_payload.search(seeded, config)
        assert payload["total"] == 2

    def test_accents_are_ignored(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = search_payload.search(seeded, config, query="cedric")
        assert [hit["full_name"] for hit in payload["results"]] == ["Cédric Laumont"]

    def test_prefix_matches(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = search_payload.search(seeded, config, query="kuber")
        assert [hit["slug"] for hit in payload["results"]] == ["alice_dupont"]

    def test_every_word_must_match(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = search_payload.search(seeded, config, query="audit lyon")
        assert payload["mode"] == "all"
        assert [hit["slug"] for hit in payload["results"]] == ["cedric_laumont"]

    def test_partial_matches_are_shown_with_a_notice(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        """An empty page would say nobody works here, which is not the answer."""
        payload = search_payload.search(seeded, config, query="kubernetes audit")
        assert payload["mode"] == "any"
        assert payload["total"] == 2

    def test_no_match_is_empty_rather_than_everyone(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = search_payload.search(seeded, config, query="astrophysics")
        assert payload["results"] == []

    def test_name_outranks_a_mention(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = search_payload.search(seeded, config, query="alice")
        assert payload["results"][0]["slug"] == "alice_dupont"

    def test_facets_count_the_matched_set(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = search_payload.search(seeded, config)
        assert {facet["value"]: facet["count"] for facet in payload["facets"]} == {
            "Operations": 1,
            "Audit": 1,
        }

    def test_facet_filters_results_but_not_the_counts(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = search_payload.search(seeded, config, facet="Audit")
        assert [hit["slug"] for hit in payload["results"]] == ["cedric_laumont"]
        assert len(payload["facets"]) == 2

    def test_suggestions_are_limited_and_ranked(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        suggestions = search_payload.suggest(seeded, config, query="a")
        assert suggestions
        assert len(suggestions) <= config["search"]["max_suggestions"]

    def test_a_stopword_only_query_suggests_nothing(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        assert search_payload.suggest(seeded, config, query="of the") == []


class TestSnippet:
    def test_it_avoids_repeating_the_title_line(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        """Searching a word from the headline should not echo the headline back."""
        payload = search_payload.search(seeded, config, query="coo")
        snippet = payload["results"][0]["snippet"]
        assert snippet["text"]
        assert "COO, Demo" != snippet["text"]

    def test_it_shows_the_section_that_matched(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = search_payload.search(seeded, config, query="spanish")
        snippet = payload["results"][0]["snippet"]
        assert snippet["label"] == "Languages"
        assert "Spanish" in snippet["text"]

    def test_it_falls_back_to_the_summary(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = search_payload.search(seeded, config, query="alice")
        assert "Runs platform operations" in payload["results"][0]["snippet"]["text"]


class TestProfile:
    def test_sections_follow_the_configured_order(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = profile_payload.profile(seeded, config, slug="alice_dupont")
        configured = [section["id"] for section in config["profile"]["sections"]]
        assert [section["id"] for section in payload["sections"]] == configured

    def test_an_empty_section_is_present_with_its_text(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = profile_payload.profile(seeded, config, slug="alice_dupont")
        sections = {section["id"]: section for section in payload["sections"]}
        assert sections["recommendations"]["items"] == []
        assert sections["recommendations"]["empty_text"]

    def test_roles_at_one_employer_are_grouped(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = profile_payload.profile(seeded, config, slug="alice_dupont")
        experience = next(
            section for section in payload["sections"] if section["id"] == "experience"
        )
        assert [group["organization"] for group in experience["items"]] == [
            "Demo",
            "Acme Consulting",
        ]
        assert len(experience["items"][0]["roles"]) == 2

    def test_an_open_role_keeps_the_whole_stay_open(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = profile_payload.profile(seeded, config, slug="alice_dupont")
        experience = next(
            section for section in payload["sections"] if section["id"] == "experience"
        )
        assert experience["items"][0]["end"] is None

    def test_a_fact_with_no_value_is_left_out(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        payload = profile_payload.profile(seeded, config, slug="cedric_laumont")
        labels = [fact["label"] for fact in payload["facts"]]
        assert "Experience" not in labels
        assert "Grade" in labels

    def test_unknown_slug_is_not_found(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        with pytest.raises(profile_payload.ProfileNotFoundError):
            profile_payload.profile(seeded, config, slug="nobody_here")

    def test_a_slug_that_is_not_a_slug_is_refused_before_any_query(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        with pytest.raises(profile_payload.ProfileNotFoundError):
            profile_payload.profile(seeded, config, slug="' OR 1=1 --")

    def test_related_lists_the_same_facet_value_only(
        self, seeded: DatasetService, config: dict[str, Any]
    ) -> None:
        related = profile_payload.related(seeded, config, slug="alice_dupont")
        assert related["value"] == "Operations"
        assert related["people"] == []
