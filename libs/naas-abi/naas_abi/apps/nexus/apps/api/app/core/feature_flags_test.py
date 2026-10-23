import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
    InvalidFeatureOverridesError,
    build_feature_flags,
    dump_feature_overrides,
    effective_workspace_overrides,
    parse_feature_overrides,
    validate_workspace_feature_overrides,
    workspace_features,
)


class TestBuildFeatureFlags:
    def test_member_role_defaults_include_slides(self) -> None:
        config = FeatureFlagsConfig()

        flags = build_feature_flags(
            role="member",
            feature_flags_config=config,
            workspace_slug="demo",
            workspace_id="ws-1",
        )

        assert flags == {
            "maps": True,
            "chat": True,
            "files": True,
            "agents": False,
            "skills": True,
            "apps": False,
            "marketplace": False,
            "search": False,
            "ontology": False,
            "graph": False,
            "datasets": True,
            "settings": False,
            "code": False,
            "slides": True,
            "sheets": True,
            "documents": True,
            "board": False,
        }

    @pytest.mark.parametrize(
        ("role", "expected"),
        [("owner", True), ("admin", True), ("member", False), ("viewer", False)],
    )
    def test_board_defaults_to_owners_and_admins_only(self, role: str, expected: bool) -> None:
        flags = build_feature_flags(
            role=role,
            feature_flags_config=FeatureFlagsConfig(),
            workspace_slug="demo",
            workspace_id="ws-1",
        )

        assert flags["board"] is expected

    def test_workspace_overrides_apply_on_top_of_role_baseline(self) -> None:
        config = FeatureFlagsConfig(
            workspace_overrides={
                "demo": {
                    "search": True,
                    "apps": True,
                    "marketplace": True,
                    "chat": False,
                }
            }
        )

        flags = build_feature_flags(
            role="member",
            feature_flags_config=config,
            workspace_slug="demo",
            workspace_id="ws-1",
        )

        assert flags["search"] is True
        assert flags["apps"] is True
        assert flags["marketplace"] is True
        assert flags["chat"] is False
        assert flags["files"] is True

    def test_unknown_role_denies_all_features(self) -> None:
        config = FeatureFlagsConfig()

        flags = build_feature_flags(
            role="unknown-role",
            feature_flags_config=config,
            workspace_slug="demo",
            workspace_id="ws-1",
        )

        assert all(value is False for value in flags.values())

    def test_code_feature_off_by_default_even_for_owner(self) -> None:
        # The coding workspaces are opt-in: the built-in defaults never grant
        # "code" to any role, so an owner sees everything else but not code.
        config = FeatureFlagsConfig()

        flags = build_feature_flags(
            role="owner",
            feature_flags_config=config,
            workspace_slug="demo",
            workspace_id="ws-1",
        )

        assert flags["code"] is False
        assert flags["chat"] is True  # owner still gets the standard features

    def test_code_feature_enabled_via_config(self) -> None:
        # Turning it on requires BOTH the catalog (enabled_features) and a role
        # grant (role_baseline). Owner gets it; a member without the grant does
        # not, even though the catalog now contains "code".
        config = FeatureFlagsConfig(
            enabled_features=[
                "chat",
                "files",
                "agents",
                "apps",
                "marketplace",
                "search",
                "ontology",
                "graph",
                "settings",
                "code",
            ],
            role_baseline={
                "owner": ["chat", "files", "code"],
                "member": ["chat", "files"],
            },
        )

        owner_flags = build_feature_flags(
            role="owner",
            feature_flags_config=config,
            workspace_slug="demo",
            workspace_id="ws-1",
        )
        member_flags = build_feature_flags(
            role="member",
            feature_flags_config=config,
            workspace_slug="demo",
            workspace_id="ws-1",
        )

        assert owner_flags["code"] is True
        assert member_flags["code"] is False

    def test_organization_override_wins_over_deployment_baseline(self) -> None:
        config = FeatureFlagsConfig()

        flags = build_feature_flags(
            role="member",
            feature_flags_config=config,
            workspace_slug="demo",
            workspace_id="ws-1",
            organization_id="org-1",
            organization_override={
                "member": ["maps", "chat"],
                "viewer": ["maps"],
                "owner": list(config.role_baseline["owner"]),
                "admin": list(config.role_baseline["admin"]),
            },
        )

        assert flags["maps"] is True
        assert flags["chat"] is True
        assert flags["files"] is False
        assert flags["skills"] is False
        assert flags["slides"] is False


class TestWorkspaceOverrideFromTheApp:
    CONFIG = FeatureFlagsConfig(workspace_overrides={"axa": {"maps": False, "graph": True}})

    def test_a_saved_override_replaces_the_config_entry(self) -> None:
        flags = build_feature_flags(
            role="member",
            feature_flags_config=self.CONFIG,
            workspace_slug="axa",
            workspace_id="ws-1",
            workspace_override={"search": True},
        )

        # The config's maps: false and graph: true no longer apply.
        assert (flags["maps"], flags["graph"], flags["search"]) == (True, False, True)

    def test_an_empty_saved_override_falls_back_to_the_role_baseline(self) -> None:
        flags = build_feature_flags(
            role="member",
            feature_flags_config=self.CONFIG,
            workspace_slug="axa",
            workspace_id="ws-1",
            workspace_override={},
        )

        assert (flags["maps"], flags["graph"]) == (True, False)

    def test_effective_overrides_report_their_source(self) -> None:
        def effective(override):
            return effective_workspace_overrides(
                self.CONFIG, workspace_slug="axa", workspace_id="ws-1", workspace_override=override
            )

        assert effective(None) == ({"maps": False, "graph": True}, "deployment")
        assert effective({"maps": True}) == ({"maps": True}, "database")
        assert effective_workspace_overrides(
            self.CONFIG, workspace_slug="other", workspace_id="ws-2", workspace_override=None
        ) == ({}, None)

    def test_workspace_features_are_the_union_over_roles(self) -> None:
        features = workspace_features(
            roles=("owner", "member"),
            feature_flags_config=self.CONFIG,
            workspace_slug="axa",
            workspace_id="ws-1",
        )

        assert "maps" not in features
        assert "graph" in features
        assert features[0] == "chat"

    def test_overrides_round_trip_through_json_and_drop_unknown_keys(self) -> None:
        raw = dump_feature_overrides({"maps": False, "graph": True})

        assert parse_feature_overrides(raw) == {"graph": True, "maps": False}
        assert parse_feature_overrides('{"nope": true, "chat": "yes"}') == {}
        assert parse_feature_overrides(None) is None
        assert parse_feature_overrides("not json") is None


class TestValidateWorkspaceFeatureOverrides:
    def test_catalog_features_are_kept(self) -> None:
        assert validate_workspace_feature_overrides(
            FeatureFlagsConfig(), {"maps": False, "graph": True}
        ) == {"maps": False, "graph": True}

    def test_features_outside_the_catalog_are_rejected(self) -> None:
        with pytest.raises(InvalidFeatureOverridesError, match="catalog: code"):
            validate_workspace_feature_overrides(FeatureFlagsConfig(), {"code": True})

    def test_pinned_features_are_rejected(self) -> None:
        with pytest.raises(InvalidFeatureOverridesError, match="always on: settings"):
            validate_workspace_feature_overrides(FeatureFlagsConfig(), {"settings": False})
