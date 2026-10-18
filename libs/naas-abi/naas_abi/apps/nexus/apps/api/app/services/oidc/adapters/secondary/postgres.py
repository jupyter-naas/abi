"""``OidcSessionPersistencePort`` on Nexus's database (PostgreSQL or SQLite)."""

from __future__ import annotations

import json
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.models import (
    AuthSessionModel,
    OidcLoginRequestModel,
    OrganizationDomainModel,
    UserModel,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc.port import (
    LoginRequest,
    OidcSessionPersistencePort,
    OidcUser,
    SessionRecord,
    UserConflictError,
)
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def _user(model: UserModel) -> OidcUser:
    return OidcUser(
        id=model.id,
        email=model.email,
        name=model.name,
        principal_id=model.principal_id,
        idp_issuer=model.idp_issuer,
        idp_subject=model.idp_subject,
    )


def _session(model: AuthSessionModel) -> SessionRecord:
    try:
        groups = tuple(str(g) for g in json.loads(model.group_ids or "[]"))
    except ValueError:
        groups = ()
    return SessionRecord(
        id=model.id,
        user_id=model.user_id,
        principal_id=model.principal_id,
        provider=model.provider,
        group_ids=groups,
        refresh_token_enc=model.refresh_token_enc,
        id_token_enc=model.id_token_enc,
        refresh_at=model.refresh_at,
        expires_at=model.expires_at,
        last_seen_at=model.last_seen_at,
        revoked_at=model.revoked_at,
    )


class OidcSessionSecondaryAdapterPostgres(OidcSessionPersistencePort):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- login requests ---------------------------------------------------------

    async def save_login_request(self, request: LoginRequest) -> None:
        self.db.add(
            OidcLoginRequestModel(
                state_hash=request.state_hash,
                provider=request.provider,
                nonce=request.nonce,
                code_verifier=request.code_verifier,
                binding_hash=request.binding_hash,
                next_path=request.next_path,
                expires_at=request.expires_at,
            )
        )
        await self.db.flush()

    async def take_login_request(self, state_hash: str) -> LoginRequest | None:
        model = await self.db.get(OidcLoginRequestModel, state_hash)
        if model is None:
            return None
        # Deleted by key: of two callbacks racing, only one deletes the row.
        deleted = await self.db.execute(
            delete(OidcLoginRequestModel).where(OidcLoginRequestModel.state_hash == state_hash)
        )
        if deleted.rowcount != 1:  # type: ignore[attr-defined]
            return None
        return LoginRequest(
            state_hash=model.state_hash,
            provider=model.provider,
            nonce=model.nonce,
            code_verifier=model.code_verifier,
            binding_hash=model.binding_hash,
            next_path=model.next_path or "/",
            expires_at=model.expires_at,
        )

    async def purge_login_requests(self, now: datetime) -> None:
        await self.db.execute(
            delete(OidcLoginRequestModel).where(OidcLoginRequestModel.expires_at <= now)
        )

    # -- users ------------------------------------------------------------------

    async def user_by_principal(self, principal_id: str) -> OidcUser | None:
        model = (
            await self.db.execute(select(UserModel).where(UserModel.principal_id == principal_id))
        ).scalar_one_or_none()
        return _user(model) if model is not None else None

    async def email_taken(self, email: str, *, except_user_id: str | None = None) -> bool:
        query = select(UserModel.id).where(func.lower(UserModel.email) == email.lower())
        if except_user_id is not None:
            query = query.where(UserModel.id != except_user_id)
        return (await self.db.execute(query.limit(1))).first() is not None

    async def create_user(
        self,
        *,
        user_id: str,
        email: str,
        name: str,
        principal_id: str,
        provider: str,
        issuer: str,
        subject: str,
        now: datetime,
    ) -> OidcUser:
        model = UserModel(
            id=user_id,
            email=email,
            name=name,
            # No password: the provider signs the user in.
            hashed_password="",
            principal_id=principal_id,
            idp_provider=provider,
            idp_issuer=issuer,
            idp_subject=subject,
            created_at=now,
            updated_at=now,
        )
        self.db.add(model)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            # A concurrent sign-in of this user (a double click, two tabs) won
            # the insert: nothing else is pending in this session.
            await self.db.rollback()
            existing = await self.user_by_principal(principal_id)
            if existing is None:
                raise UserConflictError(email) from exc
            return existing
        return _user(model)

    async def update_user(
        self, user_id: str, *, email: str | None, name: str | None, now: datetime
    ) -> None:
        values: dict[str, object] = {"updated_at": now}
        if email is not None:
            values["email"] = email
        if name is not None:
            values["name"] = name
        await self.db.execute(update(UserModel).where(UserModel.id == user_id).values(**values))

    async def provider_for_domain(self, domain: str) -> str | None:
        return (
            await self.db.execute(
                select(OrganizationDomainModel.provider).where(
                    func.lower(OrganizationDomainModel.domain) == domain.lower(),
                    OrganizationDomainModel.is_verified.is_(True),
                    OrganizationDomainModel.provider.is_not(None),
                )
            )
        ).scalar_one_or_none()

    # -- sessions ---------------------------------------------------------------

    async def create_session(self, session: SessionRecord, *, user_agent: str | None) -> None:
        self.db.add(
            AuthSessionModel(
                id=session.id,
                user_id=session.user_id,
                principal_id=session.principal_id,
                provider=session.provider,
                group_ids=json.dumps(list(session.group_ids)),
                refresh_token_enc=session.refresh_token_enc,
                id_token_enc=session.id_token_enc,
                refresh_at=session.refresh_at,
                expires_at=session.expires_at,
                created_at=session.last_seen_at,
                last_seen_at=session.last_seen_at,
                user_agent=user_agent,
            )
        )
        await self.db.flush()

    async def get_session(self, session_id: str) -> SessionRecord | None:
        model = (
            await self.db.execute(
                select(AuthSessionModel)
                .where(AuthSessionModel.id == session_id)
                # The row as it is now: this session's identity map may still
                # hold an older read of it.
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return _session(model) if model is not None else None

    async def swap_refresh_at(
        self, session_id: str, *, expected: datetime, value: datetime
    ) -> bool:
        swapped = await self.db.execute(
            update(AuthSessionModel)
            .where(
                AuthSessionModel.id == session_id,
                AuthSessionModel.refresh_at == expected,
                AuthSessionModel.revoked_at.is_(None),
            )
            .values(refresh_at=value)
            # The statement alone decides; no stale object is synchronized.
            .execution_options(synchronize_session=False)
        )
        return swapped.rowcount == 1  # type: ignore[attr-defined]

    async def update_session(
        self,
        session_id: str,
        *,
        group_ids: tuple[str, ...] | None = None,
        refresh_token_enc: str | None = None,
        id_token_enc: str | None = None,
        refresh_at: datetime | None = None,
        last_seen_at: datetime | None = None,
    ) -> None:
        values: dict[str, object] = {}
        if group_ids is not None:
            values["group_ids"] = json.dumps(list(group_ids))
        if refresh_token_enc is not None:
            values["refresh_token_enc"] = refresh_token_enc
        if id_token_enc is not None:
            values["id_token_enc"] = id_token_enc
        if refresh_at is not None:
            values["refresh_at"] = refresh_at
        if last_seen_at is not None:
            values["last_seen_at"] = last_seen_at
        if values:
            await self.db.execute(
                update(AuthSessionModel).where(AuthSessionModel.id == session_id).values(**values)
            )

    async def revoke_session(self, session_id: str, now: datetime) -> None:
        await self.db.execute(
            update(AuthSessionModel)
            .where(AuthSessionModel.id == session_id, AuthSessionModel.revoked_at.is_(None))
            .values(revoked_at=now, refresh_token_enc=None, id_token_enc=None)
        )

    async def commit(self) -> None:
        await self.db.commit()
