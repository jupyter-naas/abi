import json
import subprocess
from dataclasses import dataclass

import click


@dataclass(frozen=True)
class ComposeServiceState:
    service: str
    container_name: str | None
    state: str
    health: str | None
    exit_code: int | None
    status: str | None


def run_compose(
    args: list[str], capture_output: bool = False
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["docker", "compose", *args],
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except FileNotFoundError as error:
        raise click.ClickException(
            "Docker is not installed or not available in PATH."
        ) from error
    except subprocess.CalledProcessError as error:
        raise click.ClickException(
            f"docker compose {' '.join(args)} failed with exit code {error.returncode}."
        ) from error


def compose_service_list() -> list[str]:
    result = run_compose(["config", "--services"], capture_output=True)
    services = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return services


def _parse_ps_json(raw_json: str) -> list[dict]:
    raw_json = raw_json.strip()
    if raw_json == "":
        return []

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        rows: list[dict] = []
        for line in raw_json.splitlines():
            line = line.strip()
            if line == "":
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                rows.append(candidate)
        return rows

    if isinstance(parsed, list):
        return parsed

    if isinstance(parsed, dict):
        return [parsed]

    return []


def compose_service_states() -> dict[str, ComposeServiceState]:
    result = run_compose(["ps", "-a", "--format", "json"], capture_output=True)
    rows = _parse_ps_json(result.stdout)
    states: dict[str, ComposeServiceState] = {}

    for row in rows:
        service_name = row.get("Service") or row.get("Name")
        if not service_name:
            continue

        exit_code = row.get("ExitCode")
        if isinstance(exit_code, str) and exit_code.isdigit():
            parsed_exit_code: int | None = int(exit_code)
        elif isinstance(exit_code, int):
            parsed_exit_code = exit_code
        else:
            parsed_exit_code = None

        states[service_name] = ComposeServiceState(
            service=service_name,
            container_name=row.get("Name"),
            state=(row.get("State") or "unknown").lower(),
            health=row.get("Health"),
            exit_code=parsed_exit_code,
            status=row.get("Status"),
        )

    return states


def compose_service_logs(service: str, tail: int = 120) -> str:
    result = run_compose(
        ["logs", "--no-color", f"--tail={tail}", service], capture_output=True
    )
    return result.stdout


def compose_logs_follow(service: str | None) -> None:
    args = ["logs", "-f"]
    if service:
        args.append(service)
    run_compose(args)
