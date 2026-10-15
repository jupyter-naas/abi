import importlib
import json
import os
import stat
from pathlib import Path

import click
import pytest
import yaml

stack_module = importlib.import_module("naas_abi_cli.cli.stack")


@pytest.fixture(autouse=True)
def project(monkeypatch, tmp_path: Path) -> Path:
    """Run every stack command from an empty project: never the repository's
    own .env, and no profile or overlay left over from another test."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMPOSE_PROFILES", "")
    monkeypatch.setenv(stack_module.STACK_OVERLAY_ENV, "")
    return tmp_path


def _env(project: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in (project / ".env").read_text().splitlines()
        if "=" in line
    )


def _nats_project(project: Path) -> None:
    (project / "config.local.yaml").write_text(
        'nats:\n  nats_url: "nats://abi:{{ secret.NATS_ABI_PASSWORD }}@nats:4222"\n'
    )


class FakeCompose:
    """`docker compose` calls, with the environment each one would see."""

    def __init__(self, profiles: str = "legacy\n") -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.profiles = profiles

    def __call__(self, args: list[str], capture_output: bool = False):
        self.calls.append((args, dict(os.environ)))
        if args == ["config", "--profiles"]:
            return type("Result", (), {"stdout": self.profiles})()
        return None

    def env_of(self, command: str) -> dict[str, str]:
        return next(env for args, env in self.calls if command in args)


@pytest.fixture
def compose(monkeypatch) -> FakeCompose:
    fake = FakeCompose()
    monkeypatch.setattr(stack_module, "run_compose", fake)
    monkeypatch.setattr(stack_module, "_get_error_services", list)
    monkeypatch.setattr(stack_module.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(stack_module, "_nexus_web_url", lambda: "http://nexus/")
    return fake


def test_start_seeds_the_nats_secrets_before_compose_reads_env(
    project: Path, compose: FakeCompose
) -> None:
    """The nats service refuses to start without its passwords, and the engine
    cannot render its `nats:` block without them."""
    _nats_project(project)
    (project / ".env").write_text("NATS_ABI_PASSWORD=keep-this-password-please\n")

    stack_module._start_stack()

    env = _env(project)
    assert env["NATS_ABI_PASSWORD"] == "keep-this-password-please"
    assert len(env["NATS_MODULE_PASSWORD"]) >= 16
    assert len(env["NATS_JWT_SECRET"]) >= 32
    assert [args for args, _ in compose.calls] == [["up", "-d"]]
    up = compose.env_of("up")
    assert up["COMPOSE_PROFILES"] == ""
    assert up[stack_module.STACK_OVERLAY_ENV] == ""


def test_start_leaves_env_alone_for_a_project_without_nats(
    project: Path, compose: FakeCompose
) -> None:
    (project / "config.local.yaml").write_text("api:\n  title: classic\n")

    stack_module._start_stack()

    assert not (project / ".env").exists()


def test_legacy_start_runs_the_legacy_profile_without_nats(
    project: Path, compose: FakeCompose
) -> None:
    _nats_project(project)

    stack_module._start_stack(legacy=True)

    up = compose.env_of("up")
    assert up["COMPOSE_PROFILES"] == "legacy"
    overlay_path = up[stack_module.STACK_OVERLAY_ENV]
    assert overlay_path == ".abi/stack/legacy.overlay.yaml"
    overlay_file = project / overlay_path
    assert stat.S_IMODE(overlay_file.stat().st_mode) == 0o600
    overlay = yaml.safe_load(overlay_file.read_text())
    env = _env(project)
    assert overlay["nats"] is None
    assert overlay["services"]["bus"]["bus_adapter"] == {
        "adapter": "rabbitmq",
        "config": {
            "rabbitmq_url": (
                f"amqp://{env['RABBITMQ_USER']}:{env['RABBITMQ_PASSWORD']}@rabbitmq:5672"
            )
        },
    }
    # The nats service still runs in the default profile: its passwords too.
    assert len(env["NATS_ABI_PASSWORD"]) >= 16


def test_legacy_overlay_keeps_the_rabbitmq_credentials_of_env(
    project: Path, compose: FakeCompose
) -> None:
    (project / ".env").write_text("RABBITMQ_USER=me\nRABBITMQ_PASSWORD=p@ss/word\n")

    stack_module._start_stack(legacy=True)

    overlay = json.loads(
        "".join(
            line
            for line in (project / stack_module.LEGACY_OVERLAY).read_text().splitlines()
            if not line.startswith("#")
        )
    )
    url = overlay["services"]["bus"]["bus_adapter"]["config"]["rabbitmq_url"]
    assert url == "amqp://me:p%40ss%2Fword@rabbitmq:5672"


def test_legacy_start_refuses_a_stack_without_the_legacy_profile(
    compose: FakeCompose,
) -> None:
    """A generated project picks its stack when it is created or deployed."""
    compose.profiles = "nats\nrabbitmq\n"

    with pytest.raises(click.ClickException, match="no `legacy` profile"):
        stack_module._start_stack(legacy=True)

    assert [args for args, _ in compose.calls] == [["config", "--profiles"]]


def test_stop_takes_the_legacy_containers_down_too(compose: FakeCompose) -> None:
    stack_module._stop_stack(volumes=True)

    assert compose.calls[0][0] == ["down", "-v"]
    assert compose.calls[0][1]["COMPOSE_PROFILES"] == "legacy"


@pytest.mark.parametrize("command", [stack_module.stack_start, stack_module.start])
def test_start_help_labels_the_legacy_stack(command) -> None:
    from click.testing import CliRunner

    result = CliRunner().invoke(command, ["--help"])

    assert "--legacy" in result.output
    assert "Legacy, to be removed in the next major" in result.output


def test_start_stack_opens_nexus_when_compose_succeeds(monkeypatch) -> None:
    opened: list[str] = []

    monkeypatch.setattr(stack_module, "run_compose", lambda args: None)
    monkeypatch.setattr(stack_module, "_get_error_services", list)
    monkeypatch.setattr(stack_module.webbrowser, "open", lambda url: opened.append(url))
    monkeypatch.setattr(stack_module, "_nexus_web_url", lambda: "http://nexus/")

    stack_module._start_stack()

    assert opened == ["http://nexus/"]


def test_nexus_web_url_url_encodes_email(monkeypatch) -> None:
    monkeypatch.setattr(stack_module, "_secret_service", lambda: None)
    monkeypatch.setenv("NEXUS_WEB_PORT", "3042")
    monkeypatch.setenv("NEXUS_USER_ADMIN_EMAIL", "user+tag@example.com")

    assert stack_module._nexus_web_url() == (
        "http://127.0.0.1:3042/auth/login?email=user%2Btag%40example.com"
    )


def test_nexus_web_url_falls_back_when_email_missing(monkeypatch) -> None:
    monkeypatch.setattr(stack_module, "_secret_service", lambda: None)
    monkeypatch.delenv("NEXUS_USER_ADMIN_EMAIL", raising=False)
    monkeypatch.setenv("NEXUS_WEB_PORT", "3042")

    assert stack_module._nexus_web_url() == "http://127.0.0.1:3042/auth/login"


def test_start_stack_retries_compose_up_before_succeeding(monkeypatch) -> None:
    attempts = {"count": 0}
    messages: list[str] = []

    def _flaky_compose(args: list[str]) -> None:
        assert args == ["up", "-d"]
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise click.ClickException("temporary failure")

    monkeypatch.setattr(stack_module, "run_compose", _flaky_compose)
    monkeypatch.setattr(stack_module, "_get_error_services", list)
    monkeypatch.setattr(stack_module.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(
        stack_module.click, "echo", lambda message: messages.append(message)
    )

    stack_module._start_stack()

    assert attempts["count"] == 3
    assert any("Retrying" in message for message in messages)


def test_start_stack_fails_after_two_retries(monkeypatch) -> None:
    attempts = {"count": 0}

    def _always_failing_compose(args: list[str]) -> None:
        assert args == ["up", "-d"]
        attempts["count"] += 1
        raise click.ClickException("still failing")

    monkeypatch.setattr(stack_module, "run_compose", _always_failing_compose)
    monkeypatch.setattr(stack_module, "_get_error_services", list)

    with pytest.raises(click.ClickException, match="still failing"):
        stack_module._start_stack()

    assert attempts["count"] == 3


def test_start_stack_retries_when_container_is_in_error(monkeypatch) -> None:
    attempts = {"count": 0}
    checks = {"count": 0}
    messages: list[str] = []

    def _compose_ok(args: list[str]) -> None:
        assert args == ["up", "-d"]
        attempts["count"] += 1

    def _flaky_errors() -> list[str]:
        checks["count"] += 1
        if checks["count"] < 3:
            return ["rabbitmq"]
        return []

    monkeypatch.setattr(stack_module, "run_compose", _compose_ok)
    monkeypatch.setattr(stack_module, "_get_error_services", _flaky_errors)
    monkeypatch.setattr(stack_module.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(
        stack_module.click, "echo", lambda message: messages.append(message)
    )

    stack_module._start_stack()

    assert attempts["count"] == 3
    assert checks["count"] == 3
    assert any("containers are in error" in message for message in messages)


def test_start_stack_fails_after_container_error_retries_exhausted(monkeypatch) -> None:
    attempts = {"count": 0}
    logged: list[list[str]] = []

    def _compose_ok(args: list[str]) -> None:
        assert args == ["up", "-d"]
        attempts["count"] += 1

    monkeypatch.setattr(stack_module, "run_compose", _compose_ok)
    monkeypatch.setattr(stack_module, "_get_error_services", lambda: ["rabbitmq"])
    monkeypatch.setattr(
        stack_module, "_show_error_logs", lambda services: logged.append(services)
    )

    with pytest.raises(
        click.ClickException,
        match="containers are in error after startup: rabbitmq",
    ):
        stack_module._start_stack()

    assert attempts["count"] == 3
    assert logged == [["rabbitmq"]]
