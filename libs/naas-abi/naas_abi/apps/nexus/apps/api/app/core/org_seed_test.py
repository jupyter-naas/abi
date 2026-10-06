from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import bcrypt
import pytest
from naas_abi.apps.nexus.apps.api.app.core import org_seed
from naas_abi.apps.nexus.apps.api.app.core.config import UserSeedConfig

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


def test_an_existing_admin_with_a_real_password_is_left_alone(seed_admin) -> None:
    original = _hash(CUSTOM)
    user = SimpleNamespace(is_superadmin=True, hashed_password=original, updated_at=None)
    secrets = FakeSecrets()

    seed_admin(user, secrets)

    assert user.hashed_password == original
    assert PASSWORD_KEY not in secrets.values
