import time
import urllib.error
import urllib.request
import webbrowser

import click
from rich.console import Console
from rich.table import Table

from .stack_runtime import (
    compose_logs_follow,
    compose_service_list,
    compose_service_states,
    run_compose,
)
from .stack_services import SERVICE_CATALOG, evaluate_service_readiness
from .stack_tui import StackTUI

SERVICE_PORTAL_URL = "http://127.0.0.1:8080/"


def _wait_until_reachable(url: str, timeout_seconds: int = 120) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    return False


def _start_stack() -> None:
    run_compose(["up", "-d"])
    click.echo(f"Waiting for service portal at {SERVICE_PORTAL_URL}")
    if _wait_until_reachable(SERVICE_PORTAL_URL):
        webbrowser.open(SERVICE_PORTAL_URL)
        click.echo(f"Opened {SERVICE_PORTAL_URL}")
    else:
        click.echo(
            f"Service portal is not ready yet. Open it manually at {SERVICE_PORTAL_URL}."
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
