import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
    deep_merge,
)

BASE = (
    "api: {}\n"
    "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
    "modules: []\n"
    "services:\n"
    "  secret: {secret_adapters: []}\n"
    "  kv: {kv_adapter: {adapter: python, config: {}}}\n"
    "  bus: {bus_adapter: {adapter: python_queue, config: {}}}\n"
)


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text(BASE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("ABI_CONFIG_OVERLAY", raising=False)
    EngineConfiguration.reset_configuration_cache()
    yield tmp_path
    EngineConfiguration.reset_configuration_cache()


def test_deep_merge_merges_mappings_and_replaces_everything_else():
    base = {"a": {"b": 1, "c": [1, 2]}, "d": 1}
    merged = deep_merge(base, {"a": {"c": [3], "e": 2}, "f": {"g": 1}})

    assert merged == {"a": {"b": 1, "c": [3], "e": 2}, "d": 1, "f": {"g": 1}}
    assert base == {"a": {"b": 1, "c": [1, 2]}, "d": 1}


def test_an_adapter_block_is_replaced_whole_not_merged():
    base = {
        "bus": {
            "bus_adapter": {
                "adapter": "python_queue",
                "config": {"persistence_path": "x"},
            }
        }
    }
    overlay = {
        "bus": {
            "bus_adapter": {
                "adapter": "nats_jetstream",
                "config": {"nats_url": "nats://h:1"},
            }
        }
    }

    assert deep_merge(base, overlay) == overlay


def test_without_an_overlay_the_project_config_is_used(project):
    assert EngineConfiguration.load_configuration().nats is None


def test_an_overlay_adds_nats_mode_without_touching_the_project_config(
    project, monkeypatch
):
    overlay = project / "nats.overlay.yaml"
    overlay.write_text(
        "nats:\n"
        "  nats_url: nats://127.0.0.1:13042\n"
        "  jwt_secret: dev-secret-0123456789abcdef0123456789abcdef\n"
        "  discovery: {project: dev}\n"
        "services:\n"
        "  bus: {bus_adapter: {adapter: nats_jetstream, config: {nats_url: 'nats://127.0.0.1:13042'}}}\n"
    )
    monkeypatch.setenv("ABI_CONFIG_OVERLAY", str(overlay))

    config = EngineConfiguration.load_configuration()

    assert config.nats.nats_url == "nats://127.0.0.1:13042"
    assert config.nats.discovery.project == "dev"
    assert config.services.kv.kv_adapter.adapter == "python"
    assert config.services.bus.bus_adapter.adapter == "nats_jetstream"
    assert (project / "config.yaml").read_text() == BASE


def test_a_missing_overlay_file_is_a_clear_error(project, monkeypatch):
    monkeypatch.setenv("ABI_CONFIG_OVERLAY", str(project / "missing.yaml"))

    with pytest.raises(FileNotFoundError, match="ABI_CONFIG_OVERLAY"):
        EngineConfiguration.load_configuration()
