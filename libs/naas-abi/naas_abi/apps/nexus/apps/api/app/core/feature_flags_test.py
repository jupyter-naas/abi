import pytest

from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
    build_feature_flags,
    parse_feature_overrides,
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
            "tasks": False,
        }

    @pytest.mark.parametrize(
        ("role", "expected"),
        [("owner", True), ("admin", True), ("member", False), ("viewer", False)],
    )
    def test_tasks_defaults_to_owners_and_admins_only(self, role: str, expected: bool) -> None:
        flags = build_feature_flags(
            role=role,
            feature_flags_config=FeatureFlagsConfig(),
            workspace_slug="demo",
            workspace_id="ws-1",
        )

        assert flags["tasks"] is expected

    def test_the_feature_set_bounds_the_role_baseline(self) -> None:
        flags = build_feature_flags(
            role="member",
            feature_flags_config=FeatureFlagsConfig(),
            feature_set=("chat", "apps"),
        )

        # Within the set, the role's defaults: members have no apps by default.
        assert flags["chat"] is True
        assert flags["apps"] is False
        assert flags["files"] is False
        # Settings always stays reachable.
        assert (
            build_feature_flags(
                role="owner", feature_flags_config=FeatureFlagsConfig(), feature_set=()
            )["settings"]
            is True
        )

    def test_the_deprecated_workspace_overrides_no_longer_apply(self) -> None:
        config = FeatureFlagsConfig(workspace_overrides={"demo": {"chat": False}})

        flags = build_feature_flags(
            role="member", feature_flags_config=config, workspace_slug="demo"
        )

        assert flags["chat"] is True

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


class TestWorkspaceFeatures:
    def test_workspace_features_are_the_union_over_roles_within_the_set(self) -> None:
        features = workspace_features(
            roles=("owner", "member"),
            feature_flags_config=FeatureFlagsConfig(),
            feature_set=("chat", "graph", "settings"),
        )

        assert features == ["chat", "graph", "settings"]

    def test_saved_overrides_parse_for_the_move_and_drop_unknown_keys(self) -> None:
        assert parse_feature_overrides('{"maps": false, "graph": true}') == {
            "graph": True,
            "maps": False,
        }
        assert parse_feature_overrides('{"nope": true, "chat": "yes"}') == {}
        assert parse_feature_overrides(None) is None
        assert parse_feature_overrides("not json") is None
