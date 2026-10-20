import importlib
from pathlib import Path

import pytest
from click.testing import CliRunner

from naas_abi_cli.cli.deploy.deploy import COMPOSE_OVERRIDE, _compose_command

# The package re-exports the `deploy` group under the module's name.
deploy_module = importlib.import_module("naas_abi_cli.cli.deploy.deploy")


def test_compose_command_uses_the_project_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    command = _compose_command("up", "-d")

    assert command[:4] == ["docker", "compose", "--file", "docker-compose.yml"]
    assert COMPOSE_OVERRIDE not in command
    assert command[-2:] == ["up", "-d"]


def test_compose_command_adds_the_override_with_the_remote_modules(
    tmp_path: Path, monkeypatch
) -> None:
    """`--file` turns off Compose's own lookup of the override, where
    `abi new module` declares the remote modules."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / COMPOSE_OVERRIDE).write_text("services: {}\n")

    command = _compose_command("down")

    files = [command[i + 1] for i, arg in enumerate(command) if arg == "--file"]
    assert files == ["docker-compose.yml", COMPOSE_OVERRIDE]


@pytest.mark.parametrize(("nats", "extras_added"), [(False, True), (True, False)])
def test_deploy_local_adds_the_legacy_extras_only_without_nats(
    tmp_path: Path, monkeypatch, nats: bool, extras_added: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    block = 'nats:\n  nats_url: "nats://nats:4222"\n' if nats else ""
    (tmp_path / "config.local.yaml").write_text("api: {}\n" + block)
    added: list[str] = []
    monkeypatch.setattr(deploy_module, "setup_local_deploy", lambda *a, **k: None)
    monkeypatch.setattr(deploy_module, "ensure_legacy_extras", added.append)

    result = CliRunner().invoke(deploy_module.deploy, ["local"])

    assert result.exit_code == 0, result.output
    assert added == ([str(tmp_path)] if extras_added else [])
