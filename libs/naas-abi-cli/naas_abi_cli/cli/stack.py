import time
import webbrowser

import click
from rich.console import Console
from rich.table import Table

from .stack_runtime import (
    ComposeServiceState,
    compose_logs_follow,
    compose_service_logs,
    compose_service_list,
    compose_service_states,
    run_compose,
)
from .stack_services import SERVICE_CATALOG, evaluate_service_readiness
from .stack_tui import StackTUI

SERVICE_PORTAL_URL = "http://127.0.0.1:8080/"


def _is_container_in_error(
    service_name: str, state: ComposeServiceState | None
) -> bool:
    if state is None:
        return False

    if state.health == "unhealthy":
        return True

    if state.state in {"dead", "removing"}:
        return True

    if state.state != "exited":
        return False

    service = SERVICE_CATALOG.get(service_name)
    if service and service.is_one_shot and state.exit_code == 0:
        return False

    return state.exit_code != 0


def _show_error_logs(error_services: list[str]) -> None:
    for service_name in error_services:
        click.echo(f"\nService '{service_name}' reported an error. Recent logs:")
        logs = compose_service_logs(service_name, tail=160).strip()
        if logs:
            click.echo(logs)
        else:
            click.echo("No logs were returned for this service.")


def _wait_for_stack_readiness(
    timeout_seconds: int = 180,
    poll_interval_seconds: float = 2,
) -> tuple[bool, list[str]]:
    services = compose_service_list()
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        states_by_name = compose_service_states()

        error_services = sorted(
            service_name
            for service_name in services
            if _is_container_in_error(service_name, states_by_name.get(service_name))
        )
        if error_services:
            return False, error_services

        abi_state = states_by_name.get("abi")
        abi_healthy = abi_state is not None and abi_state.health == "healthy"

        all_ready = abi_healthy
        if all_ready:
            for service_name in services:
                readiness = evaluate_service_readiness(
                    service_name, states_by_name.get(service_name)
                )
                if not readiness.ready:
                    all_ready = False
                    break

        if all_ready:
            return True, []

        time.sleep(poll_interval_seconds)

    return False, []


def _start_stack() -> None:
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            run_compose(["up", "-d"])
            break
        except click.ClickException:
            if attempt == max_retries:
                raise
            click.echo(
                "'docker compose up -d' failed. "
                f"Retrying ({attempt + 1}/{max_retries})..."
            )

    click.echo("Waiting for containers to become healthy and ready...")
    ready, error_services = _wait_for_stack_readiness()

    if error_services:
        _show_error_logs(error_services)
        click.echo(
            "\nThe stack did not start correctly because one or more containers are in error."
        )
        return

    if ready:
        webbrowser.open(SERVICE_PORTAL_URL)
        click.echo(f"Opened {SERVICE_PORTAL_URL}")
    else:
        click.echo(
            "Timed out while waiting for the stack to become ready. "
            f"Open it manually at {SERVICE_PORTAL_URL} once services are healthy."
        )


def _stop_stack(volumes: bool) -> None:
    arguments = ["down"]
    if volumes:
        arguments.append("-v")
    run_compose(arguments)


def _show_status() -> None:
    states_by_name = compose_service_states()
    defined_services = compose_service_list()
    table = Table(title="ABI Stack Status")
    table.add_column("Service")
    table.add_column("State")
    table.add_column("Health")
    table.add_column("Ready")
    table.add_column("Probe")

    all_services = sorted(set(defined_services) | set(SERVICE_CATALOG.keys()))
    for service_name in all_services:
        state = states_by_name.get(service_name)
        state_label = "not-created"
        health_label = "-"
        if state is not None:
            state_label = state.state
            health_label = state.health or "-"

        readiness = evaluate_service_readiness(service_name, state)
        ready_label = "yes" if readiness.ready else "no"
        probe_label = readiness.source
        table.add_row(service_name, state_label, health_label, ready_label, probe_label)

    Console().print(table)


@click.group("stack")
def stack() -> None:
    """Manage and inspect the local ABI stack."""


@stack.command("start")
def stack_start() -> None:
    _start_stack()


@stack.command("stop")
@click.option(
    "-v",
    "--volumes",
    is_flag=True,
    default=False,
    help="Remove volumes along with the containers.",
)
def stack_stop(volumes: bool) -> None:
    _stop_stack(volumes)


@stack.command("logs")
@click.argument("service", required=False)
def stack_logs(service: str | None) -> None:
    compose_logs_follow(service)


@stack.command("status")
def stack_status() -> None:
    _show_status()


@stack.command("tui")
@click.option(
    "--interval",
    type=float,
    default=1.5,
    show_default=True,
    help="Refresh interval in seconds.",
)
def stack_tui(interval: float) -> None:
    StackTUI(refresh_interval=interval).run()


@click.command("start")
def start() -> None:
    _start_stack()


@click.command("stop")
@click.option(
    "-v",
    "--volumes",
    is_flag=True,
    default=False,
    help="Remove volumes along with the containers.",
)
def stop(volumes: bool) -> None:
    _stop_stack(volumes)


@click.command("logs")
@click.argument("service", required=False)
def logs(service: str | None) -> None:
    compose_logs_follow(service)
