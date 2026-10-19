import json
import os
import sys
import webbrowser
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlencode

import click
from rich.console import Console
from rich.table import Table

from .admin_credentials import (
    ensure_nats_passwords,
    ensure_nats_secret,
    ensure_rabbitmq_credentials,
)
from .deploy.local import project_uses_nats
from .stack_runtime import (
    ComposeServiceState,
    compose_logs_follow,
    compose_service_list,
    compose_service_logs,
    compose_service_states,
    run_compose,
)
from .stack_services import SERVICE_CATALOG, evaluate_service_readiness
from .stack_tui import StackTUI

# Dagster and the RabbitMQ bus, legacy: the ABI repository's docker-compose.yml
# keeps them behind this profile.
LEGACY_PROFILE = "legacy"
# The compose variable the repository's abi and dagster services pass on to the
# engine as ABI_CONFIG_OVERLAY. Its own name, so a shell's ABI_CONFIG_OVERLAY
# (a host path) never reaches the containers.
STACK_OVERLAY_ENV = "ABI_STACK_CONFIG_OVERLAY"
# Relative to the project, which the containers mount as their working directory.
LEGACY_OVERLAY = Path(".abi/stack/legacy.overlay.yaml")


@lru_cache(maxsize=1)
def _secret_service():
    """Load the secret service from the project's engine configuration.

    Returns None if the config can't be loaded (e.g. running outside a project).
    The dotenv adapter falls back to os.environ, so docker-compose-set vars work.
    """
    try:
        from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
            EngineConfiguration,
        )

        return EngineConfiguration.load_configuration().services.secret.load()
    except Exception:  # noqa: BLE001
        return None


def _get_secret(key: str, default: str | None = None) -> str | None:
    service = _secret_service()
    if service is None:
        import os

        return os.environ.get(key, default)
    value = service.get(key)
    return str(value) if value is not None else default


def _nexus_web_url() -> str:
    """Return the Nexus login URL with admin email pre-filled.

    Reads NEXUS_WEB_PORT and NEXUS_USER_ADMIN_EMAIL through the engine's
    secret service so any configured adapter (dotenv, Naas, …) resolves them.
    """
    port = _get_secret("NEXUS_WEB_PORT", "3042") or "3042"
    email = _get_secret("NEXUS_USER_ADMIN_EMAIL")
    if email:
        return f"http://127.0.0.1:{port}/auth/login?{urlencode({'email': email})}"
    return f"http://127.0.0.1:{port}/auth/login"


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


def _get_error_services() -> list[str]:
    services = compose_service_list()
    states_by_name = compose_service_states()
    return sorted(
        service_name
        for service_name in services
        if _is_container_in_error(service_name, states_by_name.get(service_name))
    )


def _show_error_logs(error_services: list[str]) -> None:
    for service_name in error_services:
        click.echo(f"\nService '{service_name}' reported an error. Recent logs:")
        logs = compose_service_logs(service_name, tail=160).strip()
        if logs:
            click.echo(logs)
        else:
            click.echo("No logs were returned for this service.")


def _ensure_stack_secrets(project: Path) -> None:
    """Generate the broker's passwords and the engine's NATS secret into
    ``.env`` before Compose reads it, when the project runs on NATS: the `nats`
    service refuses to start without its passwords, and the engine cannot
    render its `nats:` block without them. Kept when already set."""
    if not project_uses_nats(str(project)):
        return
    env_path = project / ".env"
    ensure_nats_passwords(env_path)
    ensure_nats_secret(env_path)


def _use_profile(profile: str) -> None:
    """Activate a Compose profile for every compose call of this command."""
    active = [p for p in os.environ.get("COMPOSE_PROFILES", "").split(",") if p]
    if profile not in active:
        os.environ["COMPOSE_PROFILES"] = ",".join([*active, profile])


def _require_legacy_profile() -> None:
    result = run_compose(["config", "--profiles"], capture_output=True)
    if LEGACY_PROFILE not in result.stdout.split():
        raise click.ClickException(
            f"This docker-compose.yml has no `{LEGACY_PROFILE}` profile. A generated "
            "project picks its stack when it is created (`abi new project "
            "--without-nats`, legacy) or deployed (`abi deploy local`)."
        )


def _write_legacy_overlay(project: Path) -> Path:
    """The engine config overlay of the legacy stack: the `nats:` block off,
    and the bus on the `rabbitmq` service. Holds the RabbitMQ password, so it is
    readable by its owner only."""
    user, password = ensure_rabbitmq_credentials(project / ".env")
    overlay = {
        "nats": None,
        "services": {
            "bus": {
                "bus_adapter": {
                    "adapter": "rabbitmq",
                    "config": {
                        "rabbitmq_url": (
                            f"amqp://{quote(user, safe='')}:{quote(password, safe='')}"
                            "@rabbitmq:5672"
                        )
                    },
                }
            }
        },
    }
    path = project / LEGACY_OVERLAY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(
        "# Written by `abi stack start --legacy`: the engine without NATS, its bus\n"
        "# on RabbitMQ. Rewritten on every legacy start; JSON is YAML.\n"
        + json.dumps(overlay, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return path


def _start_legacy_stack(project: Path) -> None:
    """Start the `legacy` profile too (Dagster, RabbitMQ) and run the engine
    without NATS, its bus on RabbitMQ."""
    _require_legacy_profile()
    overlay = _write_legacy_overlay(project)
    _use_profile(LEGACY_PROFILE)
    os.environ[STACK_OVERLAY_ENV] = overlay.relative_to(project).as_posix()
    click.echo(
        "Legacy stack: Dagster and the RabbitMQ bus, with the engine's `nats:` block "
        f"off ({LEGACY_OVERLAY}). They are legacy and will be removed in the next "
        "major."
    )


def _can_open_a_browser() -> bool:
    """Whether `webbrowser` would reach a graphical browser.

    On Linux without a display it falls back to a terminal browser, which holds
    `abi stack start` until someone quits it: a server reached over SSH.
    """
    if sys.platform in ("darwin", "win32") or os.environ.get("BROWSER"):
        return True
    # WSL hands the URL to the Windows browser.
    return bool(
        os.environ.get("DISPLAY")
        or os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("WSL_DISTRO_NAME")
    )


def _start_stack(legacy: bool = False) -> None:
    project = Path.cwd()
    _ensure_stack_secrets(project)
    if legacy:
        _start_legacy_stack(project)
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            run_compose(["up", "-d"])
        except click.ClickException:
            if attempt == max_retries:
                raise
            click.echo(
                "'docker compose up -d' failed. "
                f"Retrying ({attempt + 1}/{max_retries})..."
            )
            continue

        error_services = _get_error_services()
        if error_services:
            if attempt == max_retries:
                _show_error_logs(error_services)
                raise click.ClickException(
                    "One or more containers are in error after startup: "
                    f"{', '.join(error_services)}"
                )

            click.echo(
                "One or more containers are in error. "
                f"Retrying 'docker compose up -d' ({attempt + 1}/{max_retries})..."
            )
            continue

        url = _nexus_web_url()
        if _can_open_a_browser():
            webbrowser.open(url)
            click.echo(f"Opened {url}")
        else:
            click.echo(f"Open {url}")
        return


def _stop_stack(volumes: bool) -> None:
    # Containers of the legacy profile too, whichever way they were started.
    _use_profile(LEGACY_PROFILE)
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
@click.option(
    "--legacy",
    is_flag=True,
    default=False,
    help=(
        "Legacy, to be removed in the next major: also start the `legacy` "
        "profile (Dagster, RabbitMQ) and run the engine without NATS, its bus on "
        "RabbitMQ. Default: the stack on NATS."
    ),
)
def stack_start(legacy: bool) -> None:
    """Start the local Docker stack, on NATS."""
    _start_stack(legacy)


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
@click.option(
    "--legacy",
    is_flag=True,
    default=False,
    help=(
        "Legacy, to be removed in the next major: also start the `legacy` "
        "profile (Dagster, RabbitMQ) and run the engine without NATS, its bus on "
        "RabbitMQ. Default: the stack on NATS."
    ),
)
def start(legacy: bool) -> None:
    """Start the local Docker stack, on NATS."""
    _start_stack(legacy)


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
