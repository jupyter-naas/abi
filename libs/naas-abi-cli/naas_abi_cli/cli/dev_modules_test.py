import json
import sys

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
    DevModuleConfiguration,
)

from naas_abi_cli.cli.dev_modules import (
    load_dev_modules,
    module_command,
    module_environment,
    read_overlay,
)

KEY = "abi_sk_abcdefghijklmnop_c2VjcmV0"
OVERLAY = {
    "nats": {
        # The engine's login; a module logs in with its own key instead.
        "nats_url": "nats://engine:nats-engine-password@127.0.0.1:13042",
        "discovery": {"project": "zen"},
    }
}
MODULE = DevModuleConfiguration(
    name="probe-researcher",
    module="operations.projects.nats_probe",
    args=["researcher"],
    env={"NATS_PROBE_DISCOVERY_PROJECT": "${ABI_DISCOVERY_PROJECT}", "KEEP": "$$1"},
)


def test_a_module_gets_the_dev_broker_and_its_own_key_only(tmp_path):
    base = {
        "HOME": "/home/me",
        "NATS_ENGINE_PASSWORD": "engine-pw",
        "NATS_AUTH_CALLOUT_SEED": "SA-seed",
        "iam/signing-keys/20261015-0a1b2c3d": "private",
        "ABI_SERVICE_KEY": "abi_sk_someone-elses",
    }
    env = module_environment(MODULE, OVERLAY, tmp_path, base, service_key=KEY)

    assert env["HOME"] == "/home/me"
    assert env["ABI_NATS_URL"] == "nats://127.0.0.1:13042"
    assert env["ABI_SERVICE_KEY"] == KEY
    assert env["ABI_DISCOVERY_PROJECT"] == "zen"
    # No signing secret, broker login or other credential reaches it.
    for withheld in (
        "NATS_ENGINE_PASSWORD",
        "NATS_AUTH_CALLOUT_SEED",
        "NATS_JWT_SECRET",
    ):
        assert withheld not in env
    assert not any(key.startswith("iam/") for key in env)
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in env


def test_a_module_runs_as_its_own_module_id():
    assert MODULE.identity == "probe-researcher"
    named = DevModuleConfiguration(name="people", module="m", module_id="acme.people")
    assert named.identity == "acme.people"


def test_module_env_names_the_dev_settings(tmp_path):
    env = module_environment(MODULE, OVERLAY, tmp_path, {}, service_key=KEY)

    assert env["NATS_PROBE_DISCOVERY_PROJECT"] == "zen"
    assert env["KEEP"] == "$1"


def test_tracing_and_the_src_layout_reach_the_module(tmp_path):
    (tmp_path / "src").mkdir()
    overlay = {
        **OVERLAY,
        "telemetry": {"enabled": True, "otlp_endpoint": "http://127.0.0.1:16000"},
    }

    env = module_environment(
        MODULE, overlay, tmp_path, {"PYTHONPATH": "/x"}, service_key=KEY
    )

    assert env["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://127.0.0.1:16000"
    assert env["PYTHONPATH"].split(":") == [str(tmp_path / "src"), "/x"]


def test_the_module_runs_under_the_supervisor():
    command = module_command(MODULE)

    assert command[:3] == [sys.executable, "-m", "naas_abi_cli.cli.dev_supervisor"]
    assert command[command.index("--restart") + 1] == "on-failure"
    assert command[command.index("--") + 1 :] == [
        sys.executable,
        "-m",
        "operations.projects.nats_probe",
        "researcher",
    ]


def test_the_overlay_is_json_after_its_comment(tmp_path):
    path = tmp_path / "dev.overlay.yaml"
    path.write_text("# generated\n" + json.dumps(OVERLAY))

    assert read_overlay(path) == OVERLAY


def test_only_enabled_modules_are_loaded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    (tmp_path / "config.yaml").write_text(
        "dev:\n"
        "  modules:\n"
        "    - {name: first, module: a}\n"
        "    - {name: second, module: b, enabled: false}\n"
    )

    assert list(load_dev_modules()) == ["first"]


def test_no_config_means_no_modules(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)

    assert load_dev_modules() == {}


def test_an_invalid_dev_block_is_reported(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    (tmp_path / "config.yaml").write_text("dev:\n  modules: [{name: x}]\n")

    with pytest.raises(ValueError, match="module"):
        load_dev_modules()
