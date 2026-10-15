from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import bcrypt
import pytest
from naas_abi.apps.nexus.apps.api.app.core import org_seed
from naas_abi.apps.nexus.apps.api.app.core.config import UserSeedConfig, WorkspaceSeedConfig

ADMIN = "admin@example.com"
PASSWORD_KEY = "NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD"
# Generated per run: an operator-chosen value that is not a shipped default.
CUSTOM = uuid4().hex


class FakeSecrets:
    def __init__(self, values: dict[str, str] | None = None):
        self.values = dict(values or {})

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.values[key] = value


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()


def _matches(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


@pytest.fixture
def seed_admin(monkeypatch: pytest.MonkeyPatch):
    def run(existing_user, secrets: FakeSecrets):
        async def lookup(_session, _email):
            return existing_user

        monkeypatch.setattr(org_seed, "_get_user_by_email", lookup)
        monkeypatch.setattr(
            org_seed.settings,
            "users",
            [UserSeedConfig(email=ADMIN, name="Admin", is_superadmin=True)],
        )
        session = MagicMock()
        import asyncio

        asyncio.run(org_seed._upsert_users(session=session, secret_service=secrets))
        return session

    return run


@pytest.mark.parametrize("default", ["Admin1234!", "admin"])
def test_a_new_admin_never_gets_a_default_password_from_env(seed_admin, default: str) -> None:
    secrets = FakeSecrets({"NEXUS_USER_ADMIN_EXAMPLE_COM_EMAIL": ADMIN, PASSWORD_KEY: default})

    session = seed_admin(None, secrets)

    created = session.add.call_args.args[0]
    assert not _matches(default, created.hashed_password)
    assert secrets.values[PASSWORD_KEY] != default
    assert _matches(secrets.values[PASSWORD_KEY], created.hashed_password)


def test_a_new_admin_uses_a_custom_password_from_env(seed_admin) -> None:
    secrets = FakeSecrets({"NEXUS_USER_ADMIN_EXAMPLE_COM_EMAIL": ADMIN, PASSWORD_KEY: CUSTOM})

    session = seed_admin(None, secrets)

    assert _matches(CUSTOM, session.add.call_args.args[0].hashed_password)


@pytest.mark.parametrize("default", ["Admin1234!", "admin"])
def test_an_existing_admin_with_a_default_password_is_rotated(seed_admin, default: str) -> None:
    user = SimpleNamespace(is_superadmin=True, hashed_password=_hash(default), updated_at=None)
    secrets = FakeSecrets({PASSWORD_KEY: default})

    seed_admin(user, secrets)

    assert not _matches(default, user.hashed_password)
    assert _matches(secrets.values[PASSWORD_KEY], user.hashed_password)


def test_reseed_keeps_a_wallpaper_the_config_does_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = "/api/workspaces/ws-1/background-image?v=abc.png"
    workspace = SimpleNamespace(
        id="ws-1",
        owner_id="user-1",
        organization_id="org-1",
        background_image_url=saved,
        primary_color="#000000",
        updated_at=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    owner = SimpleNamespace(id="user-1")

    async def owner_lookup(*_args, **_kwargs):
        return owner

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(org_seed, "_resolve_user", owner_lookup)
    monkeypatch.setattr(org_seed, "_get_user_by_id", owner_lookup)
    monkeypatch.setattr(org_seed, "_ensure_workspace_member", noop)
    monkeypatch.setattr(org_seed, "_seed_workspace_apps", noop)

    cfg = WorkspaceSeedConfig(
        name="Forvis Mazars France",
        slug="forvis-mazars-france",
        owner_email=ADMIN,
        primary_color="#0057B8",
    )

    asyncio.run(
        org_seed._upsert_workspace(
            session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
        )
    )

    assert workspace.background_image_url == saved
    assert workspace.primary_color == "#0057B8"


def test_reseed_applies_a_wallpaper_the_config_sets(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = SimpleNamespace(
        id="ws-1",
        owner_id="user-1",
        organization_id="org-1",
        background_image_url="/api/workspaces/ws-1/background-image?v=custom.png",
        updated_at=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    owner = SimpleNamespace(id="user-1")

    async def owner_lookup(*_args, **_kwargs):
        return owner

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(org_seed, "_resolve_user", owner_lookup)
    monkeypatch.setattr(org_seed, "_get_user_by_id", owner_lookup)
    monkeypatch.setattr(org_seed, "_ensure_workspace_member", noop)
    monkeypatch.setattr(org_seed, "_seed_workspace_apps", noop)

    seeded = "src/external/valeo/assets/public/cover.webp"
    cfg = WorkspaceSeedConfig(
        name="Valeo",
        slug="valeo",
        owner_email=ADMIN,
        background_image_url=seeded,
    )

    asyncio.run(
        org_seed._upsert_workspace(
            session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
        )
    )

    assert workspace.background_image_url == seeded


def test_an_existing_admin_with_a_real_password_is_left_alone(seed_admin) -> None:
    original = _hash(CUSTOM)
    user = SimpleNamespace(is_superadmin=True, hashed_password=original, updated_at=None)
    secrets = FakeSecrets()

    seed_admin(user, secrets)

    assert user.hashed_password == original
    assert PASSWORD_KEY not in secrets.values


@pytest.fixture
def seed_users(monkeypatch: pytest.MonkeyPatch):
    def run(existing_user, users: list[UserSeedConfig]):
        async def lookup(_session, _email):
            return existing_user

        monkeypatch.setattr(org_seed, "_get_user_by_email", lookup)
        monkeypatch.setattr(org_seed.settings, "users", users)
        asyncio.run(org_seed._upsert_users(session=MagicMock(), secret_service=FakeSecrets()))

    return run


def test_config_promotes_an_existing_user_to_superadmin(seed_users) -> None:
    user = SimpleNamespace(is_superadmin=False, hashed_password=_hash(CUSTOM), updated_at=None)

    seed_users(user, [UserSeedConfig(email=ADMIN, name="Admin", is_superadmin=True)])

    assert user.is_superadmin is True


def test_config_never_demotes_a_superadmin_promoted_in_the_platform(seed_users) -> None:
    user = SimpleNamespace(is_superadmin=True, hashed_password=_hash(CUSTOM), updated_at=None)

    seed_users(user, [UserSeedConfig(email=ADMIN, name="Admin", is_superadmin=False)])

    assert user.is_superadmin is True


def _patch_member_helpers(monkeypatch: pytest.MonkeyPatch, owner) -> list[tuple]:
    ensured: list[tuple] = []

    async def owner_lookup(*_args, **_kwargs):
        return owner

    async def record_ws_member(_session, workspace_id, user_id, role):
        ensured.append(("workspace", workspace_id, user_id, role))

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(org_seed, "_resolve_user", owner_lookup)
    monkeypatch.setattr(org_seed, "_get_user_by_id", owner_lookup)
    monkeypatch.setattr(org_seed, "_ensure_workspace_member", record_ws_member)
    monkeypatch.setattr(org_seed, "_seed_workspace_apps", noop)
    return ensured


def test_workspace_seed_only_ensures_the_owner_and_ignores_members(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    workspace = SimpleNamespace(
        id="ws-1", owner_id="user-1", organization_id="org-1", updated_at=None
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    ensured = _patch_member_helpers(monkeypatch, SimpleNamespace(id="user-1"))
    cfg = WorkspaceSeedConfig(
        name="Valeo",
        slug="valeo",
        owner_email=ADMIN,
        members=[{"email": "someone@example.com", "role": "admin"}],
    )

    with caplog.at_level("WARNING"):
        asyncio.run(
            org_seed._upsert_workspace(
                session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
            )
        )

    assert ensured == [("workspace", "ws-1", "user-1", "owner")]
    assert "members" in caplog.text and "valeo" in caplog.text


@pytest.mark.parametrize(
    ("current", "expected"),
    [(None, "Key Accounts"), ("", "Key Accounts"), ("Renamed in the UI", "Renamed in the UI")],
)
def test_reseed_sets_the_group_only_when_the_workspace_has_none(
    monkeypatch: pytest.MonkeyPatch, current: str | None, expected: str
) -> None:
    workspace = SimpleNamespace(
        id="ws-1",
        owner_id="user-1",
        organization_id="org-1",
        background_image_url=None,
        workspace_group=current,
        updated_at=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    owner = SimpleNamespace(id="user-1")

    async def owner_lookup(*_args, **_kwargs):
        return owner

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(org_seed, "_resolve_user", owner_lookup)
    monkeypatch.setattr(org_seed, "_get_user_by_id", owner_lookup)
    monkeypatch.setattr(org_seed, "_ensure_workspace_member", noop)
    monkeypatch.setattr(org_seed, "_seed_workspace_apps", noop)

    cfg = WorkspaceSeedConfig(name="Orange", slug="orange", owner_email=ADMIN, group="Key Accounts")
    asyncio.run(
        org_seed._upsert_workspace(
            session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
        )
    )

    assert workspace.workspace_group == expected
