"""Nexus organization admin commands."""

from __future__ import annotations

from typing import Any

import click

from .nexus_client import (
    NexusApiError,
    build_client,
    common_api_options,
    print_json,
    print_table,
)


@click.group("org")
def org() -> None:
    """Manage Nexus organizations via the authenticated API."""


@org.command("list")
@common_api_options
def org_list(
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """List organizations for the authenticated user."""
    if dry_run:
        print_json({"method": "GET", "path": "/api/organizations"})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        rows = client.get("/api/organizations")
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc
    if not isinstance(rows, list):
        print_json(rows)
        return
    print_table(rows, ["id", "name", "slug"], title="Organizations")


@org.command("create")
@click.option("--name", required=True, help="Organization display name.")
@click.option("--slug", required=True, help="URL-safe slug.")
@common_api_options
def org_create(
    name: str,
    slug: str,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Create an organization (caller becomes owner)."""
    body = {"name": name, "slug": slug}
    if dry_run:
        print_json({"method": "POST", "path": "/api/organizations", "body": body})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        print_json(client.post("/api/organizations", body))
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc


@org.command("get")
@click.option("--id", "org_id", required=True, help="Organization id (org-...).")
@common_api_options
def org_get(
    org_id: str,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Fetch an organization by id."""
    path = f"/api/organizations/{org_id}"
    if dry_run:
        print_json({"method": "GET", "path": path})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        print_json(client.get(path))
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc


@org.group("members")
def org_members() -> None:
    """Organization membership operations."""


@org_members.command("list")
@click.option("--org", "org_id", required=True, help="Organization id (org-...).")
@common_api_options
def org_members_list(
    org_id: str,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """List organization members."""
    path = f"/api/organizations/{org_id}/members"
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
    # The directory: org members, and people of its workspaces only (role empty).
    print_table(
        rows,
        ["user_id", "email", "name", "role", "source", "status"],
        title=f"Members of {org_id}",
    )


@org_members.command("invite")
@click.option("--org", "org_id", required=True, help="Organization id (org-...).")
@click.option("--email", "member_email", required=True, help="Invitee email (created if missing).")
@click.option("--name", "member_name", default=None, help="Display name when creating the user.")
@click.option("--workspace", "workspace_id", default=None, help="Optional workspace to add as well.")
@click.option(
    "--workspace-role",
    default="member",
    show_default=True,
    type=click.Choice(["admin", "member", "viewer"], case_sensitive=False),
)
@click.option(
    "--role",
    default="member",
    show_default=True,
    type=click.Choice(["owner", "admin", "member"], case_sensitive=False),
)
@click.option(
    "--no-org-role",
    is_flag=True,
    default=False,
    help="Workspace access only (needs --workspace): no role in the organization.",
)
@common_api_options
def org_members_invite(
    org_id: str,
    member_email: str,
    member_name: str | None,
    workspace_id: str | None,
    workspace_role: str,
    role: str,
    no_org_role: bool,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Add a user to an organization: their account is created, or the one of
    this email linked, and they are mailed."""
    path = f"/api/organizations/{org_id}/members/invite"
    body = invite_body(
        member_email,
        member_name,
        role=None if no_org_role else role,
        workspace_id=workspace_id,
        workspace_role=workspace_role,
    )
    if dry_run:
        print_json({"method": "POST", "path": path, "body": body})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        print_json(client.post(path, body))
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc


@org_members.command("resend")
@click.option("--org", "org_id", required=True, help="Organization id (org-...).")
@click.option("--user-id", required=True, help="An invited member's user id.")
@common_api_options
def org_members_resend(
    org_id: str,
    user_id: str,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Send an invited member their sign-in mail again."""
    path = f"/api/organizations/{org_id}/members/{user_id}/resend"
    if dry_run:
        print_json({"method": "POST", "path": path})
        return
    client = build_client(api_url=api_url, token=token)
    try:
        print_json(client.post(path))
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc


def invite_body(
    email: str,
    name: str | None,
    *,
    role: str | None,
    workspace_id: str | None,
    workspace_role: str,
) -> dict[str, Any]:
    """The organization invite's body: ``role`` None is workspace access only."""
    if role is None and not workspace_id:
        raise click.ClickException("--no-org-role needs --workspace.")
    body: dict[str, Any] = {"email": email, "role": role.lower() if role else None}
    if name:
        body["name"] = name
    if workspace_id:
        body["workspaces"] = [{"id": workspace_id, "role": workspace_role.lower()}]
    return body


@org.command("workspaces")
@click.option("--org", "org_id", required=True, help="Organization id (org-...).")
@common_api_options
def org_workspaces(
    org_id: str,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """List workspaces under an organization."""
    path = f"/api/organizations/{org_id}/workspaces"
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
        ["id", "name", "slug", "owner_id"],
        title=f"Workspaces in {org_id}",
    )
