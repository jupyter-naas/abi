"""
Test fixtures for NEXUS API tests.

Creates an isolated test database and provides helper functions
for authentication, user creation, and workspace setup.

Updated for PostgreSQL test database with async test client.
"""

# The API reads its module configuration from the loaded ``ABIModule`` (an engine
# these tests do not run): a default one, as the route tests of ``app/`` use.
from types import SimpleNamespace  # noqa: E402
from unittest.mock import patch  # noqa: E402
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from naas_abi import ABIModule, NexusConfig  # noqa: E402
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

patch.object(
    ABIModule,
    "get_instance",
    return_value=SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig())),
).start()

# Use PostgreSQL test database
TEST_DB_NAME = "nexus_test"
TEST_DATABASE_URL_SYNC = f"postgresql://nexus:nexus@localhost:5432/{TEST_DB_NAME}"
TEST_DATABASE_URL_ASYNC = f"postgresql+asyncpg://nexus:nexus@localhost:5432/{TEST_DB_NAME}"

# Patch the database module before the app imports it
import naas_abi.apps.nexus.apps.api.app.core.database as db_module  # noqa: E402

db_module.DATABASE_URL_SYNC = TEST_DATABASE_URL_SYNC
db_module.DATABASE_URL_ASYNC = TEST_DATABASE_URL_ASYNC

# Recreate sync engine for test DB
db_module.engine = create_engine(
    db_module.DATABASE_URL_SYNC,
    echo=False,
)
db_module._sync_engine = db_module.engine

# Recreate async engine + session factory for test DB
db_module.async_engine = create_async_engine(
    db_module.DATABASE_URL_ASYNC,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
db_module.AsyncSessionLocal = async_sessionmaker(
    db_module.async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Patch the engine in the auth module (it imports engine at module level for sync helpers)
import naas_abi.apps.nexus.apps.api.app.api.endpoints.auth as auth_module  # noqa: E402

# Now we can safely import the app
from naas_abi.apps.nexus.apps.api.app.main import app  # noqa: E402

auth_module.engine = db_module.engine

# The services the routes reach through the registry (the app's startup builds it).
from naas_abi.apps.nexus.apps.api.app.services.registry_bootstrap import (  # noqa: E402
    initialize_nexus_service_registry,
)

initialize_nexus_service_registry()


# ============================================
# Fixtures
# ============================================


# Authorization is IAM's: a real one on the memory store, with the roles each
# fixture attaches (what the routes themselves do for a membership).
CURRENT_IAM: list = []


@pytest.fixture(autouse=True)
def secrets_key(monkeypatch):
    """The key the API resolves at start; nothing is encrypted without one."""
    from naas_abi.apps.nexus.apps.api.app.core import config

    monkeypatch.setattr(config.settings, "secrets_encryption_key", "a-secrets-key-for-tests")


@pytest.fixture(autouse=True)
def iam_world():
    from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
    from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam

    nexus = NexusIam()
    CURRENT_IAM[:] = [nexus]
    # The sessions the tests present are the engine's: this IAM issues and checks them.
    previous = credentials.configure_iam(lambda: nexus.iam)
    try:
        with nexus.installed():
            yield nexus
    finally:
        credentials.configure_iam(previous)
        CURRENT_IAM.clear()


def _session(user_id: str) -> dict:
    """A signed-in user: the engine's session token for them (``abi:session``)."""
    from naas_abi.apps.nexus.apps.api.app.services.auth.testing import session_token

    token = session_token(CURRENT_IAM[0].iam, user_id)
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}}


def _grant(workspace_id: str, user_id: str, role: str) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import NO_ORG

    nexus = CURRENT_IAM[0]
    scope = nexus.workspace(None, workspace_id)
    assert NO_ORG in scope
    nexus.grant(user_id, role, scope)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Create a fresh test database for each test."""
    # Drop and recreate test database
    with create_engine(
        "postgresql://nexus:nexus@localhost:5432/postgres", isolation_level="AUTOCOMMIT"
    ).connect() as conn:
        # Drop test DB if exists
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        # Create fresh test DB
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))

    # Run application migrations using the app's migration routine
    # against the test database engine configured above.
    await db_module.init_db()

    yield

    # Clean up: drop test database and dispose async engine to close connections
    await db_module.async_engine.dispose()
    try:
        db_module.engine.dispose()
    except Exception:
        pass

    with create_engine(
        "postgresql://nexus:nexus@localhost:5432/postgres", isolation_level="AUTOCOMMIT"
    ).connect() as conn:
        # Terminate connections to test DB
        conn.execute(
            text(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid()
        """)
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def test_user():
    """Create a test user and return their data."""
    user_id = f"user-{uuid4().hex[:8]}"
    email = f"test-{uuid4().hex[:6]}@example.com"
    name = "Test User"

    with db_module.engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO users (id, email, name, created_at, updated_at)
                VALUES (:id, :email, :name, NOW(), NOW())
            """),
            {"id": user_id, "email": email, "name": name},
        )
        conn.commit()

    return {"id": user_id, "email": email, "name": name, **_session(user_id)}


@pytest.fixture
def second_user():
    """Create a second test user (for cross-user tests)."""
    user_id = f"user-{uuid4().hex[:8]}"
    email = f"other-{uuid4().hex[:6]}@example.com"
    name = "Other User"

    with db_module.engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO users (id, email, name, created_at, updated_at)
                VALUES (:id, :email, :name, NOW(), NOW())
            """),
            {"id": user_id, "email": email, "name": name},
        )
        conn.commit()

    return {"id": user_id, "email": email, "name": name, **_session(user_id)}


@pytest.fixture
def test_workspace(test_user):
    """Create a test workspace owned by test_user."""
    ws_id = f"ws-{uuid4().hex[:8]}"

    with db_module.engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO workspaces (id, name, slug, owner_id, created_at, updated_at)
                VALUES (:id, :name, :slug, :owner_id, NOW(), NOW())
            """),
            {
                "id": ws_id,
                "name": "Test Workspace",
                "slug": f"test-{uuid4().hex[:6]}",
                "owner_id": test_user["id"],
            },
        )
        conn.commit()

    _grant(ws_id, test_user["id"], "owner")
    return {"id": ws_id, "name": "Test Workspace", "owner_id": test_user["id"]}


@pytest.fixture
def isolated_workspace(second_user):
    """Create a workspace owned by second_user (test_user has NO access)."""
    ws_id = f"ws-{uuid4().hex[:8]}"

    with db_module.engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO workspaces (id, name, slug, owner_id, created_at, updated_at)
                VALUES (:id, :name, :slug, :owner_id, NOW(), NOW())
            """),
            {
                "id": ws_id,
                "name": "Isolated Workspace",
                "slug": f"iso-{uuid4().hex[:6]}",
                "owner_id": second_user["id"],
            },
        )
        conn.commit()

    _grant(ws_id, second_user["id"], "owner")
    return {"id": ws_id, "name": "Isolated Workspace", "owner_id": second_user["id"]}


def add_workspace_member(workspace_id: str, user_id: str, role: str = "member"):
    """Helper: give a user a role in a workspace (an IAM role attachment)."""
    _grant(workspace_id, user_id, role)
