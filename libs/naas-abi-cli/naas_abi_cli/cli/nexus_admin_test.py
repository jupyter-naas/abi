"""Tests for Nexus workspace/user/org admin CLI (parsing + dry-run)."""

from __future__ import annotations

import json
from typing import Any, Self

import pytest
from click.testing import CliRunner

from naas_abi_cli.cli import _main, nexus_client
from naas_abi_cli.cli.nexus_postgres import create_user_sql, create_workspace_sql, esc


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_workspace_create_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "workspace",
            "create",
            "--name",
            "Research preview",
            "--slug",
            "research-preview",
            "--org",
            "org-960fbfdd82bc",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["method"] == "POST"
    assert payload["path"] == "/api/workspaces"
    assert payload["body"]["slug"] == "research-preview"
    assert payload["body"]["organization_id"] == "org-960fbfdd82bc"


def test_workspace_list_org_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        ["workspace", "list", "--org", "org-960fbfdd82bc", "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["path"] == "/api/organizations/org-960fbfdd82bc/workspaces"


def test_user_create_dry_run_redacts_password(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "user",
            "create",
            "--email",
            "tester@naas.ai",
            "--name",
            "Tester",
            "--password",
            "supersecret1",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["path"] == "/api/auth/register"
    assert payload["body"]["email"] == "tester@naas.ai"
    assert payload["body"]["password"] == "***"


def test_user_invite_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "user",
            "invite",
            "--email",
            "tester@naas.ai",
            "--workspace",
            "ws-abc",
            "--role",
            "member",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["path"] == "/api/workspaces/ws-abc/members/invite"
    assert payload["body"] == {"email": "tester@naas.ai", "role": "member"}


def test_user_list_requires_scope(runner: CliRunner) -> None:
    result = runner.invoke(_main, ["user", "list", "--dry-run"])
    assert result.exit_code != 0
    assert "exactly one of --org or --workspace" in result.output


def test_org_list_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(_main, ["org", "list", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["path"] == "/api/organizations"


def test_workspace_members_add_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "workspace",
            "members",
            "add",
            "--workspace",
            "ws-1",
            "--email",
            "a@b.co",
            "--role",
            "viewer",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["body"]["role"] == "viewer"


def test_workspace_create_postgres_dry_run_requires_owner(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "workspace",
            "create",
            "--name",
            "X",
            "--slug",
            "x-workspace",
            "--org",
            "org-1",
            "--via",
            "postgres",
            "--dry-run",
        ],
    )
    assert result.exit_code != 0
    assert "--owner-id is required" in result.output


def test_workspace_create_postgres_dry_run_prints_sql(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "workspace",
            "create",
            "--name",
            "Jeremy Ravenel",
            "--slug",
            "jeremy-ravenel",
            "--org",
            "org-960fbfdd82bc",
            "--owner-id",
            "user-0d9665ad586d",
            "--via",
            "postgres",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "INSERT INTO workspaces" in result.output
    assert "jeremy-ravenel" in result.output
    assert "user-0d9665ad586d" in result.output


def test_create_user_sql_contains_memberships(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Bcrypt:
        @staticmethod
        def gensalt() -> bytes:
            return b"$2b$12$abcdefghijklmnopqrstuv"

        @staticmethod
        def hashpw(password: bytes, salt: bytes) -> bytes:
            return b"$2b$12$hashed"

    monkeypatch.setitem(__import__("sys").modules, "bcrypt", _Bcrypt)
    # Force re-import path: create_user_sql imports bcrypt inside the function.
    sql, user_id = create_user_sql(
        email="a@naas.ai",
        name="A",
        password="password12",
        organization_id="org-1",
        workspace_id="ws-1",
    )
    assert user_id.startswith("user-")
    assert "INSERT INTO users" in sql
    assert "organization_members" in sql
    assert "workspace_members" in sql
    assert "a@naas.ai" in sql


def test_create_workspace_sql_escapes_quotes() -> None:
    sql, ws_id = create_workspace_sql(
        name="O'Brien Lab",
        slug="obrien-lab",
        owner_id="user-1",
        organization_id="org-1",
    )
    assert ws_id.startswith("ws-")
    assert "O''Brien Lab" in sql
    assert esc("a'b") == "a''b"


def test_client_get_sends_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _Resp:
        def read(self) -> bytes:
            return b'[{"id":"ws-1"}]'

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(req: Any, timeout: float = 0) -> _Resp:
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        captured["method"] = req.get_method()
        return _Resp()

    monkeypatch.setattr(nexus_client.urllib.request, "urlopen", fake_urlopen)
    client = nexus_client.NexusClient(api_url="http://nexus.test", access_token="tok")
    rows = client.get("/api/workspaces")
    assert rows == [{"id": "ws-1"}]
    assert captured["url"] == "http://nexus.test/api/workspaces"
    assert captured["headers"]["Authorization"] == "Bearer tok"
    assert captured["method"] == "GET"


def test_help_lists_new_groups(runner: CliRunner) -> None:
    result = runner.invoke(_main, ["--help"])
    assert result.exit_code == 0
    assert "workspace" in result.output
    assert "user" in result.output
    assert "org" in result.output
