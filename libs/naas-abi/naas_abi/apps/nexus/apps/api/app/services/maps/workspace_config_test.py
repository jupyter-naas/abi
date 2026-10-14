from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.config import (
    OrganizationSeedConfig,
    WorkspaceMapsSeedConfig,
    WorkspaceSeedConfig,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.workspace_config import (
    WorkspaceMapsDefaults,
    unknown_workspace_map_ids,
    workspace_maps_defaults,
)

ORGS = [
    OrganizationSeedConfig(
        name="Example",
        slug="example",
        workspaces=[
            WorkspaceSeedConfig(
                name="Erin",
                slug="erin",
                maps=WorkspaceMapsSeedConfig.model_validate(
                    {
                        "feeds": ["erin-facilities", "earthquakes"],
                        "basemaps": {"custom": ["erin-countries"]},
                    }
                ),
            ),
            WorkspaceSeedConfig(
                name="Feeds only", slug="feeds-only", maps={"feeds": ["erin-facilities"]}
            ),
            WorkspaceSeedConfig(name="Plain", slug="plain"),
        ],
    )
]


def test_workspace_config_lists_its_enabled_feeds_and_basemaps() -> None:
    assert workspace_maps_defaults(ORGS, "erin") == WorkspaceMapsDefaults(
        feeds=frozenset({"erin-facilities", "earthquakes"}),
        custom_basemaps=frozenset({"erin-countries"}),
    )


def test_without_basemaps_no_custom_basemap_is_enabled() -> None:
    assert workspace_maps_defaults(ORGS, "feeds-only") == WorkspaceMapsDefaults(
        feeds=frozenset({"erin-facilities"}), custom_basemaps=frozenset()
    )


def test_workspaces_without_maps_config_start_with_every_feed_disabled() -> None:
    nothing = WorkspaceMapsDefaults(feeds=frozenset(), custom_basemaps=frozenset())
    assert workspace_maps_defaults(ORGS, "plain") == nothing
    assert workspace_maps_defaults(ORGS, "unknown") == nothing
    assert workspace_maps_defaults(ORGS, None) == nothing


def test_unknown_keys_are_refused() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WorkspaceMapsSeedConfig.model_validate({"feeds": [], "default_on": []})
    with pytest.raises(ValidationError):
        WorkspaceMapsSeedConfig.model_validate({"basemaps": ["erin-countries"]})


def test_unknown_ids_are_reported_per_workspace() -> None:
    known_feeds = {"erin-facilities"}
    known_basemaps = {"other-countries"}
    assert unknown_workspace_map_ids(ORGS, known_feeds, known_basemaps) == {
        "erin": ["basemap 'erin-countries'", "feed 'earthquakes'"],
    }
    assert unknown_workspace_map_ids(ORGS, known_feeds | {"earthquakes"}, {"erin-countries"}) == {}


def test_mounted_module_config_accepts_the_same_maps_block() -> None:
    # The naas_abi module validates config.*.yaml before Nexus does (same schema).
    from naas_abi import WorkspaceSeedConfig as ModuleWorkspaceSeedConfig

    seed = ModuleWorkspaceSeedConfig.model_validate(
        {"name": "Erin", "slug": "erin", "maps": {"feeds": ["erin-facilities"]}}
    )
    assert seed.maps == WorkspaceMapsSeedConfig(feeds=["erin-facilities"])
