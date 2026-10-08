import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
    DevConfiguration,
    DevModuleConfiguration,
    load_dev_configuration,
)
from pydantic import ValidationError

BASE = (
    "api: {}\n"
    "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
    "modules: []\n"
    "services:\n"
    "  secret: {secret_adapters: []}\n"
    "  kv: {kv_adapter: {adapter: python, config: {}}}\n"
    "  bus: {bus_adapter: {adapter: python_queue, config: {}}}\n"
)

DEV = (
    "dev:\n"
    "  modules:\n"
    "    - name: probe-researcher\n"
    "      module: operations.projects.nats_probe\n"
    "      args: [researcher]\n"
    "      env:\n"
    '        PROBE_PROJECT: "${ABI_DISCOVERY_PROJECT}"\n'
    "    - name: worker\n"
    "      module: my_worker\n"
    "      enabled: false\n"
    "      restart: never\n"
)


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    EngineConfiguration.reset_configuration_cache()
    yield tmp_path
    EngineConfiguration.reset_configuration_cache()


def test_the_dev_block_lists_sdk_modules_with_defaults(project):
    (project / "config.yaml").write_text(BASE + DEV)

    dev = load_dev_configuration()

    researcher, worker = dev.modules
    assert researcher == DevModuleConfiguration(
        name="probe-researcher",
        module="operations.projects.nats_probe",
        args=["researcher"],
        env={"PROBE_PROJECT": "${ABI_DISCOVERY_PROJECT}"},
    )
    assert researcher.enabled and researcher.restart == "on-failure"
    assert not worker.enabled and worker.restart == "never"
    assert [m.name for m in dev.enabled_modules()] == ["probe-researcher"]


def test_a_config_without_a_dev_block_runs_no_modules(project):
    (project / "config.yaml").write_text(BASE)

    assert load_dev_configuration().modules == []


def test_the_dev_block_is_read_from_the_config_the_engine_loads(project, monkeypatch):
    (project / "config.yaml").write_text(BASE)
    (project / "config.local.yaml").write_text(BASE + DEV)
    monkeypatch.setenv("ENV", "local")

    assert EngineConfiguration.configuration_file() == "config.local.yaml"
    assert len(load_dev_configuration().modules) == 2


def test_templates_render_without_secrets(project):
    # {{ secret.X }} must not fail the CLI: it has no secret service.
    (project / "config.yaml").write_text(
        BASE + "dev:\n"
        "  modules:\n"
        "    - name: worker\n"
        "      module: my_worker\n"
        '      env: {TOKEN: "{{ secret.NOT_SET }}"}\n'
    )

    assert load_dev_configuration().modules[0].env == {"TOKEN": ""}


@pytest.mark.parametrize(
    "module",
    [
        {"name": "Bad Name", "module": "m"},
        {"name": "ok", "module": ""},
        {"name": "ok", "module": "m", "restart": "sometimes"},
        {"name": "ok", "module": "m", "unknown": 1},
    ],
)
def test_invalid_modules_are_refused(module):
    with pytest.raises(ValidationError):
        DevConfiguration(modules=[module])


def test_module_names_are_unique():
    with pytest.raises(ValidationError, match="unique"):
        DevConfiguration(
            modules=[{"name": "a", "module": "m"}, {"name": "a", "module": "n"}]
        )


def test_the_engine_validates_the_dev_block_and_ignores_it_otherwise():
    configuration = EngineConfiguration.from_yaml_content(BASE + DEV)

    assert [m.name for m in configuration.dev.modules] == ["probe-researcher", "worker"]
    with pytest.raises(ValidationError):
        EngineConfiguration.from_yaml_content(BASE + "dev:\n  modules: [{name: x}]\n")
