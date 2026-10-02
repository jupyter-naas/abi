"""Tests for the People Search configuration contract.

The point of validating on the server is that a client learns at startup, by
name, what is wrong with their config.yaml. These tests are that promise.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import (
    CONFIG_PATH,
    REGISTERED_SECTION_IDS,
    WEB_ROOT,
    ConfigError,
    load_config,
    public_config,
    public_page_urls,
    web_root_for,
)

SHIPPED = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def write_config(tmp_path: Path, mutate) -> Path:
    """A config.yaml in its own instance folder, the way a second app ships one.

    Brand files are resolved against the folder holding the config, not against
    this package, so the fixture has to lay out ``web/assets/`` the same way a
    real instance does.
    """
    raw = copy.deepcopy(SHIPPED)
    mutate(raw)
    assets = tmp_path / "web" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("logo.svg", "favicon.svg"):
        (assets / name).write_bytes((WEB_ROOT / "assets" / name).read_bytes())
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def fails(tmp_path: Path, mutate, message: str) -> None:
    with pytest.raises(ConfigError) as error:
        load_config(write_config(tmp_path, mutate))
    assert message in str(error.value)


class TestShippedConfig:
    def test_it_loads(self) -> None:
        config = load_config()
        assert config["brand"]["name"]
        assert config["data"]["namespace"] == "personnel"

    def test_every_registered_section_is_configured(self) -> None:
        """A registered section nobody configured would never be reachable."""
        configured = {section["id"] for section in load_config()["profile"]["sections"]}
        assert configured == set(REGISTERED_SECTION_IDS)

    def test_brand_assets_exist_on_disk(self) -> None:
        brand = load_config()["brand"]
        assert brand["favicon_src"] == "assets/favicon.svg"
        assert brand["logo_src"] == "assets/logo.svg"


class TestPages:
    def test_unregistered_page_is_named_in_the_error(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["app"]["pages"][0]["page_id"] = "dashboard"

        fails(tmp_path, mutate, "not registered: dashboard")

    def test_duplicate_order_is_rejected(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["app"]["pages"][1]["order"] = raw["app"]["pages"][0]["order"]

        fails(tmp_path, mutate, "order is duplicated")

    def test_duplicate_url_is_rejected(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["app"]["pages"][2]["url"] = raw["app"]["pages"][1]["url"]

        fails(tmp_path, mutate, "url is duplicated")

    def test_bad_url_token_is_rejected(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["app"]["pages"][1]["url"] = "Search Results"

        fails(tmp_path, mutate, "must be lowercase letters")

    def test_default_page_must_be_one_of_the_pages(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["app"]["default_page"] = "profile-x"

        fails(tmp_path, mutate, "app.default_page is not one of the pages")

    def test_home_owns_the_empty_url(self) -> None:
        assert "" not in public_page_urls()


class TestSections:
    def test_unregistered_section_is_rejected(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["profile"]["sections"][0]["id"] = "publications"

        fails(tmp_path, mutate, "not registered: publications")

    def test_empty_text_is_required(self, tmp_path: Path) -> None:
        """Hiding an empty section is a decision; leaving it blank is a bug."""

        def mutate(raw: dict[str, Any]) -> None:
            raw["profile"]["sections"][1]["empty_text"] = ""

        fails(tmp_path, mutate, "empty_text must be a non-empty string")

    def test_sections_come_back_in_configured_order(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            for section in raw["profile"]["sections"]:
                if section["id"] == "skills":
                    section["order"] = 1

        config = load_config(write_config(tmp_path, mutate))
        assert config["profile"]["sections"][0]["id"] == "skills"

    def test_disabled_section_is_dropped_from_the_public_config(
        self, tmp_path: Path
    ) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            for section in raw["profile"]["sections"]:
                if section["id"] == "recommendations":
                    section["enabled"] = False

        config = public_config(write_config(tmp_path, mutate))
        assert "recommendations" not in {s["id"] for s in config["profile"]["sections"]}


class TestContact:
    def test_the_shipped_config_offers_all_three(self) -> None:
        fields = [item["field"] for item in load_config()["profile"]["contact"]]
        assert fields == ["email", "phone", "linkedin_url"]

    def test_contact_must_name_a_contact_column(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["profile"]["contact"][0]["field"] = "headline"

        fails(tmp_path, mutate, "is not a contact column: headline")

    def test_a_contact_field_is_listed_once(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["profile"]["contact"].append({"field": "email", "label": "Mail"})

        fails(tmp_path, mutate, "profile.contact lists email twice")

    def test_a_contact_detail_cannot_be_a_fact(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["profile"]["facts"][0]["field"] = "phone"

        fails(tmp_path, mutate, "is not a people column: phone")

    def test_a_contact_detail_cannot_be_searched(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["search"]["fields"][0]["name"] = "email"

        fails(tmp_path, mutate, "is not searchable: email")

    def test_the_opt_in_is_a_boolean(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["privacy"]["publish_contact_details"] = "yes"

        fails(tmp_path, mutate, "privacy.publish_contact_details must be true or false")

    def test_no_contact_block_means_no_contact_row(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["profile"].pop("contact")

        assert load_config(write_config(tmp_path, mutate))["profile"]["contact"] == []


class TestFactsAndSearch:
    def test_fact_must_name_a_people_column(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["profile"]["facts"][0]["field"] = "favourite_colour"

        fails(tmp_path, mutate, "is not a people column: favourite_colour")

    def test_facet_must_name_a_people_column(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["search"]["facet_field"] = "department"

        fails(tmp_path, mutate, "search.facet_field is not a people column")

    def test_search_weight_must_be_positive(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["search"]["fields"][0]["weight"] = 0

        fails(tmp_path, mutate, "weight must be a positive number")

    def test_unsearchable_field_is_rejected(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["search"]["fields"][0]["name"] = "salary"

        fails(tmp_path, mutate, "is not searchable: salary")


class TestData:
    def test_namespace_must_be_an_identifier(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["data"]["namespace"] = "personnel; drop table people"

        fails(tmp_path, mutate, "data.namespace must be a SQL identifier")

    def test_table_name_must_be_an_identifier(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["data"]["tables"]["people"] = "people--"

        fails(tmp_path, mutate, "data.tables.people must be a SQL identifier")

    def test_missing_table_is_named(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            del raw["data"]["tables"]["languages"]

        fails(tmp_path, mutate, "data.tables is missing: languages")


class TestBrandAssets:
    def test_missing_asset_file_is_reported(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["brand"]["favicon_src"] = "assets/nope.svg"

        fails(tmp_path, mutate, "points at a file that does not exist")

    def test_traversal_out_of_the_app_is_refused(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["brand"]["logo_src"] = "assets/../../cockpit/web/favicon.svg"

        fails(tmp_path, mutate, "must stay inside the app folder")

    def test_asset_outside_the_assets_folder_is_refused(self, tmp_path: Path) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["brand"]["logo_src"] = "web/css/app.css"

        fails(tmp_path, mutate, "must be a path under assets/")

    def test_no_favicon_is_allowed_and_falls_back_to_the_mark(
        self, tmp_path: Path
    ) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["brand"]["favicon_src"] = ""
            raw["brand"]["logo_src"] = ""

        config = load_config(write_config(tmp_path, mutate))
        assert config["brand"]["favicon_src"] is None
        assert config["brand"]["logo_src"] is None
        assert config["brand"]["mark"]


class TestSecondInstance:
    """A config.yaml outside this package is a second app on the same renderers."""

    def test_brand_files_resolve_against_the_config_folder(
        self, tmp_path: Path
    ) -> None:
        path = write_config(tmp_path, lambda raw: None)
        (tmp_path / "web" / "assets" / "client.svg").write_text("<svg/>")

        def mutate(raw: dict[str, Any]) -> None:
            raw["brand"]["logo_src"] = "assets/client.svg"

        config = load_config(write_config(tmp_path, mutate))
        assert config["brand"]["logo_src"] == "assets/client.svg"
        assert web_root_for(path) == tmp_path / "web"

    def test_an_asset_only_the_shipped_app_has_is_reported_missing(
        self, tmp_path: Path
    ) -> None:
        """Instances do not silently inherit this app's brand."""

        def mutate(raw: dict[str, Any]) -> None:
            raw["brand"]["logo_src"] = "assets/portraits/alice_dupont.svg"

        fails(tmp_path, mutate, "points at a file that does not exist")

    def test_graph_file_is_resolved_and_kept_off_the_wire(
        self, tmp_path: Path
    ) -> None:
        ttl = tmp_path / "instance.ttl"
        ttl.write_text("")

        def mutate(raw: dict[str, Any]) -> None:
            raw["data"]["graph"]["file"] = "instance.ttl"

        path = write_config(tmp_path, mutate)
        assert load_config(path)["data"]["graph"]["file"] == str(ttl.resolve())
        assert "file" not in public_config(path)["knowledge_graph"]

    def test_a_graph_file_that_is_not_there_fails_at_startup(
        self, tmp_path: Path
    ) -> None:
        def mutate(raw: dict[str, Any]) -> None:
            raw["data"]["graph"]["file"] = "nowhere.ttl"

        fails(tmp_path, mutate, "data.graph.file points at a file that does not exist")

    def test_portrait_prefix_defaults_to_this_app(self, tmp_path: Path) -> None:
        assert load_config()["data"]["portrait_prefix"] == "apps/people/web/"

        def mutate(raw: dict[str, Any]) -> None:
            raw["data"]["portrait_prefix"] = "apps/people/web/"

        config = load_config(write_config(tmp_path, mutate))
        assert config["data"]["portrait_prefix"] == "apps/people/web/"


class TestPublicConfig:
    def test_table_names_and_privacy_stay_on_the_server(self) -> None:
        """The browser asks this app for people, never the warehouse directly."""
        config = public_config()
        assert "data" not in config
        assert "privacy" not in config
        assert "fields" not in config["search"]

    def test_search_settings_the_browser_needs_are_published(self) -> None:
        search = public_config()["search"]
        assert search["min_autocomplete_chars"] >= 1
        assert search["facet_label"]
