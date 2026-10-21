# AuthPersistencePort

## What it is
- Defines the persistence interface (“port”) for authentication-related storage operations.
- Provides dataclasses representing records returned from persistence (users and tokens).
- All persistence operations are asynchronous and must be implemented by an adapter (e.g., database repository).

## Public API

### Data records
- `AuthUserRecord`
  - User record fields:
    - `id: str`, `email: str`, `name: str`, `hashed_password: str`, `created_at: datetime`
    - Optional: `avatar`, `company`, `role`, `bio`
- `PasswordResetTokenRecord`
  - Password reset token fields:
    - `id: str`, `user_id: str`, `token: str`, `expires_at: datetime`, `used: bool`, `created_at: datetime`
- `MagicLinkTokenRecord`
  - Magic link token fields:
    - `id: str`, `user_id: str`, `token: str`, `expires_at: datetime`, `used: bool`, `created_at: datetime`

### Persistence port (abstract base class)
- `class AuthPersistencePort(ABC)`
  - `async get_user_by_id(user_id: str) -> AuthUserRecord | None`
    - Fetch a user by ID.
  - `async get_user_by_email(email: str) -> AuthUserRecord | None`
    - Fetch a user by email.
  - `async user_exists_with_email(email: str, exclude_user_id: str | None = None) -> bool`
    - Check whether an email is already in use, optionally excluding a given user ID.
  - `async create_user_with_personal_workspace(user_id: str, email: str, name: str, hashed_password: str, now: datetime) -> AuthUserRecord`
    - Create a new user and an associated personal workspace (implementation-defined).
  - `async update_user_profile(user_id: str, name: str | None, email: str | None, company: str | None, role: str | None, bio: str | None) -> AuthUserRecord | None`
    - Update profile fields; returns updated user or `None` if not found.
  - `async update_user_password(user_id: str, hashed_password: str, now: datetime) -> bool`
    - Update the user password; returns success status.
  - `async create_password_change_event(user_id: str, changed_at: datetime, ip_address: str | None, user_agent: str | None) -> None`
    - Record a password change event.
  - `async mark_unused_password_reset_tokens_used(user_id: str) -> None`
    - Mark existing unused password reset tokens as used for the given user.
  - `async create_password_reset_token(token_id: str, user_id: str, token: str, expires_at: datetime, created_at: datetime) -> None`
    - Persist a new password reset token.
  - `async get_password_reset_token(token: str) -> PasswordResetTokenRecord | None`
    - Fetch a password reset token record by token string.
  - `async mark_password_reset_token_used(token_id: str) -> None`
    - Mark a password reset token as used by token ID.
  - `async mark_unused_magic_link_tokens_used(user_id: str, keep_latest_unused: int = 0) -> None`
    - Mark unused magic link tokens as used; may keep a number of latest unused tokens.
  - `async create_magic_link_token(token_id: str, user_id: str, token: str, expires_at: datetime, created_at: datetime) -> None`
    - Persist a new magic link token.
  - `async get_magic_link_token(token: str) -> MagicLinkTokenRecord | None`
    - Fetch a magic link token record by token string.
  - `async mark_magic_link_token_used(token_id: str) -> None`
    - Mark a magic link token as used by token ID.
  - `async update_user_avatar(user_id: str, avatar_url: str, now: datetime) -> AuthUserRecord | None`
    - Update the user avatar URL; returns updated user or `None` if not found.
  - `async commit() -> None`
    - Commit pending changes (transaction boundary is implementation-defined).

## Configuration/Dependencies
- Depends on standard library:
  - `abc.ABC`, `abc.abstractmethod`
  - `dataclasses.dataclass`
  - `datetime.datetime`
- Requires an implementation that provides concrete async methods for storage access and transactional semantics.

## Usage
Minimal example implementing the port with an in-memory store:

```python
import asyncio
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.auth.port import (
    AuthPersistencePort, AuthUserRecord
)

class InMemoryAuthPersistence(AuthPersistencePort):
    def __init__(self):
        self.users = {}

    async def get_user_by_id(self, user_id: str):
        return self.users.get(user_id)

    async def get_user_by_email(self, email: str):
        return next((u for u in self.users.values() if u.email == email), None)

    async def user_exists_with_email(self, email: str, exclude_user_id: str | None = None) -> bool:
        u = await self.get_user_by_email(email)
        return u is not None and u.id != exclude_user_id

    async def create_user_with_personal_workspace(self, user_id, email, name, hashed_password, now):
        user = AuthUserRecord(id=user_id, email=email, name=name, hashed_password=hashed_password, created_at=now)
        self.users[user_id] = user
        return user

    async def update_user_profile(self, user_id, name, email, company, role, bio):
        user = self.users.get(user_id)
        if not user:
            return None
        self.users[user_id] = AuthUserRecord(
            id=user.id,
            email=email or user.email,
            name=name or user.name,
            hashed_password=user.hashed_password,
            created_at=user.created_at,
            avatar=user.avatar,
            company=company if company is not None else user.company,
            role=role if role is not None else user.role,
            bio=bio if bio is not None else user.bio,
        )
        return self.users[user_id]

    async def update_user_password(self, user_id, hashed_password, now):
        user = self.users.get(user_id)
        if not user:
            return False
        self.users[user_id] = AuthUserRecord(**{**user.__dict__, "hashed_password": hashed_password})
        return True

    async def create_password_change_event(self, user_id, changed_at, ip_address, user_agent): ...
    async def mark_unused_password_reset_tokens_used(self, user_id): ...
    async def create_password_reset_token(self, token_id, user_id, token, expires_at, created_at): ...
    async def get_password_reset_token(self, token): ...
    async def mark_password_reset_token_used(self, token_id): ...
    async def mark_unused_magic_link_tokens_used(self, user_id, keep_latest_unused: int = 0): ...
    async def create_magic_link_token(self, token_id, user_id, token, expires_at, created_at): ...
    async def get_magic_link_token(self, token): ...
    async def mark_magic_link_token_used(self, token_id): ...
    async def update_user_avatar(self, user_id, avatar_url, now): ...
    async def commit(self): ...

async def main():
    repo = InMemoryAuthPersistence()
    now = datetime.utcnow()
    user = await repo.create_user_with_personal_workspace("u1", "a@example.com", "Alice", "hash", now)
    assert await repo.get_user_by_email("a@example.com") == user

asyncio.run(main())
```

## Caveats
- This module defines interfaces only; behavior such as token expiry handling, uniqueness, and transaction scope is entirely implementation-dependent.
- All methods are `async`; callers must await them and implementations must be coroutine-compatible.
