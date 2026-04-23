# AuthSecondaryAdapterPostgres

## What it is
- A PostgreSQL/SQLAlchemy (async) persistence adapter implementing `AuthPersistencePort`.
- Handles user lookup/updates plus password reset and magic-link token persistence.

## Public API
### Class: `AuthSecondaryAdapterPostgres(AuthPersistencePort)`
- `__init__(db: AsyncSession | None = None, db_getter: Callable[[], AsyncSession | None] | None = None)`
  - Bind an `AsyncSession` directly or via a getter callback.
- `db -> AsyncSession` (property)
  - Returns the bound session; raises `RuntimeError` if none is available.

### User operations
- `get_user_by_id(user_id: str) -> AuthUserRecord | None`
  - Fetch user by id.
- `get_user_by_email(email: str) -> AuthUserRecord | None`
  - Fetch user by email.
- `user_exists_with_email(email: str, exclude_user_id: str | None = None) -> bool`
  - Check if email is used, optionally excluding a user id.
- `create_user_with_personal_workspace(user_id: str, email: str, name: str, hashed_password: str, now: datetime) -> AuthUserRecord`
  - Creates a `UserModel`, a personal `WorkspaceModel` owned by the user, and an `owner` `WorkspaceMemberModel`.
- `update_user_profile(user_id: str, name: str | None, email: str | None, company: str | None, role: str | None, bio: str | None) -> AuthUserRecord | None`
  - Updates provided fields; flushes and refreshes before returning.
- `update_user_password(user_id: str, hashed_password: str, now: datetime) -> bool`
  - Updates password and `updated_at`; returns `False` if user not found.
- `update_user_avatar(user_id: str, avatar_url: str | None, now: datetime) -> AuthUserRecord | None`
  - Updates avatar and `updated_at`; flushes and refreshes before returning.
- `create_password_change_event(user_id: str, changed_at: datetime, ip_address: str | None, user_agent: str | None) -> None`
  - Inserts a row into `password_changes` via raw SQL.

### Password reset tokens
- `mark_unused_password_reset_tokens_used(user_id: str) -> None`
  - Marks all unused reset tokens for the user as used.
- `create_password_reset_token(token_id: str, user_id: str, token: str, expires_at: datetime, created_at: datetime) -> None`
  - Persists a new reset token with `used=False`.
- `get_password_reset_token(token: str) -> PasswordResetTokenRecord | None`
  - Looks up an unused token matching either `hash_token(token)` or the raw token value.
- `mark_password_reset_token_used(token_id: str) -> None`
  - Marks a specific reset token as used.

### Magic-link tokens
- `mark_unused_magic_link_tokens_used(user_id: str, keep_latest_unused: int = 0) -> None`
  - Marks unused tokens as used, keeping the latest `keep_latest_unused` unused (negative treated as 0).
- `create_magic_link_token(token_id: str, user_id: str, token: str, expires_at: datetime, created_at: datetime) -> None`
  - Persists a new magic-link token with `used=False`.
- `get_magic_link_token(token: str) -> MagicLinkTokenRecord | None`
  - Looks up an unused token matching either `hash_token(token)` or the raw token value.
- `mark_magic_link_token_used(token_id: str) -> None`
  - Marks a specific magic-link token as used.

### Transaction control
- `commit() -> None`
  - Commits the current transaction on the bound session.

## Configuration/Dependencies
- Requires an SQLAlchemy `AsyncSession` bound via:
  - `db=...` in the constructor, or
  - `db_getter=...` returning an `AsyncSession` (must not return `None` at call time).
- Uses SQLAlchemy models:
  - `UserModel`, `WorkspaceModel`, `WorkspaceMemberModel`, `PasswordResetTokenModel`, `MagicLinkTokenModel`.
- Uses `hash_token` from `naas_abi.apps.nexus.apps.api.app.services.refresh_token`.
- Expects a `password_changes` table for `create_password_change_event()` (insert via raw SQL).

## Usage
```python
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.secondary.postgres import (
    AuthSecondaryAdapterPostgres,
)

async def main(session: AsyncSession):
    repo = AuthSecondaryAdapterPostgres(db=session)

    now = datetime.now(timezone.utc)
    user = await repo.create_user_with_personal_workspace(
        user_id="usr_123",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        now=now,
    )
    await repo.commit()

    found = await repo.get_user_by_email("user@example.com")
    print(found.id if found else None)

# asyncio.run(main(session))
```

## Caveats
- Methods that mutate data generally do **not** commit automatically; call `commit()` to persist changes.
- `get_*_token()` matches either a hashed token (`hash_token(token)`) or the raw token stored in DB; ensure token storage strategy aligns with this behavior.
- `create_password_change_event()` bypasses ORM models and requires the `password_changes` table schema to match the inserted columns.
