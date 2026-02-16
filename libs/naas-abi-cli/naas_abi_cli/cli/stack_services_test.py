from naas_abi_cli.cli.stack_runtime import ComposeServiceState
from naas_abi_cli.cli.stack_services import evaluate_service_readiness


def test_readiness_uses_docker_health_when_healthy() -> None:
    state = ComposeServiceState(
        service="postgres",
        container_name="project-postgres-1",
        state="running",
        health="healthy",
        exit_code=None,
        status="Up",
    )

    readiness = evaluate_service_readiness("postgres", state)
    assert readiness.ready is True
    assert readiness.source == "docker-health"


def test_readiness_detects_one_shot_completed() -> None:
    state = ComposeServiceState(
        service="minio-init",
        container_name="project-minio-init-1",
        state="exited",
        health=None,
        exit_code=0,
        status="Exited (0)",
    )

    readiness = evaluate_service_readiness("minio-init", state)
    assert readiness.ready is True


def test_readiness_is_false_when_not_running_without_health() -> None:
    state = ComposeServiceState(
        service="qdrant",
        container_name="project-qdrant-1",
        state="created",
        health=None,
        exit_code=None,
        status="Created",
    )

    readiness = evaluate_service_readiness("qdrant", state)
    assert readiness.ready is False
    assert readiness.source == "compose"
