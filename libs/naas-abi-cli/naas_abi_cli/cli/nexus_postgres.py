"""Break-glass Postgres helpers for Nexus user/workspace ops (ops VM SOP).

Preferred path is the authenticated Nexus HTTP API. Use this only when browser
auth / password registration is unavailable, typically on an ops host via:

  NEXUS_POSTGRES_COMPOSE_DIR=/opt/abi
  abi user create --via postgres --email ... --name ...

Requires `bcrypt` at runtime for password hashing.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import uuid
from pathlib import Path


def esc(value: str) -> str:
    return value.replace("'", "''")


def create_user_sql(
    *,
    email: str,
    name: str,
    password: str,
    organization_id: str | None = None,
    org_role: str = "member",
    workspace_id: str | None = None,
    workspace_role: str = "member",
) -> tuple[str, str]:
    try:
        import bcrypt
    except ImportError as exc:  # pragma: no cover - env dependent
        raise RuntimeError(
            "bcrypt is required for --via postgres. Install it in the runtime env."
        ) from exc

    user_id = f"user-{secrets.token_hex(6)}"
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    statements = [
        "BEGIN;",
        (
            "INSERT INTO users (id, email, name, hashed_password, is_superadmin, "
            "created_at, updated_at) VALUES ("
            f"'{esc(user_id)}', '{esc(email)}', '{esc(name)}', '{esc(hashed)}', "
            "false, NOW(), NOW());"
        ),
    ]
    if organization_id:
        statements.append(
            "INSERT INTO organization_members (id, organization_id, user_id, role, created_at) "
            f"VALUES ('{esc(str(uuid.uuid4()))}', '{esc(organization_id)}', "
            f"'{esc(user_id)}', '{esc(org_role)}', NOW());"
        )
    if workspace_id:
        statements.append(
            "INSERT INTO workspace_members (id, workspace_id, user_id, role, created_at) "
            f"VALUES ('{esc(str(uuid.uuid4()))}', '{esc(workspace_id)}', "
            f"'{esc(user_id)}', '{esc(workspace_role)}', NOW());"
        )
    statements.append("COMMIT;")
    statements.append(
        f"SELECT id, email, name FROM users WHERE id='{esc(user_id)}';"
    )
    return "\n".join(statements) + "\n", user_id


def create_workspace_sql(
    *,
    name: str,
    slug: str,
    owner_id: str,
    organization_id: str,
) -> tuple[str, str]:
    ws_id = f"ws-{secrets.token_hex(6)}"
    member_id = str(uuid.uuid4())
    sql = f"""
BEGIN;
INSERT INTO workspaces (id, name, slug, owner_id, organization_id, primary_color, created_at, updated_at)
VALUES ('{esc(ws_id)}', '{esc(name)}', '{esc(slug)}', '{esc(owner_id)}', '{esc(organization_id)}', '#22c55e', NOW(), NOW());
INSERT INTO workspace_members (id, workspace_id, user_id, role, created_at)
VALUES ('{esc(member_id)}', '{esc(ws_id)}', '{esc(owner_id)}', 'owner', NOW());
COMMIT;
SELECT id, name, slug, organization_id, owner_id FROM workspaces WHERE id='{esc(ws_id)}';
"""
    return sql, ws_id


def run_postgres_sql(sql: str) -> str:
    """Execute SQL against Nexus Postgres via docker compose on the ops VM."""
    compose_dir = os.getenv("NEXUS_POSTGRES_COMPOSE_DIR")
    if not compose_dir:
        raise RuntimeError(
            "Set NEXUS_POSTGRES_COMPOSE_DIR to the deployment compose directory "
            "(e.g. /opt/abi) before using --via postgres."
        )
    root = Path(compose_dir)
    gcp = root / "docker-compose.gcp.yml"
    cmd = [
        "sudo",
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
    ]
    if gcp.exists():
        cmd.extend(["-f", "docker-compose.gcp.yml"])
    cmd.extend(
        [
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            os.getenv("NEXUS_POSTGRES_USER", "abi"),
            "-d",
            os.getenv("NEXUS_POSTGRES_DB", "nexus"),
            "-v",
            "ON_ERROR_STOP=1",
        ]
    )
    proc = subprocess.run(
        cmd,
        input=sql,
        text=True,
        cwd=str(root),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"postgres exec failed ({proc.returncode}): {proc.stderr or proc.stdout}"
        )
    return proc.stdout
