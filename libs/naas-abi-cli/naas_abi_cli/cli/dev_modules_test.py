import json
import sys

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Dev import (
    DevModuleConfiguration,
)
from naas_abi_core.engine.nats_auth import verify_service_token

from naas_abi_cli.cli.dev_modules import (
    load_dev_modules,
    module_command,
    module_environment,
    read_overlay,
)

SECRET = "s" * 48
OVERLAY = {
    "nats": {
        "nats_url": "nats://127.0.0.1:13042",
        "jwt_secret": SECRET,
        "discovery": {"project": "zen"},
    }
}
MODULE = DevModuleConfiguration(
    name="probe-researcher",
    module="operations.projects.nats_probe",
    args=["researcher"],
    env={"NATS_PROBE_DISCOVERY_PROJECT": "${ABI_DISCOVERY_PROJECT}", "KEEP": "$$1"},
)


def test_a_module_gets_the_dev_broker_and_a_service_token(tmp_path):
    env = module_environment(MODULE, OVERLAY, tmp_path, {"HOME": "/home/me"})

    assert env["HOME"] == "/home/me"
    assert env["ABI_NATS_URL"] == "nats://127.0.0.1:13042"
    assert env["NATS_JWT_SECRET"] == SECRET
    assert env["ABI_DISCOVERY_PROJECT"] == "zen"
    assert verify_service_token(env["ABI_SERVICE_TOKEN"], SECRET) == "probe-researcher"
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in env


def test_module_env_names_the_dev_settings(tmp_path):
    env = module_environment(MODULE, OVERLAY, tmp_path, {})

    assert env["NATS_PROBE_DISCOVERY_PROJECT"] == "zen"
    assert env["KEEP"] == "$1"


def test_tracing_and_the_src_layout_reach_the_module(tmp_path):
    (tmp_path / "src").mkdir()
    overlay = {
        **OVERLAY,
        "telemetry": {"enabled": True, "otlp_endpoint": "http://127.0.0.1:16000"},
    }

    env = module_environment(MODULE, overlay, tmp_path, {"PYTHONPATH": "/x"})

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
