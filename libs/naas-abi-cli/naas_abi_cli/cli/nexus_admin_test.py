"""Tests for Nexus workspace/user/org admin CLI (parsing + dry-run)."""

from __future__ import annotations

import json
from typing import Any, Self

import pytest
from click.testing import CliRunner

from naas_abi_cli.cli import _main, nexus_client
from naas_abi_cli.cli.nexus_postgres import create_workspace_sql, esc


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
    assert payload["body"] == {
        "email": "tester@naas.ai",
        "admin": False,
        "level": "member",
    }


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
    assert (payload["body"]["level"], payload["body"]["admin"]) == ("viewer", False)


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
            "Emma Petit",
            "--slug",
            "emma-petit",
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
    assert "emma-petit" in result.output
    assert "user-0d9665ad586d" in result.output


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


def test_the_client_needs_a_token_and_never_logs_in(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    monkeypatch.delenv("NEXUS_ACCESS_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="abi_pk_"):
        nexus_client.build_client(api_url="http://nexus.test", token=None)
    result = runner.invoke(
        _main, ["user", "list", "--org", "o", "--auth-password", "x"]
    )
    assert result.exit_code != 0
    assert "No such option" in result.output
    assert not hasattr(nexus_client.NexusClient, "_login")


def test_there_is_no_command_that_creates_a_password_account(runner: CliRunner) -> None:
    result = runner.invoke(_main, ["user", "--help"])
    assert result.exit_code == 0
    commands = [
        line.split()[0]
        for line in result.output.split("Commands:")[1].split("\n")
        if line.strip()
    ]
    assert "create" not in commands and "migrate" in commands


# -- abi user migrate ----------------------------------------------------------------------------


@pytest.fixture()
def nexus_db(tmp_path):
    """A Nexus database with two accounts of the old login and one a provider signs in."""
    import asyncio
    import importlib

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    nexus = "naas_abi.apps.nexus.apps.api.app"
    Base = importlib.import_module(f"{nexus}.core.database").Base
    UserModel = importlib.import_module(f"{nexus}.models").UserModel

    url = f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}"

    async def make() -> None:
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncSession(engine) as db:
            db.add(UserModel(id="u-ada", email="Ada@Example.com", name="Ada"))
            db.add(UserModel(id="u-bob", email="bob@example.com", name="Bob"))
            db.add(
                UserModel(
                    id="usr_x",
                    email="carl@example.com",
                    name="Carl",
                    principal_id="usr_x",
                    idp_issuer="https://idp.example",
                    idp_subject="s-carl",
                )
            )
            await db.commit()
        await engine.dispose()

    asyncio.run(make())
    return url


class _Identity:
    default_provider = "builtin"

    def __init__(
        self, provisioning: str = "builtin", existing: tuple[str, ...] = ()
    ) -> None:
        from types import SimpleNamespace

        self._info = SimpleNamespace(
            name="builtin", provisioning=provisioning, issuer="https://idp.example"
        )
        self.people = set(existing)
        self.provisioned: list[tuple[str, str, str | None]] = []

    def list_providers(self):
        return [self._info]

    def provision_user(self, provider, email, *, name=None):
        from types import SimpleNamespace

        if self._info.provisioning != "builtin":
            raise NotImplementedError("managed in the identity provider")
        self.provisioned.append((provider, email, name))
        created = email not in self.people
        self.people.add(email)
        return SimpleNamespace(email=email, created=created, disabled=False)

    def find_provisioned_user(self, provider, email):
        from types import SimpleNamespace

        return SimpleNamespace(email=email) if email in self.people else None


def _migrate(runner: CliRunner, nexus_db: str, identity: _Identity, *args: str):
    from types import SimpleNamespace

    return runner.invoke(
        _main,
        ["user", "migrate", "--database-url", nexus_db, *args],
        obj={
            "services_opener": lambda: (
                SimpleNamespace(identity=identity),
                lambda: None,
            )
        },
    )


def test_migrate_is_a_dry_run_until_it_is_applied(
    runner: CliRunner, nexus_db: str
) -> None:
    identity = _Identity(existing=("bob@example.com",))
    result = _migrate(runner, nexus_db, identity)
    assert result.exit_code == 0, result.output
    assert identity.provisioned == []
    assert "would_create" in result.output and "exists" in result.output
    assert "carl@example.com" not in result.output  # a provider's user is not migrated
    assert "Dry run" in result.output


def test_migrate_applies_and_can_be_run_again(runner: CliRunner, nexus_db: str) -> None:
    identity = _Identity()
    first = _migrate(runner, nexus_db, identity, "--apply")
    assert first.exit_code == 0, first.output
    assert sorted(email for _, email, _ in identity.provisioned) == [
        "ada@example.com",
        "bob@example.com",
    ]
    assert ("builtin", "ada@example.com", "Ada") in identity.provisioned
    again = _migrate(runner, nexus_db, identity, "--apply")
    assert again.exit_code == 0
    assert "created" not in again.output.replace("would_create", "")


def test_migrate_refuses_a_provider_that_does_not_prove_addresses(
    runner: CliRunner, nexus_db: str
) -> None:
    identity = _Identity(provisioning="none")
    result = _migrate(runner, nexus_db, identity, "--apply")
    assert result.exit_code != 0
    assert "built-in identity provider" in result.output
    assert identity.provisioned == []


def _dry(runner: CliRunner, *args: str) -> dict[str, Any]:
    result = runner.invoke(_main, [*args, "--dry-run"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_workspace_members_search_asks_the_candidates(runner: CliRunner) -> None:
    payload = _dry(
        runner, "workspace", "members", "search", "--workspace", "ws-1", "--q", "Flo G"
    )
    assert payload == {
        "method": "GET",
        "path": "/api/workspaces/ws-1/members/candidates?q=Flo+G&limit=10",
    }


def test_workspace_members_add_by_user_id_adds_from_the_directory(
    runner: CliRunner,
) -> None:
    payload = _dry(
        runner,
        "workspace",
        "members",
        "add",
        "--workspace",
        "ws-1",
        "--user-id",
        "usr-9",
    )
    assert payload["path"] == "/api/workspaces/ws-1/members"
    assert payload["body"] == {"admin": False, "user_id": "usr-9"}


def test_workspace_members_add_needs_one_of_user_id_or_email(runner: CliRunner) -> None:
    result = runner.invoke(
        _main, ["workspace", "members", "add", "--workspace", "ws-1", "--dry-run"]
    )
    assert result.exit_code != 0
    assert "exactly one of --user-id or --email" in result.output


def test_members_resend(runner: CliRunner) -> None:
    ws = _dry(
        runner,
        "workspace",
        "members",
        "resend",
        "--workspace",
        "ws-1",
        "--user-id",
        "u1",
    )
    org = _dry(runner, "org", "members", "resend", "--org", "org-1", "--user-id", "u1")
    assert ws["path"] == "/api/workspaces/ws-1/members/u1/resend"
    assert org["path"] == "/api/organizations/org-1/members/u1/resend"


def test_org_invite_names_its_workspaces(runner: CliRunner) -> None:
    payload = _dry(
        runner,
        "org",
        "members",
        "invite",
        "--org",
        "org-1",
        "--email",
        "a@b.co",
        "--workspace",
        "ws-1",
        "--admin",
        "--level",
        "member",
        "--capability",
        "grp_runners",
    )
    assert payload["body"] == {
        "email": "a@b.co",
        "level": "member",
        "workspaces": [{"id": "ws-1", "admin": True}],
        "capabilities": ["grp_runners"],
    }


def test_org_invite_reads_the_options_of_before(runner: CliRunner) -> None:
    payload = _dry(
        runner,
        "org",
        "members",
        "invite",
        "--org",
        "org-1",
        "--email",
        "a@b.co",
        "--role",
        "admin",
        "--workspace",
        "ws-1",
        "--workspace-role",
        "viewer",
        "--no-org-role",
    )
    assert payload["body"] == {
        "email": "a@b.co",
        "level": "viewer",
        "org_admin": True,
        "workspaces": [{"id": "ws-1", "admin": False}],
    }


def test_owner_is_no_longer_given(runner: CliRunner) -> None:
    result = runner.invoke(
        _main,
        [
            "user",
            "invite",
            "--email",
            "a@b.co",
            "--org",
            "org-1",
            "--role",
            "owner",
            "--dry-run",
        ],
    )
    assert result.exit_code != 0
    assert "Owner is no longer given" in result.output


def _pending_invitation(url: str) -> None:
    import asyncio
    import importlib
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    InvitationModel = importlib.import_module(
        "naas_abi.apps.nexus.apps.api.app.models"
    ).InvitationModel

    async def make() -> None:
        engine = create_async_engine(url)
        now = datetime(2026, 11, 19)
        async with AsyncSession(engine) as db:
            db.add(
                InvitationModel(
                    id="inv-dan",
                    email="dan@example.com",
                    provider="builtin",
                    grant_ids="[]",
                    status="pending",
                    created_at=now,
                    updated_at=now,
                )
            )
            await db.commit()
        await engine.dispose()

    asyncio.run(make())


def _migrate_invitations(
    runner: CliRunner, nexus_db: str, identity: _Identity, *args: str
):
    from types import SimpleNamespace

    return runner.invoke(
        _main,
        ["user", "migrate-invitations", "--database-url", nexus_db, *args],
        obj={
            "services_opener": lambda: (
                SimpleNamespace(identity=identity, iam=None),
                lambda: None,
            )
        },
    )


def test_migrate_invitations_lists_then_moves_them_once(
    runner: CliRunner, nexus_db: str
) -> None:
    _pending_invitation(nexus_db)
    identity = _Identity()

    dry = _migrate_invitations(runner, nexus_db, identity)
    assert dry.exit_code == 0, dry.output
    assert "dan@example.com" in dry.output and "Dry run" in dry.output

    applied = _migrate_invitations(runner, nexus_db, identity, "--apply")
    assert applied.exit_code == 0, applied.output
    # No account at the provider yet: an invited row its verified sign-in binds.
    assert "migrated=1 bound=0 unbound=1" in applied.output

    again = _migrate_invitations(runner, nexus_db, identity, "--apply")
    assert again.exit_code == 0, again.output
    assert "migrated=0 bound=0 unbound=0 linked=0" in again.output
    assert "dan@example.com" not in again.output
