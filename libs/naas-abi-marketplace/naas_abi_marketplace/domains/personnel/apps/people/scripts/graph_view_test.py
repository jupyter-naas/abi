"""Tests for the profile's graph view: the cockpit graph page, fed live."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import load_config
from naas_abi_marketplace.domains.personnel.apps.people.scripts import datasets as ds
from naas_abi_marketplace.domains.personnel.apps.people.scripts.datasets_test import (
    person_row,
)
from naas_abi_marketplace.domains.personnel.apps.people.scripts.graph_view import (
    COCKPIT_PAGES,
    SCOPE,
    graph_view,
    graph_view_css,
)
from naas_abi_marketplace.domains.personnel.apps.people.scripts.profile_payload import (
    ProfileNotFoundError,
)


@pytest.fixture(scope="module")
def config() -> dict[str, Any]:
    return load_config()


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory, config: dict[str, Any]):
    tmp_path: Path = tmp_path_factory.mktemp("graph-view")
    service = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "data")
    )
    spec = ds.dataset_spec(
        "people", table=config["data"]["tables"]["people"], namespace="personnel"
    )
    ds.replace_rows(
        service,
        spec,
        [person_row(), person_row(slug="ghost_person", full_name="Ghost Person")],
    )
    return service


class TestPayload:
    def test_it_opens_on_the_profile_person(self, warehouse, config) -> None:
        view = graph_view(warehouse, config, slug="alice_dupont")
        assert view["root"] == "Alice Dupont"
        assert [person["id"] for person in view["data"]["people"]] == ["Alice Dupont"]
        assert view["data"]["relations"]

    def test_it_carries_the_cockpit_graph_settings(self, warehouse, config) -> None:
        view = graph_view(warehouse, config, slug="alice_dupont")
        assert view["config"]["graph"]["default_view"] in ("2d", "3d")
        assert view["config"]["theme"]["bfo_buckets"]

    def test_an_unknown_slug_is_not_found(self, warehouse, config) -> None:
        with pytest.raises(ProfileNotFoundError):
            graph_view(warehouse, config, slug="nobody_here")

    def test_a_person_missing_from_the_graph_is_not_found(
        self, warehouse, config
    ) -> None:
        with pytest.raises(ProfileNotFoundError):
            graph_view(warehouse, config, slug="ghost_person")

    def test_a_slug_that_is_not_a_slug_is_refused(self, warehouse, config) -> None:
        with pytest.raises(ProfileNotFoundError):
            graph_view(warehouse, config, slug="' OR 1=1 --")


class TestStylesheet:
    def test_every_rule_is_scoped_to_the_graph_view(self) -> None:
        css = graph_view_css()
        selectors = [
            line
            for line in css.splitlines()
            if line.endswith("{") and not line.startswith("@media")
        ]
        assert selectors
        assert all(line.startswith(SCOPE) for line in selectors)

    def test_it_keeps_the_graph_page_rules(self) -> None:
        css = graph_view_css()
        assert f"{SCOPE} .graph-toolbar" in css
        assert f"{SCOPE} .graph-stage" in css

    def test_it_leaves_the_cockpit_shell_out(self) -> None:
        css = graph_view_css()
        for shell in (".topbar", ".shell", ".kpis"):
            assert shell not in css
        assert not re.search(r"(^|[\s,])(html|body)\b", css)


def test_the_cockpit_graph_page_is_there_to_serve() -> None:
    assert (COCKPIT_PAGES / "graph" / "GraphPage.js").is_file()
    assert (COCKPIT_PAGES / "processes" / "bfo-buckets.js").is_file()
