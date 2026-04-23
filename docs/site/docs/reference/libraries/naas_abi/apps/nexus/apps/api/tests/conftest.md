# `conftest.py` (NEXUS API test fixtures)

## What it is
Pytest fixture module for NEXUS API tests that:
- Forces the application to use a dedicated PostgreSQL test database (`nexus_test`).
- Recreates sync/async SQLAlchemy engines/session factories against that database.
- Provides async HTTP client and helper fixtures for users/workspaces.

## Public API
### Fixtures
- `setup_test_db` *(async, autouse)*:  
  Drops/creates `nexus_test`, runs `db_module.init_db()` migrations, and tears down the DB after each test.
- `client` *(async)*:  
  Provides an `httpx.AsyncClient` using `ASGITransport(app=app)` with `base_url="http://testserver"`.
- `test_user`:  
  Inserts a user into `users`, creates an access token (`create_access_token`), returns user data plus auth headers.
- `second_user`:  
  Same as `test_user`, for cross-user isolation tests.
- `test_workspace(test_user)`:  
  Inserts a workspace owned by `test_user` and adds the owner to `workspace_members` with role `owner`.
- `isolated_workspace(second_user)`:  
  Inserts a workspace owned by `second_user` (intended to be inaccessible to `test_user`).

### Helpers
- `add_workspace_member(workspace_id: str, user_id: str, role: str = "member")`:  
  Inserts a row into `workspace_members` for the given user/workspace.

## Configuration/Dependencies
- PostgreSQL connection assumptions:
  - Admin DB: `postgresql://nexus:nexus@localhost:5432/postgres`
  - Test DB: `postgresql://nexus:nexus@localhost:5432/nexus_test`
  - Async driver: `postgresql+asyncpg://nexus:nexus@localhost:5432/nexus_test`
- Patches `app.core.database` module globals at import time:
  - `DATABASE_URL_SYNC`, `DATABASE_URL_ASYNC`, `engine`, `_sync_engine`, `async_engine`, `AsyncSessionLocal`
- Also patches `app.api.endpoints.auth.engine` to use the test sync engine.
- Requires:
  - `pytest`, `pytest-asyncio`
  - `httpx` (ASGITransport, AsyncClient)
  - `sqlalchemy` (sync + async)
  - `bcrypt`

## Usage
Minimal example test using the fixtures:

```python
import pytest

@pytest.mark.asyncio
async def test_authenticated_request(client, test_user):
    resp = await client.get("/health", headers=test_user["headers"])
    assert resp.status_code in (200, 404)  # depends on app routes
```

Using workspace fixtures and helper:

```python
def test_add_member(test_workspace, second_user):
    from conftest import add_workspace_member
    add_workspace_member(test_workspace["id"], second_user["id"], role="member")
```

## Caveats
- `setup_test_db` **drops and recreates** the `nexus_test` database for each test; do not point it at any non-test database.
- Requires a reachable local PostgreSQL instance with credentials `nexus:nexus` and permission to create/drop databases.
- Uses direct SQL `INSERT` statements; tables (`users`, `workspaces`, `workspace_members`) must exist after `db_module.init_db()`.
