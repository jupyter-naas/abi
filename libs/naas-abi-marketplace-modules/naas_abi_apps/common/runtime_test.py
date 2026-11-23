from dataclasses import dataclass, field

import pytest
from naas_abi_apps.common.runtime import configuration_from


@dataclass
class Settings:
    name: str = "default"
    enabled: bool = False
    filters: list[dict] = field(default_factory=list)
    app: dict = field(default_factory=dict)


def test_plain_fields_come_from_their_variables():
    settings = configuration_from(
        Settings, "demo", {"DEMO_NAME": "n", "DEMO_ENABLED": "yes"}
    )
    assert settings.name == "n" and settings.enabled is True
    assert configuration_from(Settings, "demo", {}) == Settings()


def test_list_and_dict_variables_are_json():
    settings = configuration_from(
        Settings,
        "demo",
        {"DEMO_FILTERS": '[{"name": "ai"}]', "DEMO_APP": '{"publish": false}'},
    )
    assert settings.filters == [{"name": "ai"}]
    assert settings.app == {"publish": False}
    with pytest.raises(SystemExit, match="DEMO_FILTERS must be JSON"):
        configuration_from(Settings, "demo", {"DEMO_FILTERS": "[nope"})


def test_a_configuration_file_sets_fields_and_variables_win(tmp_path):
    # An engine config.yaml modules: entry, copied as it is.
    path = tmp_path / "x.yaml"
    path.write_text(
        "module: naas_abi_marketplace.applications.x\n"
        "config:\n"
        "  name: from-file\n"
        "  filters:\n"
        "    - name: ai\n"
        "      query: openai\n"
    )
    settings = configuration_from(
        Settings, "demo", {"DEMO_CONFIG_FILE": str(path), "DEMO_NAME": "from-env"}
    )
    assert settings.name == "from-env"
    assert settings.filters == [{"name": "ai", "query": "openai"}]

    json_path = tmp_path / "x.json"
    json_path.write_text('{"enabled": true}')
    assert configuration_from(
        Settings, "demo", {"DEMO_CONFIG_FILE": str(json_path)}
    ).enabled


def test_a_configuration_file_with_an_unknown_field_is_refused(tmp_path):
    path = tmp_path / "x.json"
    path.write_text('{"bearer_token": "secret"}')
    with pytest.raises(SystemExit, match="unknown configuration fields"):
        configuration_from(Settings, "demo", {"DEMO_CONFIG_FILE": str(path)})
