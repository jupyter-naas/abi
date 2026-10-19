"""``abi iam``: service accounts, their keys, and module permission manifests.

docs/specs/rfcs/20261013_identity-and-authorization.md, §8. The commands open
the project's IAM store from its config (``services.iam``), as the operator
who holds that config, and act as the engine's own service account. After a
change they tell a running engine (``abi.iam.v1.changed``) so it drops its
cache at once instead of within a minute.

    abi iam service-account create ci/nightly --key
    abi iam service-account list
    abi iam service-account delete ci/nightly
    abi iam key create ci/nightly            # prints the key, once
    abi iam key list ci/nightly
    abi iam key rotate ci/nightly <key id>   # new key, old one revoked
    abi iam key revoke ci/nightly <key id>
    abi iam module list --status pending
    abi iam module approve module/acme/people [--document narrowed.yaml]
    abi iam module reject module/acme/people --reason "too wide"
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import click

# Tests and tooling swap the IAM the commands act on: a callable returning
# (an IIAMService, a function notifying the running engine of a change).
IAMOpener = Callable[[], tuple[Any, Callable[[], None]]]


def open_project_iam() -> tuple[Any, Callable[[], None]]:
    """The project's IAM, from its config, and a change notifier."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )
    from naas_abi_core.services.iam.adapters.secondary.IAMSecretsSecretService import (
        IAMSecretsSecretService,
    )

    try:
        configuration = EngineConfiguration.load_configuration()
        settings, secret = configuration.services.iam, configuration.services.secret
        nats_url = configuration.nats.nats_url if configuration.nats else None
    except Exception:  # noqa: BLE001 - a secret IAM does not need is missing
        settings, secret, nats_url = _iam_blocks()
    if settings.store.adapter == "memory":
        raise click.ClickException(
            "services.iam.store is in memory: only the engine holding it can "
            "change it. Configure the sqlite or postgres store."
        )
    iam = settings.load(secrets=IAMSecretsSecretService(secret.load_local))

    def notify() -> None:
        if nats_url:
            notify_engine(nats_url, iam.store.revision())

    return iam, notify


def _iam_blocks() -> tuple[Any, Any, str | None]:
    """``services.iam`` and ``services.secret`` alone, rendered without secrets:
    for a project whose other blocks name secrets this shell lacks (a sqlite
    store needs none). No broker login either, so no change notice."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_IAMService import (
        IAMServiceConfiguration,
    )
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_SecretService import (
        SecretServiceConfiguration,
    )

    path = Path(EngineConfiguration.configuration_file())
    data = EngineConfiguration.render_without_secrets(
        path.read_text(encoding="utf-8"), base_dir=str(path.resolve().parent)
    )
    services = (data or {}).get("services") or {}
    settings = IAMServiceConfiguration.model_validate(services.get("iam") or {})
    if settings.store.adapter == "postgres":
        raise click.ClickException(
            "services.iam.store is PostgreSQL and its DSN names secrets this shell "
            "lacks: provide them (environment or .env) to run abi iam"
        )
    secret = SecretServiceConfiguration.model_validate(
        services.get("secret")
        or {"secret_adapters": [{"adapter": "dotenv", "config": {"path": ".env"}}]}
    )
    return settings, secret, None


def notify_engine(nats_url: str, revision: int) -> None:
    """Publish ``abi.iam.v1.changed``: a running engine drops its IAM cache.
    Best effort: without one, changes reach it within a minute anyway."""
    import asyncio

    async def publish() -> None:
        import nats
        from naas_abi_proto.iam.v1 import iam_pb2

        nc = await nats.connect(
            nats_url, allow_reconnect=False, connect_timeout=2, max_reconnect_attempts=0
        )
        try:
            await nc.publish(
                "abi.iam.v1.changed",
                iam_pb2.ChangeEvent(revision=revision).SerializeToString(),
            )
            await nc.flush(timeout=2)
        finally:
            await nc.close()

    # No engine running: nothing to tell.
    with contextlib.suppress(Exception):
        asyncio.run(publish())


@contextmanager
def _iam(ctx: click.Context, *, change: bool = False) -> Iterator[Any]:
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.iam.IAMPorts import IAMError

    opener: IAMOpener = (ctx.obj or {}).get("iam_opener", open_project_iam)
    iam, notify = opener()
    try:
        with as_service_account("engine"):
            yield iam
        if change:
            notify()
    except (IAMError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        iam.close()


def _account(iam: Any, ref: str) -> Any:
    """A service account by ``sa_`` id or by name."""
    if ref.startswith("sa_"):
        return iam.get_principal(ref)
    return iam.find_service_account(ref)


def _when(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC") if value else "-"


def _show_key(value: str) -> None:
    click.echo(value)
    click.echo("Shown once: store it now (as ABI_SERVICE_KEY for a module).", err=True)


@click.group("iam")
def iam() -> None:
    """Service accounts, keys and module permission manifests."""


# -- service accounts -------------------------------------------------------------


@iam.group("service-account")
def service_account() -> None:
    """Accounts for modules (module/<project>/<id>), scripts and CI (ci/<name>)."""


@service_account.command("create")
@click.argument("name")
@click.option("--key", "with_key", is_flag=True, help="Create a key for it too.")
@click.pass_context
def service_account_create(ctx: click.Context, name: str, with_key: bool) -> None:
    """Create the service account NAME."""
    with _iam(ctx, change=True) as service:
        record = service.create_service_account(name)
        click.echo(f"{record.id}\t{record.name}")
        if with_key:
            _show_key(service.create_key(record.id, description="abi iam").value)


@service_account.command("list")
@click.pass_context
def service_account_list(ctx: click.Context) -> None:
    """List the service accounts."""
    with _iam(ctx) as service:
        after = None
        while True:
            page = service.list_principals("service_account", limit=200, after=after)
            for record in page.items:
                click.echo(f"{record.id}\t{record.status}\t{record.name}")
            if page.next_after is None:
                return
            after = page.next_after


@service_account.command("delete")
@click.argument("account")
@click.pass_context
def service_account_delete(ctx: click.Context, account: str) -> None:
    """Delete ACCOUNT (a name or an sa_ id): its keys stop at once."""
    with _iam(ctx, change=True) as service:
        record = service.delete_principal(_account(service, account).id)
        click.echo(f"{record.id}\t{record.status}\t{record.name}")


# -- keys -----------------------------------------------------------------------------


@iam.group("key")
def key() -> None:
    """Service keys (abi_sk_...): stored hashed, shown once."""


@key.command("create")
@click.argument("account")
@click.option("--description", default="", help="What the key is for.")
@click.option(
    "--expires-in-days", type=click.IntRange(min=1), help="Default: never (ci/*: 90)."
)
@click.pass_context
def key_create(
    ctx: click.Context, account: str, description: str, expires_in_days: int | None
) -> None:
    """Create a key for ACCOUNT and print it, once."""
    expires_at = (
        datetime.now(UTC) + timedelta(days=expires_in_days) if expires_in_days else None
    )
    with _iam(ctx, change=True) as service:
        record = _account(service, account)
        created = service.create_key(
            record.id, description=description, expires_at=expires_at
        )
        click.echo(f"key {created.record.key_id} of {record.name}", err=True)
        _show_key(created.value)


@key.command("list")
@click.argument("account")
@click.pass_context
def key_list(ctx: click.Context, account: str) -> None:
    """List ACCOUNT's keys (never their values)."""
    with _iam(ctx) as service:
        record = _account(service, account)
        for found in service.list_keys(record.id):
            state = "revoked" if found.revoked_at else "active"
            click.echo(
                f"{found.key_id}\t{state}\tcreated {_when(found.created_at)}\t"
                f"expires {_when(found.expires_at)}\tused {_when(found.last_used_at)}"
                f"\t{found.description}"
            )


@key.command("revoke")
@click.argument("account")
@click.argument("key_id")
@click.pass_context
def key_revoke(ctx: click.Context, account: str, key_id: str) -> None:
    """Revoke KEY_ID: the next exchange and connection fail; tokens already
    issued expire within ten minutes."""
    with _iam(ctx, change=True) as service:
        revoked = service.revoke_key(_account(service, account).id, key_id)
        click.echo(f"{revoked.key_id}\trevoked {_when(revoked.revoked_at)}")


@key.command("rotate")
@click.argument("account")
@click.argument("key_id")
@click.pass_context
def key_rotate(ctx: click.Context, account: str, key_id: str) -> None:
    """Replace KEY_ID with a new key (printed once) and revoke it."""
    with _iam(ctx, change=True) as service:
        created = service.rotate_key(_account(service, account).id, key_id)
        click.echo(f"key {created.record.key_id} replaces {key_id}", err=True)
        _show_key(created.value)


# -- module manifests -------------------------------------------------------------------


@iam.group("module")
def module() -> None:
    """Module permission manifests: approve, narrow or reject."""


@module.command("list")
@click.option(
    "--status",
    type=click.Choice(["pending", "approved", "rejected", "superseded"]),
    help="Only manifests in this state.",
)
@click.pass_context
def module_list(ctx: click.Context, status: str | None) -> None:
    """List submitted manifests, oldest first."""
    with _iam(ctx) as service:
        for found in service.list_manifests(status=status):
            name = f"module/{found.project}/{found.module_id}"
            click.echo(
                f"{found.status}\t{name}\t{found.sha256[:12]}\t"
                f"submitted {_when(found.submitted_at)}"
            )


@module.command("show")
@click.argument("account")
@click.option("--sha256", help="A version; default: the latest submitted.")
@click.pass_context
def module_show(ctx: click.Context, account: str, sha256: str | None) -> None:
    """Print a manifest as submitted, to review or narrow it."""
    with _iam(ctx) as service:
        found = service.get_manifest(_account(service, account).id, sha256)
        click.echo(json.dumps(found.document, indent=2))


@module.command("approve")
@click.argument("account")
@click.option(
    "--sha256",
    help="The version to approve (`list` prints its first 12 characters); default: "
    "the latest pending one. Name it when you reviewed a particular manifest.",
)
@click.option(
    "--document",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Approve this policy document instead (narrowed), YAML or JSON.",
)
@click.pass_context
def module_approve(
    ctx: click.Context, account: str, sha256: str | None, document: Path | None
) -> None:
    """Approve ACCOUNT's manifest: it becomes its policy, module.<project>.<id>."""
    with _iam(ctx, change=True) as service:
        approved = service.approve_manifest(
            _account(service, account).id,
            sha256,
            document=document.read_text() if document else None,
        )
        click.echo(
            f"approved module/{approved.project}/{approved.module_id} "
            f"{approved.sha256[:12]}: the module reconnects with its new permissions"
        )


@module.command("reject")
@click.argument("account")
@click.option("--sha256", help="A version; default: the latest pending one.")
@click.option("--reason", default="", help="Shown to the module.")
@click.pass_context
def module_reject(
    ctx: click.Context, account: str, sha256: str | None, reason: str
) -> None:
    """Reject ACCOUNT's pending manifest."""
    with _iam(ctx, change=True) as service:
        rejected = service.reject_manifest(
            _account(service, account).id, sha256, reason=reason
        )
        click.echo(
            f"rejected module/{rejected.project}/{rejected.module_id} {rejected.sha256[:12]}"
        )


# -- abi dev up ---------------------------------------------------------------------------

DEV_KEY_DESCRIPTION = "abi dev up"


def provision_dev_modules(
    service: Any, project: str, module_ids: dict[str, str]
) -> dict[str, str]:
    """A fresh key for each dev module's account, created when missing.

    ``module_ids``: dev module name -> module id. Keys earlier runs of
    ``abi dev up`` made are revoked: each start hands out new ones. Runs as the
    engine's service account; the dev overlay auto-approves the manifests.
    """
    from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError

    keys: dict[str, str] = {}
    for name, module_id in module_ids.items():
        account_name = f"module/{project}/{module_id}"
        try:
            record = service.find_service_account(account_name)
        except IAMNotFoundError:
            record = service.create_service_account(account_name)
        if not record.active:
            raise click.ClickException(
                f"{account_name} is {record.status}: resume or recreate it first"
            )
        for found in service.list_keys(record.id):
            if found.description == DEV_KEY_DESCRIPTION and found.revoked_at is None:
                service.revoke_key(record.id, found.key_id)
        keys[name] = service.create_key(
            record.id, description=DEV_KEY_DESCRIPTION
        ).value
    return keys
