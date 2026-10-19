"""The provider's domain: users, groups, clients, sign-in codes, sessions, and the
tokens its OIDC endpoints keep.

Synchronous on purpose (authlib is): the HTTP layer calls it from worker
threads. Everything that must change together is one document, changed with
compare-and-set, so replicas of the module and parallel requests agree.
"""

from __future__ import annotations

import logging
import re
import secrets
import time
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from uuid import uuid4

from naas_abi_idp import pages
from naas_abi_idp.configuration import (
    GRANT_TYPES,
    ClientConfiguration,
    IdPConfiguration,
)
from naas_abi_idp.keys import KeyRing
from naas_abi_idp.limits import RateLimiter
from naas_abi_idp.models import (
    AUTH_REQUESTS,
    CHALLENGES,
    CLIENTS,
    CODES,
    COLLECTIONS,
    GROUPS,
    REFRESH_TOKENS,
    SESSIONS,
    USERS,
    AuthorizationCode,
    Client,
    Group,
    RefreshToken,
    User,
)
from naas_abi_idp.ports import (
    Conflict,
    DocumentStore,
    InvalidArgument,
    InvalidCode,
    Mail,
    Mailer,
    NotFound,
    SecretStore,
)
from naas_abi_idp.secrets_hash import (
    code_digest,
    equal,
    hash_secret,
    new_token,
    token_id,
    verify_secret,
)

log = logging.getLogger(__name__)

EMAIL = re.compile(r"^[^@\s<>\"',;]{1,64}@[^@\s<>\"',;]{1,255}\.[^@\s<>\"',;.]{2,63}$")
GROUP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:-]{0,63}$")
# A hash that nothing matches, checked when the user is unknown: the time a
# password sign-in takes does not tell whether the address is registered.
_DUMMY_HASH = hash_secret(secrets.token_urlsafe(16))
_ATTEMPTS = 8


def normalize_email(value: str) -> str:
    if value is not None and not isinstance(value, str):
        raise InvalidArgument("An email address is a string")
    email = (value or "").strip().lower()
    if len(email) > 254 or not EMAIL.match(email):
        raise InvalidArgument("Enter a valid email address")
    return email


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass(frozen=True)
class Session:
    id: str
    user_id: str
    auth_time: int
    amr: tuple[str, ...]
    expires_at: float


class IdPService:
    def __init__(
        self,
        store: DocumentStore,
        secrets_: SecretStore,
        mailer: Mailer,
        configuration: IdPConfiguration,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.store = store
        self.mailer = mailer
        self.configuration = configuration
        self.clock = clock
        self.keys = KeyRing(
            store, secrets_, rotation_days=configuration.key_rotation_days, clock=clock
        )
        self.limits = RateLimiter(store, configuration.rate_limit_window_seconds, clock)
        self._mail_pool = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="idp-mail"
        )
        self._mail_pending: set[Future[None]] = set()
        for spec in COLLECTIONS:
            store.ensure(spec)

    # =========================================================================
    # Users
    # =========================================================================

    def create_user(
        self,
        email: str,
        *,
        name: str | None = None,
        groups: Iterable[str] = (),
        password: str | None = None,
        disabled: bool = False,
    ) -> User:
        if name is not None and not isinstance(name, str):
            raise InvalidArgument("name is a string")
        email = normalize_email(email)
        group_ids = [self._group(g).id for g in dict.fromkeys(groups)]
        user = User(
            id=_id("u"),
            email=email,
            name=(name or _name_of(email)).strip()[:128],
            created_at=self.clock(),
            disabled=disabled,
            groups=group_ids,
            password_hash=hash_secret(_password(password)) if password else None,
        )
        try:
            created = self.store.create(USERS, user.id, user.to_doc())
        except Conflict:
            raise Conflict(f"{email} is already registered") from None
        assert created is not None
        return user

    def get_user(self, user_id: str) -> User:
        doc = self.store.get(USERS, user_id)
        if doc is None:
            raise NotFound(f"User {user_id} not found")
        return User.from_doc(doc.data)

    def find_user(self, email: str) -> User | None:
        try:
            email = normalize_email(email)
        except InvalidArgument:
            return None
        page = self.store.find(USERS, {"email": email}, limit=1)
        return User.from_doc(page.items[0].data) if page.items else None

    def list_users(
        self, *, limit: int = 100, after: str | None = None
    ) -> tuple[list[User], str | None]:
        page = self.store.find(USERS, limit=_limit(limit), after=after)
        return [User.from_doc(d.data) for d in page.items], page.cursor

    def update_user(
        self,
        user_id: str,
        *,
        name: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> User:
        for field, value in (("name", name), ("email", email), ("password", password)):
            if value is not None and not isinstance(value, str):
                raise InvalidArgument(f"{field} is a string")
        credentials_changed = False

        def change(user: User) -> User:
            nonlocal credentials_changed
            credentials_changed = False  # the closure may run again on a retry
            if name is not None:
                user.name = name.strip()[:128]
            if email is not None:
                new_email = normalize_email(email)
                credentials_changed |= new_email != user.email
                user.email = new_email
            if password is not None:
                user.password_hash = hash_secret(_password(password))
                credentials_changed = True
            return user

        updated = self._update_user(user_id, change)
        if credentials_changed:
            # A new password or email is how a compromised account is taken
            # back: what was signed in with the old ones must not stay signed in.
            self._end_user_sessions(user_id)
            self._revoke_user_refresh_tokens(user_id)
        return updated

    def set_disabled(self, user_id: str, disabled: bool) -> User:
        """Disabling ends the user's sessions at once; their refresh tokens stop
        working with the next use, and the ten-minute tokens run out."""
        user = self._update_user(user_id, lambda u: _set(u, "disabled", disabled))
        if disabled:
            self._end_user_sessions(user_id)
            self._revoke_user_refresh_tokens(user_id)
        return user

    def _update_user(self, user_id: str, change: Callable[[User], User]) -> User:
        for _ in range(_ATTEMPTS):
            doc = self.store.get(USERS, user_id)
            if doc is None:
                raise NotFound(f"User {user_id} not found")
            updated = change(User.from_doc(doc.data))
            try:
                written = self.store.replace(doc, USERS, updated.to_doc())
            except Conflict:
                raise Conflict("That email is already registered") from None
            if written is not None:
                return updated
        raise Conflict("The user is changing: try again")

    # =========================================================================
    # Groups
    # =========================================================================

    def create_group(self, name: str, description: str = "") -> Group:
        if not isinstance(name, str) or not isinstance(description, str):
            raise InvalidArgument("A group's name and description are strings")
        name = name.strip()
        if not GROUP_NAME.match(name):
            raise InvalidArgument(
                "A group name is 1 to 64 letters, digits, space . _ : -"
            )
        group = Group(_id("g"), name, self.clock(), description[:256])
        try:
            self.store.create(GROUPS, group.id, group.to_doc())
        except Conflict:
            raise Conflict(f"Group {name} exists") from None
        return group

    def list_groups(
        self, *, limit: int = 100, after: str | None = None
    ) -> tuple[list[Group], str | None]:
        page = self.store.find(GROUPS, limit=_limit(limit), after=after)
        return [Group.from_doc(d.data) for d in page.items], page.cursor

    def delete_group(self, group: str) -> None:
        found = self._group(group)
        after = None
        while True:
            page = self.store.find(USERS, limit=200, after=after)
            for doc in page.items:
                if found.id in doc.data["groups"]:
                    self._update_user(
                        doc.id,
                        lambda u: _set(
                            u, "groups", [g for g in u.groups if g != found.id]
                        ),
                    )
            after = page.cursor
            if after is None:
                break
        self.store.delete(GROUPS, found.id)

    def add_member(self, group: str, user_id: str) -> User:
        found = self._group(group)
        return self._update_user(
            user_id,
            lambda u: (
                u if found.id in u.groups else _set(u, "groups", [*u.groups, found.id])
            ),
        )

    def remove_member(self, group: str, user_id: str) -> User:
        found = self._group(group)
        return self._update_user(
            user_id, lambda u: _set(u, "groups", [g for g in u.groups if g != found.id])
        )

    def group_names(self, user: User) -> list[str]:
        """The names the groups claim lists: a name stays as long as its group."""
        names = []
        for group_id in user.groups:
            doc = self.store.get(GROUPS, group_id)
            if doc is not None:
                names.append(doc.data["name"])
        return sorted(names)

    def _group(self, ref: str) -> Group:
        """A group by id or by name."""
        doc = self.store.get(GROUPS, ref)
        if doc is None:
            page = self.store.find(GROUPS, {"name": ref}, limit=1)
            doc = page.items[0] if page.items else None
        if doc is None:
            raise NotFound(f"Group {ref} not found")
        return Group.from_doc(doc.data)

    # =========================================================================
    # Clients
    # =========================================================================

    def seed_clients(self, configured: Iterable[ClientConfiguration]) -> None:
        """Make the stored clients named by the configuration match it."""
        for wanted in configured:
            doc = self.store.get(CLIENTS, wanted.client_id)
            if doc is not None and doc.data.get("source") != "config":
                log.warning(
                    "Client %s was created through the admin API: the configuration "
                    "does not replace it",
                    wanted.client_id,
                )
                continue
            existing = Client.from_doc(doc.data) if doc is not None else None
            secret_hash = existing.secret_hash if existing else None
            if wanted.secret is None:
                secret_hash = None
            elif secret_hash is None or not verify_secret(wanted.secret, secret_hash):
                secret_hash = hash_secret(wanted.secret)
            client = Client(
                client_id=wanted.client_id,
                name=wanted.name or wanted.client_id,
                created_at=existing.created_at if existing else self.clock(),
                redirect_uris=list(wanted.redirect_uris),
                grant_types=list(wanted.grant_types),
                scopes=list(wanted.scopes),
                secret_hash=secret_hash,
                # What an admin disabled stays disabled across restarts.
                disabled=existing.disabled if existing else False,
                source="config",
            )
            if doc is None:
                self.store.create(CLIENTS, client.client_id, client.to_doc())
            elif doc.data != client.to_doc():
                self.store.replace(doc, CLIENTS, client.to_doc())

    def create_client(
        self,
        name: str,
        *,
        redirect_uris: Iterable[str] = (),
        grant_types: Iterable[str] = ("client_credentials",),
        scopes: Iterable[str] = (),
        confidential: bool = True,
    ) -> tuple[Client, str | None]:
        """A client for a service account (or a relying party). Its secret is
        returned once and never stored in clear."""
        if not isinstance(name, str):
            raise InvalidArgument("name is a string")
        grants = list(dict.fromkeys(grant_types))
        if not grants or set(grants) - set(GRANT_TYPES):
            raise InvalidArgument(f"grant_types are among {', '.join(GRANT_TYPES)}")
        uris = list(redirect_uris)
        if "authorization_code" in grants and not uris:
            raise InvalidArgument("authorization_code needs redirect_uris")
        if "client_credentials" in grants and not confidential:
            raise InvalidArgument("client_credentials needs a confidential client")
        for uri in uris:
            _check_redirect_uri(uri)
        secret = new_token(32) if confidential else None
        client = Client(
            client_id=f"c_{secrets.token_hex(10)}",
            name=(name or "").strip()[:128] or "client",
            created_at=self.clock(),
            redirect_uris=uris,
            grant_types=grants,
            scopes=list(dict.fromkeys(scopes)),
            secret_hash=hash_secret(secret) if secret else None,
        )
        self.store.create(CLIENTS, client.client_id, client.to_doc())
        return client, secret

    def get_client(self, client_id: str) -> Client | None:
        doc = self.store.get(CLIENTS, client_id) if client_id else None
        return Client.from_doc(doc.data) if doc is not None else None

    def list_clients(
        self, *, limit: int = 100, after: str | None = None
    ) -> tuple[list[Client], str | None]:
        page = self.store.find(CLIENTS, limit=_limit(limit), after=after)
        return [Client.from_doc(d.data) for d in page.items], page.cursor

    def set_client_disabled(self, client_id: str, disabled: bool) -> Client:
        for _ in range(_ATTEMPTS):
            doc = self.store.get(CLIENTS, client_id)
            if doc is None:
                raise NotFound(f"Client {client_id} not found")
            client = Client.from_doc(doc.data)
            client.disabled = disabled
            if self.store.replace(doc, CLIENTS, client.to_doc()) is not None:
                return client
        raise Conflict("The client is changing: try again")

    # =========================================================================
    # Sign-in codes (and passwords)
    # =========================================================================

    def request_code(self, email: str, client_ip: str | None) -> bool:
        """Email a sign-in code to a registered address (or register it, when
        sign-up is on). Whether anything was sent is for the caller to log, never
        to show.

        The answer does not tell registered addresses apart, in content or in
        time: the same work is done for every address (a code, the mail, a write
        to the store), and the mail itself leaves in the background
        (``background_mail``), so how long sending takes is not in the answer.

        Raises ``RateLimited`` past the budgets of the address and the client.
        A client address counts failures (an address that is not registered)
        against a tight budget and every request against a loose one, so one peer
        that many people share (a proxy not listed in ``FORWARDED_ALLOW_IPS``)
        is not locked out by their ordinary sign-ins.
        """
        email = normalize_email(email)
        config = self.configuration
        self.limits.consume(f"send:{email}", config.rate_limit_email_sends)
        if client_ip:
            self.limits.consume(f"ip-send:{client_ip}", config.rate_limit_ip_sends)
        user = self.find_user(email)
        if user is None and config.signup_enabled:
            try:
                user = self.create_user(email)
            except Conflict:
                user = self.find_user(email)
        code = f"{secrets.randbelow(10**config.code_length):0{config.code_length}d}"
        digest = code_digest(self.keys.code_key(), email, code)
        branding = config.branding_for(email)
        mail = Mail(
            to=email,
            subject=pages.code_subject(branding),
            text=pages.code_text(branding, code, config.code_ttl_seconds // 60),
            html=pages.code_html(branding, code, config.code_ttl_seconds // 60),
            from_email=config.from_email,
            from_name=config.from_name or branding.app_name,
        )
        if user is None or user.disabled:
            if client_ip:
                self.limits.consume(f"ip:{client_ip}", config.rate_limit_ip_attempts)
            # The store traffic of a real send: one read and one write.
            self.limits.consume(f"decoy:{email}", 10**9)
            return False
        self._add_code(email, digest)
        self._deliver(mail, email, digest)
        return True

    def _deliver(self, mail: Mail, email: str, digest: str) -> None:
        """Send the code's mail. A code nobody received guards nothing: when the
        mail fails, the code is dropped (raised in the caller's thread, or logged
        when the mail leaves in the background)."""

        def send() -> None:
            try:
                self.mailer.send(mail)
            except Exception:
                self._drop_code(email, digest)
                raise

        if not self.configuration.background_mail:
            send()
            return

        def background() -> None:
            try:
                send()
            except Exception:
                log.exception("Could not send a sign-in code")

        future = self._mail_pool.submit(background)
        self._mail_pending.add(future)
        future.add_done_callback(self._mail_pending.discard)

    def flush_mail(self, timeout: float = 10.0) -> None:
        """Wait for the mail still leaving (tests, and a clean stop)."""
        wait(list(self._mail_pending), timeout=timeout)

    def verify_code(self, email: str, code: str, client_ip: str | None) -> User:
        """The user a sign-in code opens. A wrong guess counts against the
        address (all its active codes at once), and the guess is counted before
        it is judged, so parallel guesses spend one budget."""
        config = self.configuration
        try:
            email = normalize_email(email)
        except InvalidArgument:
            raise InvalidCode() from None
        digits = "".join(ch for ch in (code or "") if ch.isdigit())
        left = self.limits.consume(f"verify:{email}", config.max_attempts)
        if client_ip:
            self.limits.consume(f"verify-ip:{client_ip}", config.rate_limit_ip_attempts)
        user = self.find_user(email)
        matched = (
            len(digits) == config.code_length
            and user is not None
            and not user.disabled
            and self._take_code(email, code_digest(self.keys.code_key(), email, digits))
        )
        if not matched or user is None:
            if left == 0:
                # The budget is spent: no code sent so far opens anything now.
                self.store.delete(CHALLENGES, _challenge_id(email))
            raise InvalidCode()
        self.limits.reset(f"verify:{email}")
        if client_ip:
            self.limits.refund(f"verify-ip:{client_ip}")
        self._touch(user)
        return user

    def verify_password(self, email: str, password: str, client_ip: str | None) -> User:
        config = self.configuration
        if not config.password_login_enabled:
            raise InvalidCode()
        try:
            email = normalize_email(email)
        except InvalidArgument:
            raise InvalidCode() from None
        self.limits.consume(f"verify:{email}", config.max_attempts)
        if client_ip:
            self.limits.consume(f"verify-ip:{client_ip}", config.rate_limit_ip_attempts)
        user = self.find_user(email)
        stored = user.password_hash if user and user.password_hash else _DUMMY_HASH
        ok = verify_secret(password or "", stored)
        if not ok or user is None or user.disabled or user.password_hash is None:
            raise InvalidCode()
        self.limits.reset(f"verify:{email}")
        if client_ip:
            self.limits.refund(f"verify-ip:{client_ip}")
        self._touch(user)
        return user

    def _add_code(self, email: str, digest: str) -> None:
        id, now = _challenge_id(email), self.clock()
        config = self.configuration
        for _ in range(_ATTEMPTS):
            doc = self.store.get(CHALLENGES, id)
            codes = [c for c in (doc.data["codes"] if doc else []) if c["exp"] > now]
            codes = (
                codes[-(config.max_active_codes - 1) :]
                if config.max_active_codes > 1
                else []
            )
            codes.append({"h": digest, "exp": now + config.code_ttl_seconds})
            data = {"email": email, "codes": codes}
            written = (
                self.store.replace(doc, CHALLENGES, data)
                if doc is not None
                else self.store.create(CHALLENGES, id, data)
            )
            if written is not None:
                return
        raise Conflict("Sign-in is busy: try again")

    def _drop_code(self, email: str, digest: str) -> None:
        id = _challenge_id(email)
        for _ in range(_ATTEMPTS):
            doc = self.store.get(CHALLENGES, id)
            if doc is None:
                return
            codes = [c for c in doc.data["codes"] if c["h"] != digest]
            if self.store.replace(doc, CHALLENGES, {**doc.data, "codes": codes}):
                return

    def _take_code(self, email: str, digest: str) -> bool:
        """Spend the active code that matches: the whole challenge goes, so a
        code opens once and every older one with it."""
        id, now = _challenge_id(email), self.clock()
        doc = self.store.get(CHALLENGES, id)
        if doc is None:
            return False
        matched = False
        for entry in doc.data["codes"]:  # no early exit: the time says nothing
            if equal(entry["h"], digest) and entry["exp"] > now:
                matched = True
        return matched and self.store.delete(CHALLENGES, id, version=doc.version)

    def _touch(self, user: User) -> None:
        try:
            self._update_user(user.id, lambda u: _set(u, "last_login_at", self.clock()))
        except Exception:  # a login time is not worth a failed sign-in
            log.debug("Could not record the login time of %s", user.id, exc_info=True)

    # =========================================================================
    # Browser sessions (the provider's own single sign-on)
    # =========================================================================

    def create_session(self, user: User, amr: Iterable[str]) -> tuple[str, Session]:
        cookie = new_token(32)
        now = self.clock()
        session = Session(
            id=token_id(cookie),
            user_id=user.id,
            auth_time=int(now),
            amr=tuple(amr),
            expires_at=now + self.configuration.session_hours * 3600,
        )
        self.store.create(
            SESSIONS,
            session.id,
            {
                "user_id": user.id,
                "auth_time": session.auth_time,
                "amr": list(session.amr),
                "expires_at": session.expires_at,
            },
        )
        return cookie, session

    def get_session(self, cookie: str | None) -> tuple[Session, User] | None:
        if not cookie:
            return None
        doc = self.store.get(SESSIONS, token_id(cookie))
        if doc is None:
            return None
        if doc.data["expires_at"] <= self.clock():
            self.store.delete(SESSIONS, doc.id)
            return None
        try:
            user = self.get_user(doc.data["user_id"])
        except NotFound:
            return None
        if user.disabled:
            return None
        return (
            Session(
                doc.id,
                user.id,
                int(doc.data["auth_time"]),
                tuple(doc.data["amr"]),
                doc.data["expires_at"],
            ),
            user,
        )

    def end_session(self, cookie: str | None) -> None:
        if cookie:
            self.store.delete(SESSIONS, token_id(cookie))

    def _end_user_sessions(self, user_id: str) -> None:
        after = None
        while True:
            page = self.store.find(
                SESSIONS, {"user_id": user_id}, limit=200, after=after
            )
            for doc in page.items:
                self.store.delete(SESSIONS, doc.id)
            after = page.cursor
            if after is None:
                return

    # =========================================================================
    # Authorization requests, codes and refresh tokens
    # =========================================================================

    def save_auth_request(self, params: dict[str, str]) -> tuple[str, str]:
        """A request waiting for the user to sign in: ``(id, csrf token)``."""
        rid, csrf = new_token(32), new_token(24)
        self.store.create(
            AUTH_REQUESTS,
            token_id(rid),
            {
                "params": params,
                "csrf": csrf,
                "expires_at": self.clock()
                + self.configuration.authorization_request_seconds,
            },
        )
        return rid, csrf

    def get_auth_request(self, rid: str | None) -> tuple[dict[str, str], str] | None:
        if not rid:
            return None
        doc = self.store.get(AUTH_REQUESTS, token_id(rid))
        if doc is None:
            return None
        if doc.data["expires_at"] <= self.clock():
            self.store.delete(AUTH_REQUESTS, doc.id)
            return None
        return dict(doc.data["params"]), doc.data["csrf"]

    def drop_auth_request(self, rid: str | None) -> None:
        if rid:
            self.store.delete(AUTH_REQUESTS, token_id(rid))

    def save_code(self, code: str, record: AuthorizationCode) -> None:
        record.id = token_id(code)
        self.store.create(CODES, record.id, record.to_doc())

    def consume_code(self, code: str) -> AuthorizationCode | None:
        """The authorization code, once. A second use finds it spent: everything
        issued from it is revoked (RFC 6749 §4.1.2) and nothing is returned."""
        id = token_id(code)
        for _ in range(_ATTEMPTS):
            doc = self.store.get(CODES, id)
            if doc is None:
                return None
            record = AuthorizationCode.from_doc(doc.data)
            if record.used:
                self._revoke_code_tokens(id)
                return None
            if record.is_expired(self.clock()):
                return None
            record.used = True
            if self.store.replace(doc, CODES, record.to_doc()) is not None:
                record.used = False
                return record
        return None

    def issue_refresh_token(
        self,
        client_id: str,
        user_id: str,
        scope: str,
        *,
        token: str | None = None,
        family: str | None = None,
        code_id: str | None = None,
    ) -> str:
        """Keep a refresh token (a new one unless ``token`` is given: the OIDC
        server generates the string, then asks to keep it)."""
        token = token or new_token(32)
        now = self.clock()
        record = RefreshToken(
            id=token_id(token),
            family=family or _id("f"),
            client_id=client_id,
            user_id=user_id,
            scope=scope,
            created_at=now,
            expires_at=now + self.configuration.refresh_token_days * 86400,
            code_id=code_id,
        )
        self.store.create(REFRESH_TOKENS, record.id, record.to_doc())
        return token

    def find_refresh_token(self, token: str) -> RefreshToken | None:
        """A live refresh token. A rotated one that comes back means a copy was
        stolen: its whole family is revoked, and nothing is returned."""
        doc = self.store.get(REFRESH_TOKENS, token_id(token))
        if doc is None:
            return None
        record = RefreshToken.from_doc(doc.data)
        if record.rotated:
            self._revoke_family(record.family)
            return None
        if record.revoked or record.expires_at <= self.clock():
            return None
        return record

    def rotate_refresh_token(
        self, old: RefreshToken, token: str | None = None
    ) -> str | None:
        """Retire ``old`` and keep its successor, or None when someone else
        got there first (two uses of one token: a replay)."""
        for _ in range(_ATTEMPTS):
            doc = self.store.get(REFRESH_TOKENS, old.id)
            if doc is None:
                return None
            current = RefreshToken.from_doc(doc.data)
            if current.rotated or current.revoked:
                self._revoke_family(current.family)
                return None
            current.rotated = True
            if self.store.replace(doc, REFRESH_TOKENS, current.to_doc()) is not None:
                return self.issue_refresh_token(
                    old.client_id,
                    old.user_id,
                    old.scope,
                    token=token,
                    family=old.family,
                    code_id=old.code_id,
                )
        return None

    def revoke_refresh_token(self, record: RefreshToken) -> None:
        """RFC 7009: the token and the grant it belongs to stop working."""
        self._revoke_family(record.family)

    def _revoke_family(self, family: str) -> None:
        self._revoke_where({"family": family})

    def _revoke_code_tokens(self, code_id: str) -> None:
        self._revoke_where({"code_id": code_id})

    def _revoke_user_refresh_tokens(self, user_id: str) -> None:
        self._revoke_where({"user_id": user_id})

    def _revoke_where(self, where: dict[str, str]) -> None:
        after = None
        while True:
            page = self.store.find(REFRESH_TOKENS, where, limit=200, after=after)
            for doc in page.items:
                for _ in range(_ATTEMPTS):
                    current = self.store.get(REFRESH_TOKENS, doc.id)
                    if current is None or current.data["revoked"]:
                        break
                    if self.store.replace(
                        current, REFRESH_TOKENS, {**current.data, "revoked": True}
                    ):
                        break
            after = page.cursor
            if after is None:
                return

    # =========================================================================
    # Housekeeping
    # =========================================================================

    def purge_expired(self) -> int:
        """Delete what has expired: challenges, requests, codes, sessions,
        refresh tokens, counters. Returns how many."""
        now, removed = self.clock(), self.limits.purge()
        for collection, expired in (
            (CHALLENGES, lambda d: all(c["exp"] <= now for c in d["codes"])),
            (AUTH_REQUESTS, lambda d: d["expires_at"] <= now),
            (CODES, lambda d: d["expires_at"] + 3600 <= now),  # spent ones stay a while
            (SESSIONS, lambda d: d["expires_at"] <= now),
            (REFRESH_TOKENS, lambda d: d["expires_at"] <= now),
        ):
            after = None
            while True:
                page = self.store.find(collection, limit=200, after=after)
                for doc in page.items:
                    if expired(doc.data):
                        removed += self.store.delete(
                            collection, doc.id, version=doc.version
                        )
                after = page.cursor
                if after is None:
                    break
        return removed


def _challenge_id(email: str) -> str:
    import hashlib

    return hashlib.sha256(email.encode()).hexdigest()


def _name_of(email: str) -> str:
    local = email.split("@", 1)[0]
    return re.sub(r"[._+-]+", " ", local).strip().title() or email


def _password(value: str | None) -> str:
    if not isinstance(value, str) or len(value) < 10 or len(value) > 256:
        raise InvalidArgument("A password is 10 to 256 characters")
    return value


def _limit(value: int) -> int:
    return max(1, min(int(value), 500))


def _set(obj: User, field: str, value: object) -> User:
    setattr(obj, field, value)
    return obj


def _check_redirect_uri(uri: str) -> None:
    from urllib.parse import urlsplit

    parts = urlsplit(uri)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if parts.scheme not in ("https", "http") or not parts.netloc or parts.fragment:
        raise InvalidArgument(f"Invalid redirect URI {uri!r}")
    if parts.scheme == "http" and not local:
        raise InvalidArgument("A redirect URI is https (http on localhost only)")
