"""Start the built-in identity provider of a generated stack (#1643).

The `idp` service of a generated NATS stack logs in to the broker with its own
service key (the account ``module/<project>/idp``) and asks for its permissions
with a manifest the platform approves. Before this, an operator did it by hand
once the stack was up, and until then Nexus said "The identity provider cannot
be reached right now". `abi stack start` now does it:

1. when ``.env`` has no ``IDP_SERVICE_KEY``, creates the account's key inside
   the `abi` container (``abi iam``, which reaches the stack's IAM store) and
   writes it there, never printing it;
2. starts `idp` again, so it reads the key;
3. approves the idp account's pending manifest, and no other account's.

A later start finds the key and an approved manifest and does nothing.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
import yaml

from .admin_credentials import _read, _set, _value, _write
from .stack_runtime import run_compose

IDP_SERVICE = "idp"
IDP_SERVICE_KEY = "IDP_SERVICE_KEY"
KEY_PREFIX = "abi_sk_"
KEY_DESCRIPTION = "idp (abi stack start)"
# The idp submits its manifest once it is connected: a few seconds after start.
APPROVE_TIMEOUT_SECONDS = 120.0
APPROVE_POLL_SECONDS = 5.0

Compose = Callable[..., Any]


def idp_account(project: Path) -> str | None:
    """``module/<project>/idp`` when the project's docker-compose.yml runs the
    built-in IdP (the `idp` service), else None."""
    compose_file = project / "docker-compose.yml"
    if not compose_file.exists():
        return None
    try:
        data = yaml.safe_load(compose_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    service = (data.get("services") or {}).get(IDP_SERVICE)
    if not isinstance(service, dict):
        return None
    environment = service.get("environment") or {}
    if isinstance(environment, list):
        environment = dict(
            entry.split("=", 1) for entry in environment if "=" in str(entry)
        )
    discovery = str(environment.get("ABI_DISCOVERY_PROJECT") or "").strip()
    return f"module/{discovery}/{IDP_SERVICE}" if discovery else None


def _abi_iam(compose: Compose, *args: str) -> str:
    """``abi iam ARGS`` in the `abi` container, its output captured."""
    result = compose(
        ["exec", "-T", "abi", "uv", "run", "--no-dev", "abi", "iam", *args],
        capture_output=True,
    )
    return result.stdout or ""


def _key_in(output: str) -> str | None:
    for line in output.splitlines():
        if line.strip().startswith(KEY_PREFIX):
            return line.strip()
    return None


def _create_key(compose: Compose, account: str) -> str:
    """A new key of ``account``, creating the account when it is missing."""
    try:
        output = _abi_iam(compose, "service-account", "create", account, "--key")
    except click.ClickException:
        # The account exists (an earlier start, or created by hand).
        output = _abi_iam(
            compose, "key", "create", account, "--description", KEY_DESCRIPTION
        )
    key = _key_in(output)
    if key is None:
        raise click.ClickException(f"{account}: `abi iam` printed no key")
    return key


def _manifest_states(compose: Compose, account: str) -> list[tuple[str, str]]:
    """(status, sha256 prefix) of ``account``'s manifests, oldest first."""
    states: list[tuple[str, str]] = []
    for line in _abi_iam(compose, "module", "list").splitlines():
        fields = line.split("\t")
        if len(fields) >= 3 and fields[1] == account:
            states.append((fields[0], fields[2]))
    return states


def _approve(
    compose: Compose,
    account: str,
    *,
    sleep: Callable[[float], None],
    timeout: float,
    poll: float,
) -> bool:
    """Approve ``account``'s pending manifest, waiting for the idp to submit
    one when it has none yet. True once one is in force."""
    waited = 0.0
    while True:
        states = _manifest_states(compose, account)
        pending = [sha for status, sha in states if status == "pending"]
        if pending:
            _abi_iam(compose, "module", "approve", account)
            click.echo(f"{account}: permissions approved ({pending[-1]})")
            return True
        if any(status == "approved" for status, _ in states):
            return True
        if waited >= timeout:
            return False
        sleep(poll)
        waited += poll


def bootstrap_idp(
    project: Path,
    *,
    compose: Compose = run_compose,
    sleep: Callable[[float], None] = time.sleep,
    timeout: float = APPROVE_TIMEOUT_SECONDS,
    poll: float = APPROVE_POLL_SECONDS,
) -> None:
    """Give the stack's idp its key and its permissions, when it lacks them.

    A failure is reported with the manual steps and does not stop the stack:
    everything else runs, only sign-in waits for the idp.
    """
    account = idp_account(project)
    if account is None:
        return
    env_path = project / ".env"
    try:
        key = _value(_read(env_path), IDP_SERVICE_KEY) or ""
        if not key.startswith(KEY_PREFIX):
            key = _create_key(compose, account)
            _write(env_path, _set(_read(env_path), IDP_SERVICE_KEY, key))
            click.echo(f"{account}: service key written to .env ({IDP_SERVICE_KEY})")
            # Recreated: the container reads the key from its environment.
            compose(["up", "-d", IDP_SERVICE])
        if not _approve(compose, account, sleep=sleep, timeout=timeout, poll=poll):
            click.secho(
                f"{account}: no permission manifest after {int(timeout)} s, sign-in "
                "waits for it. Check `docker compose logs idp`, then "
                f"`abi iam module approve {account}`.",
                fg="yellow",
            )
    except click.ClickException as exc:
        click.secho(
            f"The identity provider is not started ({exc.message}). By hand: "
            f"`abi iam service-account create {account} --key`, the key into .env "
            f"as {IDP_SERVICE_KEY}, `docker compose up -d idp`, then "
            f"`abi iam module approve {account}`.",
            fg="yellow",
        )
