"""Fixtures shared by the Nexus API's unit tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam


@pytest.fixture(autouse=True)
def secrets_key(monkeypatch):
    """The key the API resolves at start (``core/secret_key.py``); nothing is
    encrypted without one."""
    from naas_abi.apps.nexus.apps.api.app.core import config

    monkeypatch.setattr(config.settings, "secrets_encryption_key", "a-secrets-key-for-tests")


@pytest.fixture
def nexus_iam():
    """A real IAM installed as Nexus's: orgs, workspaces and role attachments are
    set up on it (``workspace``, ``grant``) and routes decide with it. Features
    follow the deployment defaults; build ``NexusIam(flags)`` to change them."""
    nexus = NexusIam()
    with nexus.installed():
        yield nexus


@pytest.fixture
def team(nexus_iam: NexusIam) -> NexusIam:
    """``ws-1`` of ``org-1`` with an owner, an admin, a member and a viewer (users
    ``owner``, ``admin``, ``member``, ``viewer``) and ``stranger``, who holds nothing."""
    scope = nexus_iam.workspace("org-1", "ws-1")
    org = nexus_iam.org("org-1")
    for user in ("owner", "admin", "member", "viewer"):
        nexus_iam.grant(user, user, scope)
        nexus_iam.grant(user, user, org)
    nexus_iam.user("stranger")
    return nexus_iam


@pytest_asyncio.fixture
async def nexus_db(tmp_path):
    """A SQLite database holding the Nexus tables, as ``abi dev`` runs them:
    returns the session factory to hand to ``get_db`` overrides."""
    from naas_abi.apps.nexus.apps.api.app.core.database import Base
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
