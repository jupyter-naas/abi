"""Nexus workspace admin commands."""

from __future__ import annotations

import urllib.parse
from typing import Any

import click

from .nexus_client import (
    NexusApiError,
    build_client,
    common_api_options,
    print_json,
    print_table,
)
from .nexus_postgres import create_workspace_sql, run_postgres_sql


@click.group("workspace")
def workspace() -> None:
    """Manage Nexus workspaces via the authenticated API."""


@workspace.command("create")
@click.option("--name", required=True, help="Workspace display name.")
@click.option("--slug", required=True, help="URL-safe slug (lowercase, digits, hyphens).")
@click.option(
    "--org",
    "organization_id",
    required=True,
    help="Organization id (e.g. org-960fbfdd82bc).",
)
@click.option(
    "--owner-id",
    default=None,
    help="Owner user id (required for --via postgres; API path always uses the caller).",
)
@click.option(
    "--via",
    type=click.Choice(["api", "postgres"], case_sensitive=False),
    default="api",
    show_default=True,
    help="api: POST /api/workspaces. postgres: break-glass SQL (ops VM only).",
)
@common_api_options
def workspace_create(
    name: str,
    slug: str,
    organization_id: str,
    owner_id: str | None,
    via: str,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Create a workspace under an organization (API caller becomes owner)."""
    if via.lower() == "postgres":
        if not owner_id:
            raise click.ClickException("--owner-id is required with --via postgres.")
        sql, ws_id = create_workspace_sql(
            name=name,
            slug=slug,
            owner_id=owner_id,
            organization_id=organization_id,
        )
        if dry_run:
            print(sql)
            return
        out = run_postgres_sql(sql)
        print_json({"via": "postgres", "id": ws_id, "slug": slug, "postgres_output": out})
        return

    body = {"name": name, "slug": slug, "organization_id": organization_id}
    if dry_run:
        print_json({"method": "POST", "path": "/api/workspaces", "body": body})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        result = client.post("/api/workspaces", body)
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc
    print_json(result)


@workspace.command("list")
@click.option(
    "--org",
    "organization_id",
    default=None,
    help="If set, list workspaces for this organization instead of the caller's memberships.",
)
@common_api_options
def workspace_list(
    organization_id: str | None,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """List workspaces visible to the authenticated user (or under --org)."""
    path = (
        f"/api/organizations/{organization_id}/workspaces"
        if organization_id
        else "/api/workspaces"
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
        ["id", "name", "slug", "organization_id", "owner_id"],
        title="Workspaces",
    )


@workspace.command("get")
@click.option("--id", "workspace_id", default=None, help="Workspace id (ws-...).")
@click.option("--slug", default=None, help="Workspace slug.")
@common_api_options
def workspace_get(
    workspace_id: str | None,
    slug: str | None,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Fetch a workspace by id or slug."""
    if bool(workspace_id) == bool(slug):
        raise click.ClickException("Provide exactly one of --id or --slug.")
    path = f"/api/workspaces/{workspace_id}" if workspace_id else f"/api/workspaces/slug/{slug}"
    if dry_run:
        print_json({"method": "GET", "path": path})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        print_json(client.get(path))
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc


@workspace.command("delete")
@click.option("--id", "workspace_id", required=True, help="Workspace id (ws-...).")
@click.option("--yes", is_flag=True, default=False, help="Skip confirmation.")
@common_api_options
def workspace_delete(
    workspace_id: str,
    yes: bool,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Delete a workspace (owner only)."""
    path = f"/api/workspaces/{workspace_id}"
    if dry_run:
        print_json({"method": "DELETE", "path": path})
        return
    if not yes and not click.confirm(f"Delete workspace {workspace_id}?"):
        raise click.Abort()
    client = build_client(api_url=api_url, token=token)
    try:
        print_json(client.delete(path))
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc


@workspace.group("members")
def workspace_members() -> None:
    """Workspace membership operations."""


@workspace_members.command("list")
@click.option("--workspace", "workspace_id", required=True, help="Workspace id (ws-...).")
@common_api_options
def workspace_members_list(
    workspace_id: str,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """List members of a workspace."""
    path = f"/api/workspaces/{workspace_id}/members"
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
        ["user_id", "email", "name", "role", "source", "status"],
        title=f"Members of {workspace_id}",
    )


@workspace_members.command("search")
@click.option("--workspace", "workspace_id", required=True, help="Workspace id (ws-...).")
@click.option("--q", "query", required=True, help="Name or email (at least 2 characters).")
@click.option("--limit", default=10, show_default=True, type=click.IntRange(1, 20))
@common_api_options
def workspace_members_search(
    workspace_id: str,
    query: str,
    limit: int,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Find people of the workspace's organization to add (not already in it)."""
    path = (
        f"/api/workspaces/{workspace_id}/members/candidates?"
        f"{urllib.parse.urlencode({'q': query, 'limit': limit})}"
    )
    if dry_run:
        print_json({"method": "GET", "path": path})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        found = client.get(path)
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc
    rows = found.get("items") if isinstance(found, dict) else None
    if not isinstance(rows, list):
        print_json(found)
        return
    print_table(
        rows,
        ["user_id", "email", "name", "org_role", "status"],
        title=f"People to add to {workspace_id}",
    )


@workspace_members.command("add")
@click.option("--workspace", "workspace_id", required=True, help="Workspace id (ws-...).")
@click.option(
    "--user-id",
    "member_user_id",
    default=None,
    help="Someone of the organization (see `members search`): added now and notified.",
)
@click.option(
    "--email",
    "member_email",
    default=None,
    help="Anyone else: their account is created, or the one of this email linked.",
)
@click.option("--name", "member_name", default=None, help="Display name when creating the user.")
@click.option(
    "--role",
    default="member",
    show_default=True,
    type=click.Choice(["admin", "member", "viewer"], case_sensitive=False),
)
@common_api_options
def workspace_members_add(
    workspace_id: str,
    member_user_id: str | None,
    member_email: str | None,
    member_name: str | None,
    role: str,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Add a user to a workspace, with the workspace role only (no org role)."""
    if bool(member_user_id) == bool(member_email):
        raise click.ClickException("Provide exactly one of --user-id or --email.")
    body: dict[str, Any] = {"role": role.lower()}
    if member_user_id:
        path = f"/api/workspaces/{workspace_id}/members"
        body["user_id"] = member_user_id
    else:
        path = f"/api/workspaces/{workspace_id}/members/invite"
        body["email"] = member_email
        if member_name:
            body["name"] = member_name
    if dry_run:
        print_json({"method": "POST", "path": path, "body": body})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        print_json(client.post(path, body))
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc


@workspace_members.command("resend")
@click.option("--workspace", "workspace_id", required=True, help="Workspace id (ws-...).")
@click.option("--user-id", required=True, help="An invited member's user id.")
@common_api_options
def workspace_members_resend(
    workspace_id: str,
    user_id: str,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Send an invited member their sign-in mail again."""
    path = f"/api/workspaces/{workspace_id}/members/{user_id}/resend"
    if dry_run:
        print_json({"method": "POST", "path": path})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        print_json(client.post(path))
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc


@workspace_members.command("remove")
@click.option("--workspace", "workspace_id", required=True, help="Workspace id (ws-...).")
@click.option("--user-id", required=True, help="User id to remove.")
@click.option("--yes", is_flag=True, default=False, help="Skip confirmation.")
@common_api_options
def workspace_members_remove(
    workspace_id: str,
    user_id: str,
    yes: bool,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Remove a member from a workspace."""
    path = f"/api/workspaces/{workspace_id}/members/{user_id}"
    if dry_run:
        print_json({"method": "DELETE", "path": path})
        return
    if not yes and not click.confirm(f"Remove {user_id} from {workspace_id}?"):
        raise click.Abort()
    client = build_client(api_url=api_url, token=token)
    try:
        print_json(client.delete(path))
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc
