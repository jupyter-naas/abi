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
    abi iam invite bob@example.com --workspace W --org O --role member
    abi iam invitation list [--email bob@example.com]
    abi iam invitation revoke pgr_...
    abi iam group bind acme "Data readers" --workspace W --org O --role viewer
    abi iam group unbind acme "Data readers" --workspace W --org O --role viewer
    abi iam group list

``invite`` and ``group`` act through the engine's services (RFC §12.2), like
``abi chat``: the running engine when there is one, as its own account. They
work with IAM's own names, an org id and a workspace id (the ones Nexus shows),
and never send mail: the Nexus invite (``abi user invite``) sends the
invitation email and keeps the invitation list.
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


def open_project_iam(
    nats_url: str | None = None,
) -> tuple[Any, Callable[[], None]]:
    """The project's IAM, from its config, and a change notifier.

    ``nats_url``: the broker to tell about a change, when it is not the one the
    config names (``abi dev up``'s own broker listens on another port)."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )
    from naas_abi_core.services.iam.adapters.secondary.IAMSecretsSecretService import (
        IAMSecretsSecretService,
    )

    try:
        configuration = EngineConfiguration.load_configuration()
        settings, secret = configuration.services.iam, configuration.services.secret
        configured_url = configuration.nats.nats_url if configuration.nats else None
    except Exception:  # noqa: BLE001 - a secret IAM does not need is missing
        settings, secret, configured_url = _iam_blocks()
    nats_url = nats_url or configured_url
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


NOTIFY_TIMEOUT_SECONDS = 5.0


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

    # No engine running: nothing to tell. The client retries an unreachable
    # server for as long as it is let, so the whole notice has a deadline.
    async def bounded() -> None:
        await asyncio.wait_for(publish(), timeout=NOTIFY_TIMEOUT_SECONDS)

    with contextlib.suppress(Exception):
        asyncio.run(bounded())


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


ServicesOpener = Callable[[], tuple[Any, Callable[[], None]]]


def open_engine_services() -> tuple[Any, Callable[[], None]]:
    """The engine's services (IAM and identity), and how to let go of them: the
    serving engine's over NATS when one runs, else this process's own."""
    from naas_abi_core.engine.Engine import Engine

    from naas_abi_cli.cli.engine_role import use_auto_engine_role

    use_auto_engine_role()
    engine = Engine()
    engine.load(module_names=[])
    return engine.services, engine.shutdown


@contextmanager
def _services(ctx: click.Context) -> Iterator[Any]:
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.iam.IAMPorts import IAMError
    from naas_abi_core.services.identity.IdentityPorts import IdentityError

    opener: ServicesOpener = (ctx.obj or {}).get(
        "services_opener", open_engine_services
    )
    services, close = opener()
    try:
        with as_service_account("engine"):
            yield services
    except NotImplementedError as exc:
        raise click.ClickException(str(exc)) from exc
    except (IAMError, IdentityError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        close()


def _scope(services: Any, org: str | None, workspace: str | None) -> str:
    """``abi:<org>:-`` for an org's own roles, ``abi:<org>:<workspace>`` for a
    workspace's: the org is named, or IAM knows the workspace's."""
    from naas_abi_core.services.iam.names import scope_name

    if workspace is None:
        if org is None:
            raise click.UsageError("Name --org, or --workspace")
        return scope_name(org, "-")
    org = org or services.iam.workspace_org(workspace)
    if org is None:
        raise click.UsageError(
            f"IAM does not know workspace {workspace!r}: name its organization with --org"
        )
    return scope_name(org, workspace)


def _provider(services: Any, named: str | None) -> str:
    if named:
        return named
    known = services.identity.list_providers()
    if services.identity.default_provider:
        return str(services.identity.default_provider)
    if len(known) == 1:
        return str(known[0].name)
    raise click.UsageError(
        "Name the identity provider with --provider ("
        + (", ".join(p.name for p in known) or "none is configured")
        + ")"
    )


ROLES = click.Choice(["owner", "admin", "member", "viewer"])


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


# -- invitations ----------------------------------------------------------------------------


@iam.command("invite")
@click.argument("email")
@click.option("--org", help="The organization id.")
@click.option("--org-role", type=ROLES, help="The role in the organization itself.")
@click.option("--workspace", help="The workspace id.")
@click.option("--role", type=ROLES, help="The role in the workspace.")
@click.option(
    "--provider", help="The identity provider; default: the engine's default."
)
@click.option("--name", help="Their display name, where the provider needs one.")
@click.option(
    "--no-provision",
    is_flag=True,
    help="Only keep the pending grants: do not create the person at the provider.",
)
@click.pass_context
def invite(
    ctx: click.Context,
    email: str,
    org: str | None,
    org_role: str | None,
    workspace: str | None,
    role: str | None,
    provider: str | None,
    name: str | None,
    no_provision: bool,
) -> None:
    """Invite EMAIL: roles that wait for them, and an account at their provider.

    The roles attach when they first sign in through the provider with this
    address verified. Where the provider's people are managed in the provider
    (provisioning: none) only the pending grants are kept.
    """
    if not org_role and not role:
        raise click.UsageError(
            "Name a role: --org-role (with --org) or --role (with --workspace)"
        )
    if org_role and not org:
        raise click.UsageError("--org-role needs --org")
    if role and not workspace:
        raise click.UsageError("--role needs --workspace")
    with _services(ctx) as services:
        chosen = _provider(services, provider)
        scopes: list[tuple[str, str]] = []
        if org_role:
            scopes.append((org_role, _scope(services, org, None)))
        if role:
            scopes.append((role, _scope(services, org, workspace)))
        made: list[Any] = []
        created: list[Any] = []  # only these are this command's to take back
        try:
            for policy, scope in scopes:
                held = any(
                    g.scope == scope
                    for g in services.iam.list_pending_grants(
                        provider=chosen, email=email, policy_id=f"builtin.{policy}"
                    )
                )
                grant = services.iam.create_pending_grant(
                    chosen, email, f"builtin.{policy}", scope
                )
                made.append(grant)
                if not held:
                    created.append(grant)
        except Exception:
            for grant in created:
                services.iam.revoke_pending_grant(grant.id)
            raise
        for grant in made:
            click.echo(f"{grant.id}\t{grant.policy_id}\t{grant.scope}\t{grant.email}")
        if no_provision:
            click.echo("not provisioned: --no-provision", err=True)
            return
        try:
            user = services.identity.provision_user(chosen, email, name=name)
        except NotImplementedError:
            click.echo(
                f"Users of {chosen} are managed in the identity provider: they sign in "
                "with this address once their account exists there.",
                err=True,
            )
            return
        except Exception:
            for grant in created:
                services.iam.revoke_pending_grant(grant.id)
            raise
        state = "created" if user.created else "already existed"
        click.echo(
            f"{chosen}: {user.email} {state} ({user.subject or 'no id'})", err=True
        )
        if getattr(user, "warning", None):
            click.echo(f"warning: {user.warning}", err=True)


@iam.group("invitation")
def invitation() -> None:
    """The roles that wait for people who have not signed in yet."""


@invitation.command("list")
@click.option("--email")
@click.option("--provider")
@click.pass_context
def invitation_list(
    ctx: click.Context, email: str | None, provider: str | None
) -> None:
    """List pending grants: id, role, scope, provider, email."""
    with _services(ctx) as services:
        for grant in services.iam.list_pending_grants(provider=provider, email=email):
            click.echo(
                f"{grant.id}\t{grant.policy_id}\t{grant.scope}\t{grant.provider}\t{grant.email}"
            )


@invitation.command("revoke")
@click.argument("grant_id")
@click.pass_context
def invitation_revoke(ctx: click.Context, grant_id: str) -> None:
    """Withdraw a pending grant."""
    with _services(ctx) as services:
        if not services.iam.revoke_pending_grant(grant_id):
            raise click.ClickException(f"No pending grant {grant_id}")
        click.echo(f"revoked {grant_id}")


# -- IdP groups ---------------------------------------------------------------------------------


@iam.group("group")
def group() -> None:
    """Bind an identity provider's groups to roles."""


def _binding_options(command: Callable[..., Any]) -> Callable[..., Any]:
    for option in reversed(
        (
            click.argument("provider"),
            click.argument("claim_value", metavar="GROUP"),
            click.option("--org", help="The organization id."),
            click.option(
                "--workspace", help="The workspace id (with --org unless IAM knows it)."
            ),
            click.option("--role", type=ROLES, required=True),
        )
    ):
        command = option(command)
    return command


@group.command("bind")
@_binding_options
@click.pass_context
def group_bind(
    ctx: click.Context,
    provider: str,
    claim_value: str,
    org: str | None,
    workspace: str | None,
    role: str,
) -> None:
    """Give the members of PROVIDER's group GROUP a role in an org or a workspace.

    Without --workspace the role is the organization's own (--org).
    """
    with _services(ctx) as services:
        binding = services.iam.bind_idp_group(
            provider, claim_value, f"builtin.{role}", _scope(services, org, workspace)
        )
        click.echo(
            f"{binding.provider}\t{binding.claim_value}\t{binding.policy_id}\t{binding.scope}"
        )


@group.command("unbind")
@_binding_options
@click.pass_context
def group_unbind(
    ctx: click.Context,
    provider: str,
    claim_value: str,
    org: str | None,
    workspace: str | None,
    role: str,
) -> None:
    """Take that role from the members of GROUP."""
    with _services(ctx) as services:
        removed = services.iam.unbind_idp_group(
            provider, claim_value, f"builtin.{role}", _scope(services, org, workspace)
        )
        if not removed:
            raise click.ClickException("No such binding")
        click.echo("unbound")


@group.command("list")
@click.option("--provider")
@click.pass_context
def group_list(ctx: click.Context, provider: str | None) -> None:
    """List bindings: provider, group, role, scope."""
    with _services(ctx) as services:
        for binding in services.iam.list_idp_bindings(provider=provider):
            click.echo(
                f"{binding.provider}\t{binding.claim_value}\t{binding.policy_id}\t{binding.scope}"
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
