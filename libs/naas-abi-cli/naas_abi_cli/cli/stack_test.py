import importlib
from naas_abi_cli.cli.stack_runtime import ComposeServiceState
from naas_abi_cli.cli.stack_services import ReadinessResult


stack_module = importlib.import_module("naas_abi_cli.cli.stack")


def test_is_container_in_error_detects_unhealthy_container() -> None:
    state = ComposeServiceState(
        service="abi",
        container_name="abi-1",
        state="running",
        health="unhealthy",
        exit_code=None,
        status="Up",
    )

    assert stack_module._is_container_in_error("abi", state) is True


def test_is_container_in_error_ignores_successful_one_shot_exit() -> None:
    state = ComposeServiceState(
        service="minio-init",
        container_name="minio-init-1",
        state="exited",
        health=None,
        exit_code=0,
        status="Exited (0)",
    )

    assert stack_module._is_container_in_error("minio-init", state) is False


def test_wait_for_stack_readiness_requires_abi_health(monkeypatch) -> None:
    states = {
        "abi": ComposeServiceState(
            service="abi",
            container_name="abi-1",
            state="running",
            health="healthy",
            exit_code=None,
            status="Up",
        ),
        "service-portal": ComposeServiceState(
            service="service-portal",
            container_name="service-portal-1",
            state="running",
            health=None,
            exit_code=None,
            status="Up",
        ),
    }

    monkeypatch.setattr(
        stack_module, "compose_service_list", lambda: ["abi", "service-portal"]
    )
    monkeypatch.setattr(stack_module, "compose_service_states", lambda: states)
    monkeypatch.setattr(
        stack_module,
        "evaluate_service_readiness",
        lambda service_name, state: ReadinessResult(True, "compose", "ready"),
    )

    ready, error_services = stack_module._wait_for_stack_readiness(
        timeout_seconds=1,
        poll_interval_seconds=0,
    )
    assert ready is True
    assert error_services == []


def test_wait_for_stack_readiness_returns_error_services(monkeypatch) -> None:
    states = {
        "abi": ComposeServiceState(
            service="abi",
            container_name="abi-1",
            state="running",
            health="healthy",
            exit_code=None,
            status="Up",
        ),
        "postgres": ComposeServiceState(
            service="postgres",
            container_name="postgres-1",
            state="exited",
            health=None,
            exit_code=1,
            status="Exited (1)",
        ),
    }

    monkeypatch.setattr(
        stack_module, "compose_service_list", lambda: ["abi", "postgres"]
    )
    monkeypatch.setattr(stack_module, "compose_service_states", lambda: states)

    ready, error_services = stack_module._wait_for_stack_readiness(
        timeout_seconds=1,
        poll_interval_seconds=0,
    )
    assert ready is False
    assert error_services == ["postgres"]
