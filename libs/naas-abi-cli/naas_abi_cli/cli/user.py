"""Nexus user admin commands."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

import click

from .nexus_client import (
    NexusApiError,
    build_client,
    common_api_options,
    print_json,
    print_table,
)
from .nexus_postgres import create_user_sql, run_postgres_sql


def _register_user(*, api_url: str, body: dict[str, Any]) -> Any:
    """Public register endpoint (no bearer token)."""
    import json
    import urllib.error
    import urllib.request

    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/auth/register",
        data=raw,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        # http(s) Nexus register endpoint only.
        with urllib.request.urlopen(req, timeout=30.0) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        from .nexus_client import _read_error_detail

        raise NexusApiError(exc.code, _read_error_detail(exc), "/api/auth/register") from exc


@click.group("user")
def user() -> None:
    """Manage Nexus users via the authenticated API (or break-glass Postgres)."""


@user.command("create")
@click.option("--email", "user_email", required=True, help="User email.")
@click.option("--name", "user_name", required=True, help="Display name.")
@click.option(
    "--password",
    "user_password",
    default=None,
    help="Initial password (generated if omitted). Never printed unless --show-password.",
)
@click.option(
    "--workspace",
    "workspace_id",
    default=None,
    help="Optional workspace id to invite the user into after create.",
)
@click.option(
    "--role",
    default="member",
    show_default=True,
    type=click.Choice(["admin", "member", "viewer"], case_sensitive=False),
    help="Workspace role when --workspace is set.",
)
@click.option(
    "--org",
    "organization_id",
    default=None,
    help="Optional organization id to invite the user into after create.",
)
@click.option(
    "--org-role",
    default="member",
    show_default=True,
    type=click.Choice(["owner", "admin", "member"], case_sensitive=False),
)
@click.option(
    "--secret-file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write credentials here (mode 600). Default: secrets/NEXUS_USER_<EMAIL>.env",
)
@click.option(
    "--show-password",
    is_flag=True,
    default=False,
    help="Echo the password to stdout (off by default).",
)
@click.option(
    "--via",
    "via",
    type=click.Choice(["api", "postgres"], case_sensitive=False),
    default="api",
    show_default=True,
    help="api: POST /api/auth/register. postgres: break-glass SQL (ops VM only).",
)
@common_api_options
def user_create(
    user_email: str,
    user_name: str,
    user_password: str | None,
    workspace_id: str | None,
    role: str,
    organization_id: str | None,
    org_role: str,
    secret_file: Path | None,
    show_password: bool,
    via: str,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Create a user.

    API path uses `/api/auth/register` (requires password auth enabled on the
    Nexus instance). On production deployments where password auth is disabled, use
    magic-link signup or `--via postgres` on the VM (documented break-glass).
    """
    password_value = user_password or secrets.token_urlsafe(18)
    if via.lower() == "postgres":
        _create_via_postgres(
            user_email=user_email,
            user_name=user_name,
            password_value=password_value,
            organization_id=organization_id,
            workspace_id=workspace_id,
            workspace_role=role.lower(),
            org_role=org_role.lower(),
            secret_file=secret_file,
            show_password=show_password,
            dry_run=dry_run,
        )
        return

    body = {"email": user_email, "name": user_name, "password": password_value}
    if dry_run:
        redacted = {**body, "password": "***"}
        print_json({"method": "POST", "path": "/api/auth/register", "body": redacted})
        return

    try:
        result = _register_user(api_url=api_url, body=body)
    except NexusApiError as exc:
        if exc.status == 410:
            raise click.ClickException(
                "Password registration is disabled on this Nexus instance. "
                "Use magic-link signup, config seed (settings.users), or "
                "`abi user create --via postgres` on the VM (break-glass)."
            ) from exc
        raise click.ClickException(str(exc)) from exc

    user_payload = result.get("user") if isinstance(result, dict) else None
    user_id = (user_payload or {}).get("id")

    invite_results: list[dict[str, Any]] = []
    if workspace_id or organization_id:
        client = build_client(
            api_url=api_url, token=token, email=email, password=password
        )
        if workspace_id:
            try:
                invite_results.append(
                    client.post(
                        f"/api/workspaces/{workspace_id}/members/invite",
                        {"email": user_email, "role": role.lower()},
                    )
                )
            except NexusApiError as exc:
                raise click.ClickException(
                    f"User created ({user_id}) but workspace invite failed: {exc}"
                ) from exc
        if organization_id:
            try:
                invite_results.append(
                    client.post(
                        f"/api/organizations/{organization_id}/members/invite",
                        {"email": user_email, "role": org_role.lower()},
                    )
                )
            except NexusApiError as exc:
                raise click.ClickException(
                    f"User created ({user_id}) but org invite failed: {exc}"
                ) from exc

    secret_path = _write_secret_file(
        secret_file=secret_file,
        user_email=user_email,
        user_id=str(user_id or ""),
        password_value=password_value,
        workspace_id=workspace_id,
    )

    out: dict[str, Any] = {
        "user": user_payload,
        "secret_file": str(secret_path) if secret_path else None,
        "invites": invite_results,
    }
    if show_password:
        out["password"] = password_value
    print_json(out)


@user.command("invite")
@click.option("--email", "member_email", required=True, help="Invitee email (created if missing).")
@click.option("--name", "member_name", default=None, help="Display name when creating the user.")
@click.option("--workspace", "workspace_id", default=None, help="Workspace id (ws-...).")
@click.option("--org", "organization_id", default=None, help="Organization id (org-...).")
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
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Invite a user (create-on-invite) to an org and/or workspace.

    Creates the Nexus account when missing and emails OTP / magic-link sign-in.
    Prefer --org (optionally with --workspace). Workspace-only invite remains supported.
    """
    if not organization_id and not workspace_id:
        raise click.ClickException("Provide --org and/or --workspace.")

    results: list[dict[str, Any]] = []

    if organization_id:
        path = f"/api/organizations/{organization_id}/members/invite"
        org_role = role.lower()
        if org_role not in {"owner", "admin", "member"}:
            raise click.ClickException("--role for --org must be owner, admin, or member.")
        body: dict[str, Any] = {"email": member_email, "role": org_role}
        if member_name:
            body["name"] = member_name
        if workspace_id:
            body["workspace_id"] = workspace_id
            body["workspace_role"] = workspace_role.lower()
        if dry_run:
            results.append({"method": "POST", "path": path, "body": body})
        else:
            client = build_client(
                api_url=api_url, token=token, email=email, password=password
            )
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
            client = build_client(
                api_url=api_url, token=token, email=email, password=password
            )
            try:
                results.append(client.post(path, body))
            except NexusApiError as exc:
                raise click.ClickException(str(exc)) from exc

    print_json(results[0] if len(results) == 1 else {"invites": results})


@user.command("list")
@click.option("--org", "organization_id", default=None, help="List organization members.")
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
    email: str | None,
    password: str | None,
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
    client = build_client(api_url=api_url, token=token, email=email, password=password)
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


@user.command("me")
@common_api_options
def user_me(
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Show the authenticated Nexus user (`GET /api/auth/me`)."""
    if dry_run:
        print_json({"method": "GET", "path": "/api/auth/me"})
        return
    client = build_client(api_url=api_url, token=token, email=email, password=password)
    try:
        print_json(client.get("/api/auth/me"))
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc


def _write_secret_file(
    *,
    secret_file: Path | None,
    user_email: str,
    user_id: str,
    password_value: str,
    workspace_id: str | None,
) -> Path | None:
    if secret_file is None:
        safe = user_email.upper().replace("@", "_").replace(".", "_").replace("-", "_")
        secret_file = Path("secrets") / f"NEXUS_USER_{safe}.env"
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"email={user_email}",
        f"user_id={user_id}",
        f"password={password_value}",
    ]
    if workspace_id:
        lines.append(f"workspace_id={workspace_id}")
    secret_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(secret_file, 0o600)
    return secret_file


def _create_via_postgres(
    *,
    user_email: str,
    user_name: str,
    password_value: str,
    organization_id: str | None,
    workspace_id: str | None,
    workspace_role: str,
    org_role: str,
    secret_file: Path | None,
    show_password: bool,
    dry_run: bool,
) -> None:
    sql, user_id = create_user_sql(
        email=user_email,
        name=user_name,
        password=password_value,
        organization_id=organization_id,
        org_role=org_role,
        workspace_id=workspace_id,
        workspace_role=workspace_role,
    )
    if dry_run:
        print(sql)
        return
    run_postgres_sql(sql)
    secret_path = _write_secret_file(
        secret_file=secret_file,
        user_email=user_email,
        user_id=user_id,
        password_value=password_value,
        workspace_id=workspace_id,
    )
    out: dict[str, Any] = {
        "via": "postgres",
        "user_id": user_id,
        "email": user_email,
        "name": user_name,
        "secret_file": str(secret_path) if secret_path else None,
    }
    if show_password:
        out["password"] = password_value
    print_json(out)
