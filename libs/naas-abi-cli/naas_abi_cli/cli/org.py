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


def legacy_access(
    level: str | None,
    org_admin: bool,
    workspace_admin: bool,
    *,
    role: str | None,
    workspace_role: str | None,
) -> tuple[str | None, bool, bool]:
    """The level, org admin and workspace admin the options of before ask for:
    ``--role admin`` is ``--org-admin``, ``--workspace-role admin`` is ``--admin``
    and ``viewer`` or ``member`` the level. Owner is no longer given."""
    if "owner" in ((role or "").lower(), (workspace_role or "").lower()):
        raise click.ClickException(
            "Owner is no longer given: use --org-admin or --admin."
        )
    org_admin = org_admin or (role or "").lower() == "admin"
    ws_role = (workspace_role or "").lower()
    workspace_admin = workspace_admin or ws_role == "admin"
    if level is None and ws_role in ("viewer", "member"):
        level = ws_role
    return (level.lower() if level else None), org_admin, workspace_admin


def invite_body(
    email: str,
    name: str | None,
    *,
    level: str | None,
    org_admin: bool,
    workspace_id: str | None,
    workspace_admin: bool,
    capabilities: tuple[str, ...] = (),
) -> dict[str, Any]:
    """The organization invite's body (#1589): the level (absent: theirs, Member
    for someone new), org admin, the workspace with whether they administer it,
    and capability groups."""
    if workspace_admin and not workspace_id:
        raise click.ClickException("--admin needs --workspace.")
    body: dict[str, Any] = {"email": email}
    if name:
        body["name"] = name
    if level:
        body["level"] = level
    if org_admin:
        body["org_admin"] = True
    if workspace_id:
        body["workspaces"] = [{"id": workspace_id, "admin": workspace_admin}]
    if capabilities:
        body["capabilities"] = list(capabilities)
    return body


def workspace_access_body(
    level: str | None, admin: bool, capabilities: tuple[str, ...] = ()
) -> dict[str, Any]:
    """What a workspace add or invite gives (#1589): the level (absent: theirs,
    Member for someone new), whether they administer it, capability groups."""
    body: dict[str, Any] = {"admin": admin}
    if level:
        body["level"] = level
    if capabilities:
        body["capabilities"] = list(capabilities)
    return body


def access_options(command: Any) -> Any:
    """The options of an invite (#1589), and the ones of before, still read."""
    for option in reversed(
        (
            click.option(
                "--level",
                default=None,
                type=click.Choice(["viewer", "member"], case_sensitive=False),
                help="Their level, in all their workspaces (default: theirs; Member if new).",
            ),
            click.option("--org-admin", is_flag=True, default=False, help="Org admin."),
            click.option(
                "--admin",
                "workspace_admin",
                is_flag=True,
                default=False,
                help="They administer the workspace (--workspace).",
            ),
            click.option(
                "--capability",
                "capabilities",
                multiple=True,
                help="A capability group id (repeat for several).",
            ),
            click.option(
                "--role",
                default=None,
                type=click.Choice(
                    ["owner", "admin", "member", "viewer"], case_sensitive=False
                ),
                help="Deprecated: admin is --org-admin.",
            ),
            click.option(
                "--workspace-role",
                default=None,
                type=click.Choice(["admin", "member", "viewer"], case_sensitive=False),
                help="Deprecated: admin is --admin, viewer or member the --level.",
            ),
            click.option("--no-org-role", is_flag=True, default=False, hidden=True),
        )
    ):
        command = option(command)
    return command


@org_members.command("invite")
@click.option("--org", "org_id", required=True, help="Organization id (org-...).")
@click.option(
    "--email", "member_email", required=True, help="Invitee email (created if missing)."
)
@click.option(
    "--name", "member_name", default=None, help="Display name when creating the user."
)
@click.option(
    "--workspace",
    "workspace_id",
    default=None,
    help="Optional workspace to add as well.",
)
@access_options
@common_api_options
def org_members_invite(
    org_id: str,
    member_email: str,
    member_name: str | None,
    workspace_id: str | None,
    level: str | None,
    org_admin: bool,
    workspace_admin: bool,
    capabilities: tuple[str, ...],
    role: str | None,
    workspace_role: str | None,
    no_org_role: bool,
    api_url: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Add a user to an organization: their account is created, or the one of
    this email linked, and they are mailed. With no workspace and not an org admin,
    they join the organization's people."""
    path = f"/api/organizations/{org_id}/members/invite"
    level, org_admin, workspace_admin = legacy_access(
        level, org_admin, workspace_admin, role=role, workspace_role=workspace_role
    )
    body = invite_body(
        member_email,
        member_name,
        level=level,
        org_admin=org_admin,
        workspace_id=workspace_id,
        workspace_admin=workspace_admin,
        capabilities=capabilities,
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
