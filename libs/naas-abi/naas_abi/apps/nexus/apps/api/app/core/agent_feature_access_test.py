from dataclasses import dataclass

from naas_abi.apps.nexus.apps.api.app.core.agent_feature_access import (
    feature_agent_visible,
    filter_feature_agents,
)

APPS = "naas_abi.agents.AppsAgent/AppsAgent"
ONTOLOGY = "naas_abi.agents.OntologyAgent/OntologyAgent"
CATALOG = "naas_abi.agents.AgentCatalogAgent/AgentCatalogAgent"
SETTINGS = "naas_abi.agents.SettingsAgent/SettingsAgent"
ABI = "naas_abi.agents.AbiAgent/AbiAgent"
AXI = "axi.agents.AxiAgent/AxiAgent"


@dataclass
class Row:
    id: str
    class_name: str | None
    is_default: bool = False


def test_office_agent_follows_its_feature() -> None:
    assert feature_agent_visible(APPS, {"apps": True}) is True
    assert feature_agent_visible(APPS, {"apps": False}) is False
    assert feature_agent_visible(APPS, {}) is False


def test_multi_feature_agent_survives_on_any_one() -> None:
    assert (
        feature_agent_visible(SETTINGS, {"settings": False, "settings.workspace": True})
        is True
    )
    assert (
        feature_agent_visible(
            SETTINGS, {"settings": False, "settings.workspace": False}
        )
        is False
    )


def test_non_office_agents_are_never_gated() -> None:
    for class_name in (ABI, AXI, None, "", "AppsAgent"):
        assert feature_agent_visible(class_name, {}) is True


def test_a_lookalike_from_another_module_is_not_gated() -> None:
    assert feature_agent_visible("acme.agents.AppsAgent/AppsAgent", {}) is True


def test_filter_keeps_the_allowed_features_and_the_default() -> None:
    rows = [
        Row("1", AXI, is_default=True),
        Row("2", APPS),
        Row("3", ONTOLOGY),
        Row("4", CATALOG),
    ]
    kept = filter_feature_agents(rows, {"apps": True, "files": True, "ontology": True})
    assert [row.id for row in kept] == ["1", "2", "3"]


def test_filter_never_drops_the_default_office_agent() -> None:
    rows = [Row("1", APPS, is_default=True)]
    assert filter_feature_agents(rows, {"apps": False}) == rows
