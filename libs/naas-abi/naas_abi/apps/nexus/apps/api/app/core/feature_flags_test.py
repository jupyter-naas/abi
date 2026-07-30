from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import build_feature_flags


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
            "settings": False,
            "code": False,
            "slides": True,
        }

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
