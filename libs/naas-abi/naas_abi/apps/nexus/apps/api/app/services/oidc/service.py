"""Nexus as an OIDC client of the engine's identity providers.

* **Sign-in** is authorization code with PKCE (S256). Nexus keeps the state,
  the nonce and the code verifier server-side, bound to the browser by a
  cookie; the engine builds the authorization URL and redeems the code with
  the provider's client secret, which Nexus never holds.
* **A user** is one Nexus row per ``(issuer, sub)``, whose id is its IAM
  principal id. Nothing is linked across providers: a verified email another
  account holds refuses the sign-in. The one exception is the move of the old
  built-in login's users: at the *built-in* provider, which proves an
  address by mailing it a code, the verified email of a row no provider signs in
  yet links the identity to that row and to its IAM user, which keeps its roles,
  groups and data (``_link_legacy_user``).
* **The session** is a random secret in an httpOnly cookie; Nexus stores its
  SHA-256, the user, and the provider's refresh token, encrypted. The provider
  vouches for the user again at least every ten minutes (``refresh_at``); a
  refresh it refuses ends the session, and an IAM suspension within seconds.
* **CSRF**: a request the cookie authenticates and that changes state carries
  ``X-CSRF-Token``, an HMAC of the session secret Nexus hands the web app
  (``csrf_token``). The browser keeps it in memory only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from email_validator import EmailNotValidError, validate_email
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.oidc.port import (
    IdentityGateway,
    LoginRequest,
    OidcSessionPersistencePort,
    OidcUser,
    PrincipalGateway,
    SessionRecord,
    UserConflictError,
    UserSuspendedError,
)
from naas_abi_core import logger
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
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
# A refresh is claimed by moving ``refresh_at`` this far ahead, in one
# compare-and-set: of the requests (and workers) that find a session due, one
# refreshes it, and the others carry on with the session as it stands. A claim
# whose holder died lapses by itself.
REFRESH_LEASE = timedelta(seconds=30)
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


def representable_email(email: str) -> bool:
    """Whether Nexus's schemas can carry the email (``EmailStr``): one with a
    reserved name (``.test``, ``.local``) would fail every request of its user."""
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        return False
    return True


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
        on_signed_in: Callable[[OidcUser, AuthenticatedUser], Awaitable[None]] | None = None,
    ) -> None:
        self.adapter = adapter
        self.identity = identity
        self.principals = principals
        self.redirect_uri = redirect_uri
        self.session_max_age = session_max_age
        self._encrypt = encrypt
        self._decrypt = decrypt
        self._clock = clock
        # What a first sign-in sets in motion beyond the session (invitations).
        self._on_signed_in = on_signed_in

    # =========================================================================
    # Routing
    # =========================================================================

    async def route(self, email: str | None) -> str | None:
        """The provider an email's login goes to: the one its verified
        organization domain names, else the engine's default provider (Nexus has
        no login of its own: whoever no domain maps signs in there), else none."""
        if not email or "@" not in email:
            return None
        domain = email.rsplit("@", 1)[1].strip().lower()
        mapped = await self.adapter.provider_for_domain(domain) if domain else None
        if mapped is not None:
            return mapped
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
        try:
            if provider is None:
                if email:
                    provider = await self.route(email)
                else:
                    # /login?provider= left out, no email: the default provider.
                    _, provider = await self.identity.providers()
            if provider is None:
                raise OidcLoginError("no_provider", "No identity provider is configured")
            state = secrets.token_urlsafe(32)
            nonce = secrets.token_urlsafe(32)
            verifier = secrets.token_urlsafe(64)
            binding = secrets.token_urlsafe(32)
            url = await self.identity.authorization_url(
                provider,
                redirect_uri=self.redirect_uri,
                state=state,
                nonce=nonce,
                code_challenge=code_challenge(verifier),
                login_hint=email or None,
            )
        except Exception as exc:  # noqa: BLE001 - mapped for the login page
            raise _login_error(exc) from exc
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
        user, principal_id = await self._nexus_user(signed.user, request.provider)
        authenticated = (
            signed.user
            if principal_id == signed.user.principal_id
            else replace(signed.user, principal_id=principal_id)
        )
        if self._on_signed_in is not None:
            try:
                await self._on_signed_in(user, authenticated)
            except Exception as exc:  # noqa: BLE001 - the session stands; the invitation stays pending
                logger.opt(exception=exc).error("Claiming the user's invitations failed")
        secret = secrets.token_urlsafe(32)
        expires_at = now + self.session_max_age
        await self.adapter.create_session(
            SessionRecord(
                id=digest(secret),
                user_id=user.id,
                principal_id=principal_id,
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

    async def _nexus_user(
        self, signed_in: AuthenticatedUser, provider: str
    ) -> tuple[OidcUser, str]:
        """The Nexus row of ``(issuer, sub)`` and the IAM principal that signs
        in: for a row a provider created, its id is the principal id."""
        token = signed_in.token
        verified_email = (
            token.email.lower()
            if token.email and token.email_verified and representable_email(token.email)
            else None
        )
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
            return existing, signed_in.principal_id
        if verified_email:
            legacy = await self.adapter.legacy_user_by_email(verified_email)
            if legacy is not None and await self._is_builtin(provider):
                return await self._link_legacy_user(legacy, signed_in, provider)
        if verified_email and await self.adapter.email_taken(verified_email):
            # Never linked automatically: an admin links accounts (iam:LinkUser).
            raise OidcLoginError(
                "email_in_use",
                f"{verified_email} already belongs to another account",
            )
        try:
            created = await self.adapter.create_user(
                user_id=signed_in.principal_id,
                email=verified_email or f"{signed_in.principal_id}@{PLACEHOLDER_EMAIL_DOMAIN}",
                name=name,
                principal_id=signed_in.principal_id,
                provider=token.provider,
                issuer=token.issuer,
                subject=token.subject,
                now=now,
            )
        except UserConflictError as exc:
            # Another sign-in of the same user won the insert, or another
            # account took the email meanwhile: never linked automatically.
            raise OidcLoginError(
                "email_in_use", f"{verified_email} already belongs to another account"
            ) from exc
        return created, signed_in.principal_id

    async def _is_builtin(self, provider: str) -> bool:
        """The built-in provider (``provisioning: builtin``) mails every sign-in
        a code, so its ``email_verified`` means the person reads that mailbox:
        the one provider whose verified email may take over a built-in login's
        account."""
        providers, _ = await self.identity.providers()
        return any(p.name == provider and p.provisioning == "builtin" for p in providers)

    async def _link_legacy_user(
        self, legacy: OidcUser, signed_in: AuthenticatedUser, provider: str
    ) -> tuple[OidcUser, str]:
        """The identity becomes one more identity of the legacy user's IAM
        principal (which keeps its roles, groups and keys), and of its row (which
        keeps its id, email and data)."""
        token = signed_in.token
        try:
            principal_id = await self.principals.link(
                legacy.id,
                provider=provider,
                issuer=token.issuer,
                subject=token.subject,
                email=legacy.email,
                display_name=token.display_name,
            )
            linked = await self.adapter.link_user(
                legacy.id,
                principal_id=principal_id,
                provider=provider,
                issuer=token.issuer,
                subject=token.subject,
                now=self._clock(),
            )
        except UserSuspendedError as exc:
            raise OidcLoginError("suspended", "This account is suspended") from exc
        except UserConflictError as exc:
            raise OidcLoginError(
                "email_in_use", f"{legacy.email} already belongs to another account"
            ) from exc
        logger.info(f"Linked the account {legacy.id} to {provider} identity {principal_id}")
        return linked, principal_id

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
        """Refresh a due session at its provider, once across requests and workers.

        The claim is a compare-and-set on ``refresh_at``: the request that moves
        it refreshes; the others use the session as it stands (it was vouched
        for within ten minutes) and never replay a refresh token a provider that
        rotates them has already spent.
        """
        now = self._clock()
        lease = now + REFRESH_LEASE
        claimed = await self.adapter.swap_refresh_at(
            record.id, expected=record.refresh_at, value=lease
        )
        await self.adapter.commit()
        if not claimed:
            return await self._refreshed_elsewhere(record.id)
        refresh_token = (
            self._decrypt(record.refresh_token_enc) if record.refresh_token_enc else None
        )
        if not refresh_token:
            await self._end(record.id, now)
            return None
        try:
            signed = await self.identity.refresh(
                record.provider,
                refresh_token=refresh_token,
                principal_id=record.principal_id,
            )
        except ProviderUnavailableError as exc:
            # Not vouched for: this request is not authenticated, and the next
            # one tries again.
            logger.warning(f"Session refresh at {record.provider} failed: {exc}")
            await self.adapter.swap_refresh_at(record.id, expected=lease, value=record.refresh_at)
            await self.adapter.commit()
            return None
        except (SignInError, TokenRejectedError, PrincipalSuspendedError) as exc:
            # A refresh another worker completed (after a lapsed claim) spent
            # the token: the session is alive.
            latest = await self.adapter.get_session(record.id)
            if (
                latest is not None
                and latest.revoked_at is None
                and latest.refresh_token_enc != record.refresh_token_enc
                and latest.refresh_at > now
            ):
                return latest
            logger.info(f"Session ended: {record.provider} refused its refresh ({exc})")
            await self._end(record.id, now)
            return None
        refresh_at = self._refresh_at(signed, now)
        # A refresh that sends no ID token (OIDC Core §12.2) keeps the groups and
        # the ID token the session already holds.
        renewed = signed.tokens.id_token is not None
        group_ids = signed.user.group_ids if renewed else record.group_ids
        await self.adapter.update_session(
            record.id,
            group_ids=group_ids,
            refresh_token_enc=self._sealed(signed.tokens.refresh_token),
            id_token_enc=self._sealed(signed.tokens.id_token),
            refresh_at=refresh_at,
            last_seen_at=now,
        )
        await self.adapter.commit()
        return SessionRecord(
            id=record.id,
            user_id=record.user_id,
            principal_id=record.principal_id,
            provider=record.provider,
            group_ids=group_ids,
            refresh_token_enc=None,
            id_token_enc=None,
            refresh_at=refresh_at,
            expires_at=record.expires_at,
            last_seen_at=now,
        )

    async def _refreshed_elsewhere(self, session_id: str) -> SessionRecord | None:
        """The session after another request claimed its refresh: usable while
        that refresh (or its lease) runs."""
        latest = await self.adapter.get_session(session_id)
        now = self._clock()
        if latest is None or latest.revoked_at is not None or latest.expires_at <= now:
            return None
        return latest if latest.refresh_at > now else None

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
    if isinstance(exc, PermissionDeniedError):
        logger.warning(f"IAM refused Nexus a sign-in: {exc}")
        return OidcLoginError("sign_in_failed", "Sign-in is not permitted for this provider")
    logger.opt(exception=exc).error("OIDC sign-in failed")
    return OidcLoginError("sign_in_failed", "The sign-in failed")
