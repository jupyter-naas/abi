from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import build_feature_flags


class TestBuildFeatureFlags:
    def test_member_role_defaults_to_chat_and_files_only(self) -> None:
        config = FeatureFlagsConfig()

        flags = build_feature_flags(
            role="member",
            feature_flags_config=config,
            workspace_slug="demo",
            workspace_id="ws-1",
        )

        assert flags == {
            "chat": True,
            "files": True,
            "agents": False,
            "knowledge": False,
            "settings": False,
        }

    def test_workspace_overrides_apply_on_top_of_role_baseline(self) -> None:
        config = FeatureFlagsConfig(
            workspace_overrides={
                "demo": {
                    "knowledge": True,
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

        assert flags["knowledge"] is True
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
