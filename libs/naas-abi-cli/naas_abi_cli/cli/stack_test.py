import importlib

import click
import pytest


stack_module = importlib.import_module("naas_abi_cli.cli.stack")


def test_start_stack_opens_service_portal_when_compose_succeeds(monkeypatch) -> None:
    opened: list[str] = []

    monkeypatch.setattr(stack_module, "run_compose", lambda args: None)
    monkeypatch.setattr(stack_module, "_get_error_services", lambda: [])
    monkeypatch.setattr(stack_module.webbrowser, "open", lambda url: opened.append(url))

    stack_module._start_stack()

    assert opened == [stack_module.SERVICE_PORTAL_URL]


def test_start_stack_retries_compose_up_before_succeeding(monkeypatch) -> None:
    attempts = {"count": 0}
    messages: list[str] = []

    def _flaky_compose(args: list[str]) -> None:
        assert args == ["up", "-d"]
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise click.ClickException("temporary failure")

    monkeypatch.setattr(stack_module, "run_compose", _flaky_compose)
    monkeypatch.setattr(stack_module, "_get_error_services", lambda: [])
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
    monkeypatch.setattr(stack_module, "_get_error_services", lambda: [])

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
