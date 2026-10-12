from pathlib import Path

from naas_abi_cli.cli.deploy.deploy import COMPOSE_OVERRIDE, _compose_command


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
