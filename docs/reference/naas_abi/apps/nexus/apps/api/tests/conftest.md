# conftest (NEXUS API test fixtures)

## What it is
Pytest/pytest-asyncio fixtures and helpers for NEXUS API tests that:

- Patch the application’s database configuration to use a dedicated PostgreSQL test database.
- Create/drop a fresh test database per test.
- Provide an async HTTP client against the ASGI app.
- Provide fixtures for users and workspaces plus a helper to add workspace members.

## Public API
- `setup_test_db` (autouse async fixture)
  - Drops/creates `nexus_test`, runs `db_module.init_db()`, and cleans up by disposing engines and dropping the DB after each test.
- `client` (async fixture)
  - Returns an `httpx.AsyncClient` using `ASGITransport(app=app)` with `base_url="http://testserver"`.
- `test_user` (fixture)
  - Inserts a user into the `users` table and returns a dict with `id`, `email`, `name`, `token`, and `headers` (`Authorization: Bearer ...`).
- `second_user` (fixture)
  - Same as `test_user`, used for cross-user isolation tests.
- `test_workspace` (fixture, depends on `test_user`)
  - Inserts a workspace owned by `test_user` and adds the owner to `workspace_members` with role `owner`.
- `isolated_workspace` (fixture, depends on `second_user`)
  - Inserts a workspace owned by `second_user` (intended to be inaccessible to `test_user`).
- `add_workspace_member(workspace_id: str, user_id: str, role: str = "member")`
  - Inserts a row into `workspace_members` for the given workspace/user with the specified role.

## Configuration/Dependencies
- Requires a reachable PostgreSQL server at:
  - Admin DB: `postgresql://nexus:nexus@localhost:5432/postgres`
  - Test DB: `postgresql://nexus:nexus@localhost:5432/nexus_test`
  - Async driver: `postgresql+asyncpg://nexus:nexus@localhost:5432/nexus_test`
- Patches module globals before importing the app:
  - `app.core.database` (`DATABASE_URL_SYNC`, `DATABASE_URL_ASYNC`, `engine`, `async_engine`, `AsyncSessionLocal`)
  - `app.api.endpoints.auth.engine` (for sync helpers)
- Uses:
  - `bcrypt` to generate `TEST_PASSWORD_HASH`
  - `sqlalchemy` sync engine for direct inserts in fixtures
  - `httpx` (`ASGITransport`, `AsyncClient`)
  - `pytest`, `pytest_asyncio`

## Usage
```python
import pytest

@pytest.mark.asyncio
async def test_me(client, test_user, test_workspace):
    r = await client.get(
        f"/workspaces/{test_workspace['id']}",
        headers=test_user["headers"],
    )
    assert r.status_code in (200, 404)  # depends on the API implementation
```

Adding a member to a workspace:
```python
def test_add_member(test_workspace, second_user):
    from conftest import add_workspace_member

    add_workspace_member(test_workspace["id"], second_user["id"], role="member")
```

## Caveats
- **Destructive behavior:** `setup_test_db` drops and recreates the `nexus_test` database **for each test**.
- **Requires privileges:** the configured Postgres user must be able to `DROP DATABASE` and `CREATE DATABASE`.
- **Assumes schema/tables exist after migrations:** fixtures insert directly into `users`, `workspaces`, and `workspace_members` via SQL text.
