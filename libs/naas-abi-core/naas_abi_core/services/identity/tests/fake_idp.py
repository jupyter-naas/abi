"""A small OIDC provider over real HTTP, for tests.

It serves discovery, a JWKS, authorization code with PKCE (S256), refresh
tokens, revocation and end-session on ``http://127.0.0.1:<port>``, with RS256
and ES256 keys it can rotate. A sign-in needs no page: ``sign_in`` approves a
pending authorization request for a user and returns the redirect the
browser would follow.

It implements ``IdentityProviderHarness``, so the generic identity suite
(``identity_contract.py``) runs against it on every test run, and against a
real provider (Zitadel, the built-in IdP) when one is available.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Self
from urllib.parse import parse_qs, unquote_plus, urlencode, urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from naas_abi_core.services.identity.tests.identity_contract import TestUser


@dataclass
class _Key:
    kid: str
    algorithm: str
    private: Any

    def public_jwk(self) -> dict[str, Any]:
        algorithm = jwt.get_algorithm_by_name(self.algorithm)
        jwk = json.loads(algorithm.to_jwk(self.private.public_key()))
        jwk.update(kid=self.kid, alg=self.algorithm, use="sig")
        return jwk


@dataclass
class _Client:
    client_id: str
    secret: str | None
    redirect_uris: tuple[str, ...]


@dataclass
class _User:
    subject: str
    email: str
    email_verified: bool = True
    name: str | None = None
    groups: list[str] = field(default_factory=list)


@dataclass
class _Pending:
    client_id: str
    redirect_uri: str
    state: str | None
    nonce: str | None
    challenge: str
    scope: str


@dataclass
class _Code:
    pending: _Pending
    subject: str
    expires_at: float


def _new_key(algorithm: str) -> _Key:
    if algorithm == "ES256":
        private: Any = ec.generate_private_key(ec.SECP256R1())
    else:
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return _Key(f"k-{secrets.token_hex(4)}", algorithm, private)


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class FakeIdP:
    """An OIDC provider in this process. Use as a context manager."""

    provider_name = "fake"
    groups_claim: str | None = "groups"
    scopes: tuple[str, ...] = ("openid", "email", "profile", "offline_access")

    def __init__(
        self,
        *,
        token_ttl_seconds: int = 600,
        jwks_max_age: int = 300,
        redirect_uri: str = "http://127.0.0.1:9/callback",
    ) -> None:
        self.token_ttl_seconds = token_ttl_seconds
        self.jwks_max_age = jwks_max_age
        # The JWKS's Cache-Control, when a test wants something else than max-age.
        self.jwks_cache_control: str | None = None
        # OIDC Core §12.2: a refresh response may leave the ID token out.
        self.refresh_returns_id_token = True
        self.redirect_uri = redirect_uri
        self._lock = threading.Lock()
        self._keys: list[_Key] = [_new_key("RS256")]
        self._active = self._keys[0]
        self._clients: dict[str, _Client] = {}
        self._users: dict[str, _User] = {}
        self._pending: dict[str, _Pending] = {}
        self._codes: dict[str, _Code] = {}
        self._refresh: dict[str, tuple[str, str]] = {}  # token -> (client, subject)
        self.revoked: list[str] = []
        self.token_requests: list[dict[str, str]] = []
        self.jwks_reads = 0
        self.client_id, self.client_secret = self.add_client(redirect_uri)
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(self))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    # -- lifecycle --------------------------------------------------------------

    @property
    def issuer(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> Self:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- IdentityProviderHarness ------------------------------------------------

    def create_user(self, email: str, *, groups: Sequence[str] = ()) -> TestUser:
        subject = f"sub-{secrets.token_hex(6)}"
        with self._lock:
            self._users[subject] = _User(
                subject, email, name=email.split("@")[0].title(), groups=list(groups)
            )
        return TestUser(subject=subject, email=email, login=email)

    def set_groups(self, user: TestUser, groups: Sequence[str]) -> None:
        with self._lock:
            self._users[user.subject].groups = list(groups)

    def sign_in(self, authorization_url: str, user: TestUser) -> str:
        response = httpx.get(authorization_url, follow_redirects=False)
        if response.status_code != 302:
            raise AssertionError(
                f"authorize answered {response.status_code}: {response.text}"
            )
        location = response.headers["location"]
        request_id = parse_qs(urlsplit(location).query)["request"][0]
        approved = httpx.post(
            f"{self.issuer}/login",
            data={"request": request_id, "subject": user.subject},
            follow_redirects=False,
        )
        if approved.status_code != 302:
            raise AssertionError(
                f"login answered {approved.status_code}: {approved.text}"
            )
        return approved.headers["location"]

    def rotate_signing_key(self) -> None:
        """A new key, of the other algorithm, published and signing from now."""
        with self._lock:
            algorithm = "ES256" if self._active.algorithm == "RS256" else "RS256"
            key = _new_key(algorithm)
            self._keys.append(key)
            self._active = key

    def retire_old_keys(self) -> None:
        with self._lock:
            self._keys = [self._active]

    def other_client(self) -> tuple[str, str | None]:
        return self.add_client(self.redirect_uri)

    # -- test controls ----------------------------------------------------------

    def add_client(
        self,
        redirect_uri: str,
        *,
        confidential: bool = True,
        secret: str | None = None,
    ) -> tuple[str, str | None]:
        client_id = f"client-{secrets.token_hex(4)}"
        if secret is None and confidential:
            secret = secrets.token_urlsafe(24)
        with self._lock:
            self._clients[client_id] = _Client(client_id, secret, (redirect_uri,))
        return client_id, secret

    def allow_redirect_uri(
        self, redirect_uri: str, client_id: str | None = None
    ) -> None:
        with self._lock:
            client = self._clients[client_id or self.client_id]
            client.redirect_uris = (*client.redirect_uris, redirect_uri)

    def issue_id_token(
        self,
        subject: str,
        *,
        audience: str | list[str] | None = None,
        issued_at: float | None = None,
        lifetime: int | None = None,
        nonce: str | None = None,
        **claims: Any,
    ) -> str:
        """An ID token for ``subject``, signed with the active key."""
        now = int(issued_at if issued_at is not None else time.time())
        user = self._users.get(subject)
        body: dict[str, Any] = {
            "iss": self.issuer,
            "sub": subject,
            "aud": audience if audience is not None else self.client_id,
            "iat": now,
            "exp": now + (lifetime if lifetime is not None else self.token_ttl_seconds),
        }
        if isinstance(body["aud"], str):
            body["azp"] = body["aud"]
        if user is not None:
            body.update(
                email=user.email, email_verified=user.email_verified, name=user.name
            )
            if self.groups_claim:
                body[self.groups_claim] = list(user.groups)
        if nonce is not None:
            body["nonce"] = nonce
        body.update(claims)
        with self._lock:
            key = self._active
        return jwt.encode(
            body, key.private, algorithm=key.algorithm, headers={"kid": key.kid}
        )

    # -- endpoint logic ---------------------------------------------------------

    def _discovery(self) -> dict[str, Any]:
        issuer = self.issuer
        return {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/authorize",
            "token_endpoint": f"{issuer}/token",
            "jwks_uri": f"{issuer}/jwks",
            "userinfo_endpoint": f"{issuer}/userinfo",
            "revocation_endpoint": f"{issuer}/revoke",
            "end_session_endpoint": f"{issuer}/end_session",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256", "ES256"],
            "code_challenge_methods_supported": ["S256"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
        }

    def _jwks(self) -> dict[str, Any]:
        with self._lock:
            self.jwks_reads += 1
            return {"keys": [k.public_jwk() for k in self._keys]}

    def _authorize(self, query: Mapping[str, str]) -> tuple[int, dict[str, str], str]:
        client = self._clients.get(query.get("client_id", ""))
        redirect_uri = query.get("redirect_uri", "")
        if client is None or redirect_uri not in client.redirect_uris:
            return 400, {}, "unknown client or redirect_uri"
        if query.get("response_type") != "code":
            return 400, {}, "response_type must be code"
        if query.get("code_challenge_method") != "S256" or not query.get(
            "code_challenge"
        ):
            return 400, {}, "PKCE with S256 is required"
        request_id = secrets.token_urlsafe(12)
        with self._lock:
            self._pending[request_id] = _Pending(
                client.client_id,
                redirect_uri,
                query.get("state"),
                query.get("nonce"),
                query["code_challenge"],
                query.get("scope", "openid"),
            )
        return 302, {"Location": f"{self.issuer}/login?request={request_id}"}, ""

    def _login(self, form: Mapping[str, str]) -> tuple[int, dict[str, str], str]:
        with self._lock:
            pending = self._pending.pop(form.get("request", ""), None)
            known = form.get("subject", "") in self._users
        if pending is None or not known:
            return 400, {}, "unknown request or user"
        code = secrets.token_urlsafe(24)
        with self._lock:
            self._codes[code] = _Code(pending, form["subject"], time.time() + 60)
        params = {"code": code}
        if pending.state is not None:
            params["state"] = pending.state
        return 302, {"Location": f"{pending.redirect_uri}?{urlencode(params)}"}, ""

    def _client_of(
        self, form: Mapping[str, str], authorization: str | None
    ) -> _Client | None:
        client_id, secret = form.get("client_id"), form.get("client_secret")
        if authorization and authorization.lower().startswith("basic "):
            decoded = base64.b64decode(authorization[6:]).decode()
            client_id, _, secret = decoded.partition(":")
            # RFC 6749 §2.3.1: form-urlencoded before the Basic encoding.
            client_id, secret = unquote_plus(client_id), unquote_plus(secret)
        client = self._clients.get(client_id or "")
        if client is None:
            return None
        if client.secret is not None and not secrets.compare_digest(
            client.secret, secret or ""
        ):
            return None
        return client

    def _token(
        self, form: Mapping[str, str], authorization: str | None
    ) -> tuple[int, dict[str, Any]]:
        self.token_requests.append(dict(form))
        client = self._client_of(form, authorization)
        if client is None:
            return 401, {"error": "invalid_client"}
        grant = form.get("grant_type")
        if grant == "authorization_code":
            with self._lock:
                code = self._codes.pop(form.get("code", ""), None)
            if (
                code is None
                or code.expires_at < time.time()
                or code.pending.client_id != client.client_id
                or code.pending.redirect_uri != form.get("redirect_uri")
            ):
                return 400, {"error": "invalid_grant"}
            if _s256(form.get("code_verifier", "")) != code.pending.challenge:
                return 400, {"error": "invalid_grant", "error_description": "PKCE"}
            return 200, self._tokens(client, code.subject, nonce=code.pending.nonce)
        if grant == "refresh_token":
            with self._lock:
                held = self._refresh.pop(form.get("refresh_token", ""), None)
            if held is None or held[0] != client.client_id:
                return 400, {"error": "invalid_grant"}
            tokens = self._tokens(client, held[1], nonce=None)
            if not self.refresh_returns_id_token:
                del tokens["id_token"]
            return 200, tokens
        return 400, {"error": "unsupported_grant_type"}

    def _tokens(
        self, client: _Client, subject: str, *, nonce: str | None
    ) -> dict[str, Any]:
        refresh = secrets.token_urlsafe(32)
        with self._lock:
            self._refresh[refresh] = (client.client_id, subject)
        return {
            "access_token": secrets.token_urlsafe(32),
            "token_type": "Bearer",
            "expires_in": self.token_ttl_seconds,
            "refresh_token": refresh,
            "id_token": self.issue_id_token(
                subject, audience=client.client_id, nonce=nonce
            ),
        }

    def _revoke(self, form: Mapping[str, str], authorization: str | None) -> int:
        if self._client_of(form, authorization) is None:
            return 401
        token = form.get("token", "")
        with self._lock:
            self._refresh.pop(token, None)
            self.revoked.append(token)
        return 200


def _handler(idp: FakeIdP) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def _send(
            self,
            status: int,
            body: Any = None,
            headers: Mapping[str, str] | None = None,
        ) -> None:
            payload = (
                json.dumps(body).encode()
                if isinstance(body, (dict, list))
                else str(body or "").encode()
            )
            self.send_response(status)
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            if isinstance(body, (dict, list)):
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _form(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode()
            return {k: v[0] for k, v in parse_qs(raw).items()}

        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            query = {k: v[0] for k, v in parse_qs(parts.query).items()}
            if parts.path == "/.well-known/openid-configuration":
                self._send(200, idp._discovery(), {"Cache-Control": "max-age=60"})
            elif parts.path == "/jwks":
                self._send(
                    200,
                    idp._jwks(),
                    {
                        "Cache-Control": idp.jwks_cache_control
                        or f"max-age={idp.jwks_max_age}"
                    },
                )
            elif parts.path == "/authorize":
                status, headers, text = idp._authorize(query)
                self._send(status, text, headers)
            elif parts.path == "/end_session":
                target = query.get("post_logout_redirect_uri")
                self._send(
                    302 if target else 200, "", {"Location": target} if target else {}
                )
            else:
                self._send(404, "not found")

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            form = self._form()
            authorization = self.headers.get("Authorization")
            if path == "/token":
                status, body = idp._token(form, authorization)
                self._send(status, body, {"Cache-Control": "no-store"})
            elif path == "/login":
                status, headers, text = idp._login(form)
                self._send(status, text, headers)
            elif path == "/revoke":
                self._send(idp._revoke(form, authorization), "")
            else:
                self._send(404, "not found")

    return Handler
