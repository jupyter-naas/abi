"""What ``secret_key`` encrypted moves under the secrets key (RFC §13)."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core import config
from naas_abi.apps.nexus.apps.api.app.models import (
    AuthSessionModel,
    SecretModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services import secrets_crypto
from naas_abi.apps.nexus.apps.api.app.services.secrets.migration import move_to_secrets_key
from sqlalchemy import select

OLD = "the-old-signing-key"
NEW = "the-new-secrets-key"
NOW = datetime(2026, 10, 19, 12, 0, 0)


def use(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    monkeypatch.setattr(config, "settings", SimpleNamespace(secrets_encryption_key=key))


def sealed(key: str, value: str) -> str:
    return secrets_crypto._fernet_for(key).encrypt(value.encode()).decode()


LOST = sealed("a-key-nobody-has", "gone")


@pytest_asyncio.fixture
async def rows(nexus_db):
    async with nexus_db() as db:
        db.add(UserModel(id="u1", email="a@example.com", name="A"))
        db.add(WorkspaceModel(id="w1", name="W", slug="w", owner_id="u1"))
        await db.flush()
        for ident, key, value in (
            ("s-old", "OPENAI_API_KEY", sealed(OLD, "sk-old")),
            ("s-default", "ANTHROPIC_API_KEY", sealed("change-me-in-production", "sk-default")),
            ("s-new", "GITHUB_TOKEN", sealed(NEW, "gh-new")),
            ("s-lost", "LOST", LOST),
        ):
            db.add(
                SecretModel(id=ident, workspace_id="w1", key=key, encrypted_value=value)
            )
        db.add(
            AuthSessionModel(
                id="sess-1",
                user_id="u1",
                principal_id="usr_1",
                provider="builtin",
                refresh_token_enc=sealed(OLD, "refresh-1"),
                id_token_enc=sealed(OLD, "id-1"),
                refresh_at=NOW,
                expires_at=NOW + timedelta(days=1),
            )
        )
        db.add(
            AuthSessionModel(
                id="sess-2",
                user_id="u1",
                principal_id="usr_1",
                provider="builtin",
                refresh_token_enc=None,
                id_token_enc=sealed(NEW, "id-2"),
                refresh_at=NOW,
                expires_at=NOW + timedelta(days=1),
            )
        )
        await db.commit()
    return nexus_db


@pytest.mark.asyncio
async def test_secrets_and_session_tokens_move_to_the_secrets_key(rows, monkeypatch) -> None:
    use(monkeypatch, NEW)
    async with rows() as db:
        moved = await move_to_secrets_key(db, [OLD, "change-me-in-production"])
        await db.commit()

    assert (moved.secrets, moved.session_tokens, moved.unreadable) == (2, 2, 1)
    async with rows() as db:
        secrets = {s.id: s.encrypted_value for s in (await db.execute(select(SecretModel))).scalars()}
        for ident, plain in (("s-old", "sk-old"), ("s-default", "sk-default"), ("s-new", "gh-new")):
            assert secrets_crypto.decrypt_secret_value(secrets[ident]) == plain
        # What no known key opens is left as it was, never lost.
        assert secrets_crypto.try_decrypt_secret_value(secrets["s-lost"]) is None
        assert secrets["s-lost"] == LOST
        sessions = {s.id: s for s in (await db.execute(select(AuthSessionModel))).scalars()}
        assert secrets_crypto.decrypt_secret_value(sessions["sess-1"].refresh_token_enc) == "refresh-1"
        assert secrets_crypto.decrypt_secret_value(sessions["sess-1"].id_token_enc) == "id-1"
        assert sessions["sess-2"].refresh_token_enc is None


@pytest.mark.asyncio
async def test_the_old_key_is_no_longer_needed_afterwards(rows, monkeypatch) -> None:
    use(monkeypatch, NEW)
    async with rows() as db:
        await move_to_secrets_key(db, [OLD, "change-me-in-production"])
        await db.commit()
    async with rows() as db:
        rerun = await move_to_secrets_key(db, [])
        assert (rerun.secrets, rerun.session_tokens) == (0, 0)
        # Nothing readable only by the old key is left (the lost one never was).
        assert rerun.unreadable == 1


@pytest.mark.asyncio
async def test_running_again_moves_nothing(rows, monkeypatch) -> None:
    use(monkeypatch, NEW)
    async with rows() as db:
        await move_to_secrets_key(db, [OLD, "change-me-in-production"])
        await db.commit()
    async with rows() as db:
        again = await move_to_secrets_key(db, [OLD, "change-me-in-production"])
    assert (again.secrets, again.session_tokens) == (0, 0)


@pytest.mark.asyncio
async def test_the_signing_key_decrypts_nothing_after_the_move(rows, monkeypatch) -> None:
    use(monkeypatch, NEW)
    async with rows() as db:
        await move_to_secrets_key(db, [OLD, "change-me-in-production"])
        await db.commit()
    use(monkeypatch, OLD)
    async with rows() as db:
        for row in (await db.execute(select(SecretModel).where(SecretModel.id == "s-old"))).scalars():
            assert secrets_crypto.try_decrypt_secret_value(row.encrypted_value) is None


def test_nothing_is_encrypted_under_no_key(monkeypatch) -> None:
    use(monkeypatch, "")
    with pytest.raises(RuntimeError, match="secrets encryption key"):
        secrets_crypto.encrypt_secret_value("x")
