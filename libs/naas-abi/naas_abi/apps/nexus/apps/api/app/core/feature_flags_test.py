from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
    KNOWN_FEATURE_KEYS,
    enabled_feature_catalog,
    feature_enabled,
    offered_features,
    parse_feature_overrides,
)


class TestEnabledFeatures:
    def test_code_is_opt_in(self) -> None:
        config = FeatureFlagsConfig()

        assert not feature_enabled(config, "code")
        assert feature_enabled(config, "chat")
        assert "code" not in enabled_feature_catalog(config)

    def test_code_is_enabled_by_the_catalog_alone(self) -> None:
        # No role brings a feature: enabling one is the catalog's, using it a policy's.
        config = FeatureFlagsConfig(enabled_features=["chat", "code"])

        assert enabled_feature_catalog(config) == ["chat", "code"]
        assert feature_enabled(config, "code")
        assert not feature_enabled(config, "files")

    def test_an_empty_catalog_is_every_known_feature(self) -> None:
        assert enabled_feature_catalog(FeatureFlagsConfig(enabled_features=[])) == list(
            KNOWN_FEATURE_KEYS
        )


class TestOfferedFeatures:
    def test_a_workspace_offers_the_enabled_features_within_its_set(self) -> None:
        config = FeatureFlagsConfig()

        assert offered_features(config, ("chat", "graph", "code")) == [
            "chat",
            "graph",
            "settings",
        ]
        assert offered_features(config) == enabled_feature_catalog(config)

    def test_settings_stays_offered_with_an_empty_set(self) -> None:
        assert offered_features(FeatureFlagsConfig(), ()) == ["settings"]

    def test_saved_overrides_parse_for_the_move_and_drop_unknown_keys(self) -> None:
        assert parse_feature_overrides('{"maps": false, "graph": true}') == {
            "graph": True,
            "maps": False,
        }
        assert parse_feature_overrides('{"nope": true, "chat": "yes"}') == {}
        assert parse_feature_overrides(None) is None
        assert parse_feature_overrides("not json") is None
