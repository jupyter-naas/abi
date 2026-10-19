"""Nexus user admin commands."""

from __future__ import annotations

import asyncio
import importlib
from typing import Any

import click

from .nexus_client import (
    NexusApiError,
    build_client,
    common_api_options,
    print_json,
    print_table,
)

_NEXUS_OIDC = "naas_abi.apps.nexus.apps.api.app.services.oidc"


@click.group("user")
def user() -> None:
    """Manage Nexus users: invite them, list them, move the old logins to the identity provider."""


@user.command("invite")
@click.option(
    "--email", "member_email", required=True, help="Invitee email (created if missing)."
)
@click.option(
    "--name", "member_name", default=None, help="Display name when creating the user."
)
@click.option(
    "--workspace", "workspace_id", default=None, help="Workspace id (ws-...)."
)
@click.option(
    "--org", "organization_id", default=None, help="Organization id (org-...)."
)
@click.option(
    "--role",
    default="member",
    show_default=True,
    type=click.Choice(["owner", "admin", "member", "viewer"], case_sensitive=False),
    help="Org role when --org is set; workspace role when only --workspace is set.",
)
@click.option(
    "--workspace-role",
    default="member",
    show_default=True,
    type=click.Choice(["admin", "member", "viewer"], case_sensitive=False),
    help="Workspace role when inviting via --org --workspace together.",
)
@common_api_options
def user_invite(
    member_email: str,
    member_name: str | None,
    workspace_id: str | None,
    organization_id: str | None,
    role: str,
    workspace_role: str,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Invite a user to an org and/or workspace.

    The identity provider makes the person exist and Nexus emails them a link to
    sign in (the provider mails the code). Prefer --org (optionally with
    --workspace). Workspace-only invite remains supported.
    """
    if not organization_id and not workspace_id:
        raise click.ClickException("Provide --org and/or --workspace.")

    results: list[dict[str, Any]] = []

    if organization_id:
        path = f"/api/organizations/{organization_id}/members/invite"
        org_role = role.lower()
        if org_role not in {"owner", "admin", "member"}:
            raise click.ClickException(
                "--role for --org must be owner, admin, or member."
            )
        body: dict[str, Any] = {"email": member_email, "role": org_role}
        if member_name:
            body["name"] = member_name
        if workspace_id:
            body["workspace_id"] = workspace_id
            body["workspace_role"] = workspace_role.lower()
        if dry_run:
            results.append({"method": "POST", "path": path, "body": body})
        else:
            client = build_client(api_url=api_url, token=token)
            try:
                results.append(client.post(path, body))
            except NexusApiError as exc:
                raise click.ClickException(str(exc)) from exc
    elif workspace_id:
        path = f"/api/workspaces/{workspace_id}/members/invite"
        ws_role = role.lower()
        if ws_role not in {"admin", "member", "viewer"}:
            raise click.ClickException(
                "--role for workspace-only invite must be admin, member, or viewer."
            )
        body = {"email": member_email, "role": ws_role}
        if member_name:
            body["name"] = member_name
        if dry_run:
            results.append({"method": "POST", "path": path, "body": body})
        else:
            client = build_client(api_url=api_url, token=token)
            try:
                results.append(client.post(path, body))
            except NexusApiError as exc:
                raise click.ClickException(str(exc)) from exc

    print_json(results[0] if len(results) == 1 else {"invites": results})


@user.command("list")
@click.option(
    "--org", "organization_id", default=None, help="List organization members."
)
@click.option(
    "--workspace",
    "workspace_id",
    default=None,
    help="List workspace members.",
)
@common_api_options
def user_list(
    organization_id: str | None,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """List users in an org or workspace (no global admin user index API today)."""
    if bool(organization_id) == bool(workspace_id):
        raise click.ClickException("Provide exactly one of --org or --workspace.")
    path = (
        f"/api/organizations/{organization_id}/members"
        if organization_id
        else f"/api/workspaces/{workspace_id}/members"
    )
    if dry_run:
        print_json({"method": "GET", "path": path})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        rows = client.get(path)
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc
    if not isinstance(rows, list):
        print_json(rows)
        return
    print_table(
        rows,
        ["user_id", "email", "name", "role"],
        title="Users",
    )


@user.command("migrate")
@click.option(
    "--provider",
    default=None,
    help="The built-in identity provider to move the users to (default: the engine's default).",
)
@click.option(
    "--database-url",
    envvar="DATABASE_URL",
    default=None,
    help="Nexus's database (default: nexus_config.database_url of the project's configuration).",
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Make the people exist at the provider. Without it: a dry run, nothing changes.",
)
@click.pass_context
def user_migrate(
    ctx: click.Context, provider: str | None, database_url: str | None, apply: bool
) -> None:
    """Move the users of Nexus's old login to the built-in identity provider.

    Makes every account that no provider signs in yet exist at the provider,
    with the same email. Each person then signs in with the code the provider
    mails to that address, and that first sign-in links the account: it keeps
    its roles, groups and data. Passwords do not move. Run it without --apply
    first, and again whenever accounts were added; it creates nobody twice.
    """
    from .iam import _provider, _services

    # Nexus ships in naas-abi, which the CLI reaches by name only (it is not a
    # dependency of the CLI's own type check).
    migrate_users = importlib.import_module(f"{_NEXUS_OIDC}.migration").migrate_users

    url = database_url or _configured_database_url()
    users = asyncio.run(_legacy_users(url))
    with _services(ctx) as services:
        chosen = _provider(services, provider)
        info = next(
            (p for p in services.identity.list_providers() if p.name == chosen), None
        )
        if info is None or getattr(info, "provisioning", None) != "builtin":
            raise click.ClickException(
                f"{chosen!r} is not the built-in identity provider (provisioning: builtin): "
                "only it proves an address by mailing a code, so only it takes over an "
                "existing account. Other providers' people are managed in the provider."
            )
        rows = migrate_users(
            users,
            provision=lambda email, name: services.identity.provision_user(
                chosen, email, name=name
            ),
            find=lambda email: services.identity.find_provisioned_user(chosen, email),
            apply=apply,
        )
    print_table(
        [
            {
                "user": r.user_id,
                "email": r.email,
                "result": r.outcome,
                "detail": r.detail,
            }
            for r in rows
        ],
        ["user", "email", "result", "detail"],
        title=f"Users to {chosen}" + ("" if apply else " (dry run)"),
    )
    failed = [r for r in rows if r.outcome == "failed"]
    if not apply:
        click.echo("Dry run: nothing changed. Run again with --apply.", err=True)
    if failed:
        raise click.ClickException(
            f"{len(failed)} user(s) could not be moved: see above"
        )


def _configured_database_url() -> str:
    """``nexus_config.database_url`` of the project's configuration."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )

    try:
        configuration = EngineConfiguration.load_configuration()
    except Exception as exc:
        raise click.ClickException(
            f"Could not read the project's configuration ({exc}): pass --database-url"
        ) from exc
    for module in configuration.modules:
        if module.module == "naas_abi" or (module.path or "").endswith("naas_abi"):
            found = (module.config.get("nexus_config") or {}).get("database_url")
            if found:
                return str(found)
    return str(importlib.import_module("naas_abi").NexusConfig().database_url)


async def _legacy_users(database_url: str) -> list[Any]:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    adapter = importlib.import_module(
        f"{_NEXUS_OIDC}.adapters.secondary.postgres"
    ).OidcSessionSecondaryAdapterPostgres

    engine = create_async_engine(database_url)
    try:
        async with AsyncSession(engine) as db:
            return await adapter(db).list_legacy_users()
    except Exception as exc:
        raise click.ClickException(f"Could not read Nexus's users: {exc}") from exc
    finally:
        await engine.dispose()
