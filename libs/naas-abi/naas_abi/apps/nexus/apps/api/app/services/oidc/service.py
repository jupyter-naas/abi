"""Nexus as an OIDC client of the engine's identity providers (RFC §12.1).

* **Sign-in** is authorization code with PKCE (S256). Nexus keeps the state,
  the nonce and the code verifier server-side, bound to the browser by a
  cookie; the engine builds the authorization URL and redeems the code with
  the provider's client secret, which Nexus never holds.
* **A user** is one Nexus row per ``(issuer, sub)``, whose id is its IAM
  principal id. Nothing is linked across providers or to a built-in account:
  a verified email another account holds refuses the sign-in.
* **The session** is a random secret in an httpOnly cookie; Nexus stores its
  SHA-256, the user, and the provider's refresh token, encrypted. The provider
  vouches for the user again at least every ten minutes (``refresh_at``); a
  refresh it refuses, or an IAM suspension, ends the session at once.
* **CSRF**: a request the cookie authenticates and that changes state carries
  ``X-CSRF-Token``, an HMAC of the session secret Nexus hands the web app
  (``csrf_token``). The browser keeps it in memory only.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import secrets
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.oidc.port import (
    IdentityGateway,
    LoginRequest,
    OidcSessionPersistencePort,
    OidcUser,
    PrincipalGateway,
    SessionRecord,
)
from naas_abi_core import logger
from naas_abi_core.services.identity.IdentityPorts import (
    AuthenticatedUser,
    PrincipalSuspendedError,
    ProviderUnavailableError,
    SignIn,
    SignInError,
    TokenRejectedError,
    UnknownProviderError,
)

LOGIN_REQUEST_SECONDS = 600
# A provider's email that is absent or unverified is never stored as such: a
# placeholder that routes nowhere (".internal" is reserved for private use and
# never delegated), so no invitation or lookup by email finds the account.
PLACEHOLDER_EMAIL_DOMAIN = "unverified.internal"
_LAST_SEEN_EVERY = timedelta(minutes=1)
_CSRF_CONTEXT = b"nexus-csrf-v1"


def now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def code_challenge(verifier: str) -> str:
    raw = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def csrf_token(session_secret: str) -> str:
    """The CSRF token of a session: derived from its secret, never stored."""
    mac = hmac.new(session_secret.encode("utf-8"), _CSRF_CONTEXT, hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).rstrip(b"=").decode("ascii")


def csrf_matches(session_secret: str, presented: str | None) -> bool:
    return bool(presented) and hmac.compare_digest(csrf_token(session_secret), presented or "")


def safe_next_path(value: str | None) -> str:
    """A path on the web app: never another origin, never a scheme."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    if any(ord(c) < 32 for c in value):
        return "/"
    return value[:2048]


class OidcLoginError(Exception):
    """A sign-in that cannot complete; ``code`` is what the login page shows.

    ``no_provider``, ``unknown_provider``, ``expired_request``,
    ``browser_mismatch``, ``sign_in_failed``, ``token_rejected``, ``suspended``,
    ``email_in_use``, ``provider_unavailable``.
    """

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


@dataclass(frozen=True)
class LoginStart:
    authorization_url: str
    # The browser binding: set as a cookie, presented again on the callback.
    binding: str


@dataclass(frozen=True)
class SignedIn:
    session_secret: str
    user_id: str
    next_path: str
    expires_at: datetime


@dataclass(frozen=True)
class ActiveSession:
    """A session that authenticates the current request."""

    id: str
    user_id: str
    principal_id: str
    provider: str
    group_ids: tuple[str, ...]
    refresh_at: datetime


# One refresh at a time per session, in this process.
_refresh_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()


def _refresh_lock(session_id: str) -> asyncio.Lock:
    lock = _refresh_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _refresh_locks[session_id] = lock
    return lock


class OidcSignInService:
    def __init__(
        self,
        adapter: OidcSessionPersistencePort,
        identity: IdentityGateway,
        principals: PrincipalGateway,
        *,
        redirect_uri: str,
        session_max_age: timedelta,
        encrypt: Callable[[str], str],
        decrypt: Callable[[str], str | None],
        clock: Callable[[], datetime] = now_naive,
    ) -> None:
        self.adapter = adapter
        self.identity = identity
        self.principals = principals
        self.redirect_uri = redirect_uri
        self.session_max_age = session_max_age
        self._encrypt = encrypt
        self._decrypt = decrypt
        self._clock = clock

    # =========================================================================
    # Routing
    # =========================================================================

    async def route(self, email: str | None) -> str | None:
        """The provider a login goes to: the email's verified organization
        domain, else the default provider, else none."""
        if email and "@" in email:
            domain = email.rsplit("@", 1)[1].strip().lower()
            routed = await self.adapter.provider_for_domain(domain) if domain else None
            if routed:
                return routed
        _, default = await self.identity.providers()
        return default

    # =========================================================================
    # Sign-in
    # =========================================================================

    async def begin(
        self,
        *,
        provider: str | None = None,
        email: str | None = None,
        next_path: str | None = None,
    ) -> LoginStart:
        if provider is None:
            provider = await self.route(email)
        if provider is None:
            raise OidcLoginError("no_provider", "No identity provider is configured")
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        binding = secrets.token_urlsafe(32)
        try:
            url = await self.identity.authorization_url(
                provider,
                redirect_uri=self.redirect_uri,
                state=state,
                nonce=nonce,
                code_challenge=code_challenge(verifier),
                login_hint=email or None,
            )
        except UnknownProviderError as exc:
            raise OidcLoginError("unknown_provider", str(exc)) from exc
        except ProviderUnavailableError as exc:
            raise OidcLoginError("provider_unavailable", str(exc)) from exc
        now = self._clock()
        await self.adapter.purge_login_requests(now)
        await self.adapter.save_login_request(
            LoginRequest(
                state_hash=digest(state),
                provider=provider,
                nonce=nonce,
                code_verifier=verifier,
                binding_hash=digest(binding),
                next_path=safe_next_path(next_path),
                expires_at=now + timedelta(seconds=LOGIN_REQUEST_SECONDS),
            )
        )
        await self.adapter.commit()
        return LoginStart(authorization_url=url, binding=binding)

    async def complete(
        self,
        *,
        code: str,
        state: str,
        binding: str | None,
        user_agent: str | None = None,
    ) -> SignedIn:
        request = await self.adapter.take_login_request(digest(state)) if state else None
        await self.adapter.commit()  # a state is used once, whatever follows
        now = self._clock()
        if request is None or request.expires_at <= now:
            raise OidcLoginError("expired_request", "The sign-in expired: start again")
        if not binding or not hmac.compare_digest(digest(binding), request.binding_hash):
            raise OidcLoginError("browser_mismatch", "The sign-in was started in another browser")
        try:
            signed = await self.identity.exchange_code(
                request.provider,
                code=code,
                code_verifier=request.code_verifier,
                redirect_uri=self.redirect_uri,
                nonce=request.nonce,
            )
        except Exception as exc:  # noqa: BLE001 - mapped for the login page
            raise _login_error(exc) from exc
        user = await self._nexus_user(signed.user)
        await self.principals.admit(signed.user.principal_id)
        secret = secrets.token_urlsafe(32)
        expires_at = now + self.session_max_age
        await self.adapter.create_session(
            SessionRecord(
                id=digest(secret),
                user_id=user.id,
                principal_id=signed.user.principal_id,
                provider=request.provider,
                group_ids=signed.user.group_ids,
                refresh_token_enc=self._sealed(signed.tokens.refresh_token),
                id_token_enc=self._sealed(signed.tokens.id_token),
                refresh_at=self._refresh_at(signed, now),
                expires_at=expires_at,
                last_seen_at=now,
            ),
            user_agent=(user_agent or "")[:512] or None,
        )
        await self.adapter.commit()
        return SignedIn(
            session_secret=secret,
            user_id=user.id,
            next_path=request.next_path,
            expires_at=expires_at,
        )

    async def _nexus_user(self, signed_in: AuthenticatedUser) -> OidcUser:
        """The Nexus row of ``(issuer, sub)``: its id is the principal id."""
        token = signed_in.token
        verified_email = token.email.lower() if token.email and token.email_verified else None
        name = token.display_name or (token.email or "").split("@")[0] or "User"
        now = self._clock()
        existing = await self.adapter.user_by_principal(signed_in.principal_id)
        if existing is not None:
            email = None
            if verified_email and verified_email != existing.email:
                if not await self.adapter.email_taken(verified_email, except_user_id=existing.id):
                    email = verified_email
            if email or name != existing.name:
                await self.adapter.update_user(existing.id, email=email, name=name, now=now)
            return existing
        if verified_email and await self.adapter.email_taken(verified_email):
            # Never linked automatically: an admin links accounts (iam:LinkUser).
            raise OidcLoginError(
                "email_in_use",
                f"{verified_email} already belongs to another account",
            )
        return await self.adapter.create_user(
            user_id=signed_in.principal_id,
            email=verified_email or f"{signed_in.principal_id}@{PLACEHOLDER_EMAIL_DOMAIN}",
            name=name,
            principal_id=signed_in.principal_id,
            provider=token.provider,
            issuer=token.issuer,
            subject=token.subject,
            now=now,
        )

    # =========================================================================
    # Sessions
    # =========================================================================

    async def resolve(self, secret: str | None) -> ActiveSession | None:
        """The session a cookie names, refreshed at the provider when due;
        None when it is unknown, ended, expired, suspended or refused."""
        if not secret:
            return None
        record = await self.adapter.get_session(digest(secret))
        now = self._clock()
        if record is None or record.revoked_at is not None or record.expires_at <= now:
            return None
        if not await self.principals.is_active(record.principal_id):
            await self._end(record.id, now)
            return None
        if record.refresh_at <= now:
            refreshed = await self._refresh(record)
            if refreshed is None:
                return None
            record = refreshed
        elif record.last_seen_at is None or now - record.last_seen_at >= _LAST_SEEN_EVERY:
            await self.adapter.update_session(record.id, last_seen_at=now)
            await self.adapter.commit()
        return ActiveSession(
            id=record.id,
            user_id=record.user_id,
            principal_id=record.principal_id,
            provider=record.provider,
            group_ids=record.group_ids,
            refresh_at=record.refresh_at,
        )

    async def _refresh(self, record: SessionRecord) -> SessionRecord | None:
        async with _refresh_lock(record.id):
            current = await self.adapter.get_session(record.id)
            now = self._clock()
            if current is None or current.revoked_at is not None:
                return None
            if current.refresh_at > now:
                return current  # refreshed meanwhile
            refresh_token = (
                self._decrypt(current.refresh_token_enc) if current.refresh_token_enc else None
            )
            if not refresh_token:
                await self._end(current.id, now)
                return None
            try:
                signed = await self.identity.refresh(
                    current.provider,
                    refresh_token=refresh_token,
                    principal_id=current.principal_id,
                )
            except ProviderUnavailableError as exc:
                # Not vouched for: this request is not authenticated, and the
                # next one tries again.
                logger.warning(f"Session refresh at {current.provider} failed: {exc}")
                return None
            except (SignInError, TokenRejectedError, PrincipalSuspendedError) as exc:
                logger.info(f"Session ended: {current.provider} refused its refresh ({exc})")
                await self._end(current.id, now)
                return None
            refresh_at = self._refresh_at(signed, now)
            await self.adapter.update_session(
                current.id,
                group_ids=signed.user.group_ids,
                refresh_token_enc=self._sealed(signed.tokens.refresh_token),
                id_token_enc=self._sealed(signed.tokens.id_token),
                refresh_at=refresh_at,
                last_seen_at=now,
            )
            await self.adapter.commit()
            return SessionRecord(
                id=current.id,
                user_id=current.user_id,
                principal_id=current.principal_id,
                provider=current.provider,
                group_ids=signed.user.group_ids,
                refresh_token_enc=None,
                id_token_enc=None,
                refresh_at=refresh_at,
                expires_at=current.expires_at,
                last_seen_at=now,
            )

    async def logout(
        self, secret: str | None, *, post_logout_redirect_uri: str | None
    ) -> str | None:
        """End the session, revoke its refresh token at the provider, and return
        the provider's logout URL when it offers one."""
        if not secret:
            return None
        record = await self.adapter.get_session(digest(secret))
        if record is None or record.revoked_at is not None:
            return None
        await self._end(record.id, self._clock())
        refresh_token = (
            self._decrypt(record.refresh_token_enc) if record.refresh_token_enc else None
        )
        id_token = self._decrypt(record.id_token_enc) if record.id_token_enc else None
        try:
            if refresh_token:
                await self.identity.revoke(record.provider, refresh_token=refresh_token)
            return await self.identity.end_session_url(
                record.provider,
                id_token_hint=id_token,
                post_logout_redirect_uri=post_logout_redirect_uri,
            )
        except Exception as exc:  # noqa: BLE001 - the session is ended anyway
            logger.warning(f"Logout at {record.provider} failed: {exc}")
            return None

    # -- helpers ----------------------------------------------------------------

    async def _end(self, session_id: str, now: datetime) -> None:
        await self.adapter.revoke_session(session_id, now)
        await self.adapter.commit()

    def _sealed(self, value: str | None) -> str | None:
        return self._encrypt(value) if value else None

    @staticmethod
    def _refresh_at(signed: SignIn, now: datetime) -> datetime:
        at = datetime.fromtimestamp(signed.refresh_at, UTC).replace(tzinfo=None)
        # Never later than ten minutes, whatever the clocks say.
        return min(at, now + timedelta(seconds=600))


def _login_error(exc: Exception) -> OidcLoginError:
    if isinstance(exc, OidcLoginError):
        return exc
    if isinstance(exc, PrincipalSuspendedError):
        return OidcLoginError("suspended", "This account is suspended")
    if isinstance(exc, TokenRejectedError):
        return OidcLoginError("token_rejected", f"The provider's token was refused: {exc.reason}")
    if isinstance(exc, SignInError):
        return OidcLoginError("sign_in_failed", f"The provider refused the sign-in: {exc.error}")
    if isinstance(exc, ProviderUnavailableError):
        return OidcLoginError("provider_unavailable", "The identity provider cannot be reached")
    if isinstance(exc, UnknownProviderError):
        return OidcLoginError("unknown_provider", str(exc))
    logger.opt(exception=exc).error("OIDC sign-in failed")
    return OidcLoginError("sign_in_failed", "The sign-in failed")
