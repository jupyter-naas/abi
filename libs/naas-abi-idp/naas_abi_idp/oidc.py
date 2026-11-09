"""The OpenID Connect provider, on authlib.

Authlib's ``AuthorizationServer`` runs the protocol (request validation, PKCE,
the grants, error responses); this module gives it the provider's storage and
tokens:

* authorization code with PKCE (S256 only, required of every client) and OpenID
  Connect, ID tokens signed ES256;
* refresh tokens, rotated on every use, a replayed one revoking its family;
* client credentials, for service accounts;
* revocation (RFC 7009); no introspection, access tokens live ten minutes;
* access tokens are ES256 JWTs (RFC 9068 shape) that ``userinfo`` verifies.

Nothing here is HTTP: ``web.py`` turns requests into ``HttpRequest`` and the
``(status, body, headers)`` it gets back into responses.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar
from urllib.parse import urlsplit

from authlib.common.encoding import to_native
from authlib.jose import JsonWebToken
from authlib.oauth2.rfc6749 import (
    AuthorizationServer,
    InvalidGrantError,
    InvalidRequestError,
    OAuth2Payload,
    OAuth2Request,
    grants,
)
from authlib.oauth2.rfc7009 import RevocationEndpoint
from authlib.oauth2.rfc7636 import CodeChallenge
from authlib.oidc.core import OpenIDCode, OpenIDToken, UserInfo
from authlib.oidc.core.util import create_half_hash

from naas_abi_idp.models import AuthorizationCode, Client, User
from naas_abi_idp.service import IdPService

log = logging.getLogger(__name__)

SCOPES = ("openid", "email", "profile", "groups", "offline_access")
CLAIMS = (
    "sub",
    "iss",
    "aud",
    "exp",
    "iat",
    "auth_time",
    "nonce",
    "amr",
    "email",
    "email_verified",
    "name",
    "preferred_username",
    "groups",
)
TOKEN_AUTH_METHODS = ["client_secret_basic", "client_secret_post", "none"]


@dataclass
class HttpRequest:
    """What the OIDC server needs of an HTTP request."""

    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    query: Mapping[str, str] = field(default_factory=dict)
    form: Mapping[str, str] = field(default_factory=dict)


@dataclass
class HttpResult:
    status: int
    body: bytes
    headers: list[tuple[str, str]]


class _Payload(OAuth2Payload):
    def __init__(self, data: Mapping[str, str]) -> None:
        self._data = dict(data)

    @property
    def data(self) -> dict[str, str]:
        return self._data

    @property
    def datalist(self) -> dict[str, list[str]]:
        return {k: [v] for k, v in self._data.items()}


class IdPOAuth2Request(OAuth2Request):
    """An authlib request over ``HttpRequest``. The query of an authorization
    request and the form of a token request are one payload each, never merged:
    a parameter in the wrong place is not read."""

    def __init__(self, request: HttpRequest, *, authorization: bool) -> None:
        super().__init__(request.method, request.url, headers=request.headers)
        self._request = request
        self.payload = _Payload(request.query if authorization else request.form)
        # Set by the web layer once the user is signed in.
        self.auth_time: int = int(time.time())
        self.amr: list[str] = []

    @property
    def args(self) -> Mapping[str, str]:
        return self._request.query

    @property
    def form(self) -> Mapping[str, str]:
        return self._request.form


class IdPAuthorizationServer(AuthorizationServer):
    def __init__(self, service: IdPService) -> None:
        # No server-wide scope list: each client's own scopes say what it may ask.
        super().__init__()
        self.service = service
        self.issuer = service.configuration.issuer
        self._jwt = JsonWebToken(["ES256"])
        self.register_token_generator("default", self._generate_token)
        self.register_grant(
            AuthorizationCodeGrant,
            [_Pkce(required=True), _OpenIDCode(self)],
        )
        self.register_grant(RefreshTokenGrant, [_OpenIDRefresh(self)])
        self.register_grant(ClientCredentialsGrant)
        self.register_endpoint(_Revocation)

    # -- authlib's hooks ------------------------------------------------------

    def query_client(self, client_id: str) -> Client | None:
        client = self.service.get_client(client_id)
        return None if client is None or client.disabled else client

    def save_token(self, token: dict[str, Any], request: IdPOAuth2Request) -> None:
        """Keep the refresh token the generator made (access tokens are stateless)."""
        refresh = token.get("refresh_token")
        if not refresh:
            return
        old = getattr(request, "refresh_token", None)
        if old is not None:  # a refresh: the new token continues the old one's family
            kept = self.service.rotate_refresh_token(old, refresh)
            if kept is None:
                raise InvalidGrantError("The refresh token was already used.")
            return
        code = request.authorization_code
        self.service.issue_refresh_token(
            request.client.client_id,
            request.user.id,
            token.get("scope", ""),
            token=refresh,
            code_id=code.id if code is not None else None,
        )

    def create_oauth2_request(self, request: Any) -> IdPOAuth2Request:
        if isinstance(request, IdPOAuth2Request):
            return request
        return IdPOAuth2Request(request, authorization=request.method == "GET")

    def handle_response(self, status: int, body: Any, headers: Any) -> HttpResult:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode()
        elif isinstance(body, str):
            data = body.encode()
        else:
            data = body or b""
        return HttpResult(int(status), data, [(k, v) for k, v in headers])

    def send_signal(self, name: str, *args: Any, **kwargs: Any) -> None:
        return None

    # -- tokens ---------------------------------------------------------------

    def _generate_token(
        self,
        grant_type: str,
        client: Client,
        user: User | None = None,
        scope: str | None = None,
        expires_in: int | None = None,
        include_refresh_token: bool = True,
    ) -> dict[str, Any]:
        config = self.service.configuration
        scope = client.get_allowed_scope(scope or "") if scope else ""
        ttl = min(
            expires_in or config.access_token_seconds, config.access_token_seconds
        )
        now = int(self.service.clock())
        key = self.service.keys.active()
        claims: dict[str, Any] = {
            "iss": self.issuer,
            "sub": user.id if user is not None else client.client_id,
            "aud": self.issuer,
            "client_id": client.client_id,
            "scope": scope,
            "jti": secrets.token_urlsafe(16),
            "iat": now,
            "nbf": now,
            "exp": now + ttl,
        }
        if user is not None and "groups" in scope.split():
            claims["groups"] = self.service.group_names(user)
        header = {"alg": "ES256", "typ": "at+jwt", "kid": key.kid}
        token: dict[str, Any] = {
            "token_type": "Bearer",
            "access_token": self._jwt.encode(header, claims, key.key).decode(),
            "expires_in": ttl,
            "scope": scope,
        }
        wants_refresh = (
            include_refresh_token
            and user is not None
            and "refresh_token" in client.grant_types
            and "offline_access" in scope.split()
        )
        if wants_refresh:
            # Kept by ``save_token`` once the grant has validated everything.
            token["refresh_token"] = secrets.token_urlsafe(32)
        return token

    def user_claims(self, user: User, scope: str) -> dict[str, Any]:
        scopes = scope.split()
        claims: dict[str, Any] = {"sub": user.id}
        if "email" in scopes:
            claims["email"] = user.email
            claims["email_verified"] = True  # an address the provider mailed a code to
        if "profile" in scopes:
            claims["name"] = user.name
            claims["preferred_username"] = user.email
        if "groups" in scopes:
            claims[self.service.configuration.groups_claim] = self.service.group_names(
                user
            )
        return claims

    def verify_access_token(self, token: str) -> dict[str, Any] | None:
        """The claims of an access token of this provider, or None."""
        try:
            claims = self._jwt.decode(token, _KeySet(self.service))
            claims.validate(now=int(self.service.clock()))
        except Exception:  # noqa: BLE001 - any failure is "not a valid token"
            return None
        if claims.get("iss") != self.issuer or claims.get("aud") != self.issuer:
            return None
        return dict(claims)


class _KeySet:
    """Authlib key resolver: the public key a token's ``kid`` names."""

    def __init__(self, service: IdPService) -> None:
        self._service = service

    def __call__(self, header: Mapping[str, Any], payload: Any) -> Any:
        from authlib.jose import JsonWebKey

        kid = header.get("kid")
        for jwk in self._service.keys.jwks()["keys"]:
            if jwk["kid"] == kid:
                return JsonWebKey.import_key(jwk)
        raise ValueError("unknown key")


# -- grants ----------------------------------------------------------------------


class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    TOKEN_ENDPOINT_AUTH_METHODS: ClassVar[list[str]] = TOKEN_AUTH_METHODS

    @property
    def service(self) -> IdPService:
        return self.server.service  # type: ignore[attr-defined,no-any-return]

    def generate_authorization_code(self) -> str:
        return secrets.token_urlsafe(32)

    def save_authorization_code(self, code: str, request: IdPOAuth2Request) -> None:
        data = request.payload.data
        service = self.service
        service.save_code(
            code,
            AuthorizationCode(
                id="",
                client_id=request.client.client_id,
                user_id=request.user.id,
                redirect_uri=request.payload.redirect_uri or "",
                scope=request.client.get_allowed_scope(request.payload.scope or ""),
                expires_at=service.clock()
                + service.configuration.authorization_code_seconds,
                auth_time=request.auth_time,
                code_challenge=data.get("code_challenge"),
                code_challenge_method=data.get("code_challenge_method"),
                nonce=data.get("nonce"),
                amr=list(request.amr),
            ),
        )

    def query_authorization_code(
        self, code: str, client: Client
    ) -> AuthorizationCode | None:
        # The code is spent here, whatever the rest of the request holds: a
        # wrong verifier or redirect URI burns it, and a second use revokes what
        # the first one got.
        record = self.service.consume_code(code)
        if record is None or record.client_id != client.client_id:
            return None
        return record

    def delete_authorization_code(self, authorization_code: AuthorizationCode) -> None:
        return None  # already spent by ``query_authorization_code``

    def authenticate_user(self, authorization_code: AuthorizationCode) -> User | None:
        try:
            user = self.service.get_user(authorization_code.user_id)
        except Exception:  # noqa: BLE001
            return None
        return None if user.disabled else user


class RefreshTokenGrant(grants.RefreshTokenGrant):
    TOKEN_ENDPOINT_AUTH_METHODS: ClassVar[list[str]] = TOKEN_AUTH_METHODS
    INCLUDE_NEW_REFRESH_TOKEN = True

    @property
    def service(self) -> IdPService:
        return self.server.service  # type: ignore[attr-defined,no-any-return]

    def authenticate_refresh_token(self, refresh_token: str) -> Any:
        return self.service.find_refresh_token(refresh_token)

    def authenticate_user(self, refresh_token: Any) -> User | None:
        try:
            user = self.service.get_user(refresh_token.user_id)
        except Exception:  # noqa: BLE001
            return None
        return None if user.disabled else user

    def revoke_old_credential(self, refresh_token: Any) -> None:
        return None  # rotated by ``save_token``, in one step with the new one


class ClientCredentialsGrant(grants.ClientCredentialsGrant):
    TOKEN_ENDPOINT_AUTH_METHODS: ClassVar[list[str]] = [
        "client_secret_basic",
        "client_secret_post",
    ]


class _Pkce(CodeChallenge):
    """PKCE is required of every client, public or not, and only S256 counts:
    the code of a request without it would be as good as a password."""

    SUPPORTED_CODE_CHALLENGE_METHOD: ClassVar[list[str]] = ["S256"]

    def validate_code_challenge(self, grant: Any, redirect_uri: str) -> None:
        data = grant.request.payload.data
        if (
            not data.get("code_challenge")
            or data.get("code_challenge_method") != "S256"
        ):
            raise InvalidRequestError(
                "PKCE is required: send code_challenge with code_challenge_method=S256",
                redirect_uri=redirect_uri,
            )
        super().validate_code_challenge(grant, redirect_uri)

    def validate_code_verifier(self, grant: Any, result: Any) -> None:
        if not grant.request.form.get("code_verifier"):
            raise InvalidRequestError("Missing 'code_verifier'")
        super().validate_code_verifier(grant, result)


class _OpenIDMixin:
    """Issues the ID token with the provider's clock (authlib's helper reads
    the system's), and shows the claims the scopes allow."""

    def __init__(self, server: IdPAuthorizationServer, **kwargs: Any) -> None:
        super().__init__(**kwargs)  # type: ignore[call-arg]
        self.server = server

    def process_token(self, grant: Any, response: Any) -> Any:
        _, token, _ = response
        scope = token.get("scope")
        if not scope or "openid" not in scope.split():
            return token  # a plain OAuth 2.0 grant
        request = grant.request
        service = self.server.service
        now = int(service.clock())
        key = service.keys.active()
        code = request.authorization_code
        payload: dict[str, Any] = {
            "iss": self.server.issuer,
            "aud": [request.client.get_client_id()],
            "iat": now,
            "exp": now + service.configuration.id_token_seconds,
            "auth_time": code.get_auth_time() if code is not None else now,
        }
        if code is not None:
            if code.get_nonce():
                payload["nonce"] = code.get_nonce()
            if code.get_amr():
                payload["amr"] = code.get_amr()
        half = create_half_hash(token["access_token"], "ES256")
        if half is not None:
            payload["at_hash"] = to_native(half)
        payload.update(self.generate_user_info(request.user, scope))
        header = {"alg": "ES256", "kid": key.kid}
        token["id_token"] = to_native(self.server._jwt.encode(header, payload, key.key))
        return token

    def generate_user_info(self, user: User, scope: str) -> UserInfo:
        return UserInfo(self.server.user_claims(user, scope))


class _OpenIDCode(_OpenIDMixin, OpenIDCode):
    def exists_nonce(self, nonce: str, request: Any) -> bool:
        return False  # a code is single use: there is no replay to catch


class _OpenIDRefresh(_OpenIDMixin, OpenIDToken):
    pass


class _Revocation(RevocationEndpoint):
    """RFC 7009 over the refresh tokens. Access tokens are stateless and live
    ten minutes: revoking one is accepted and changes nothing."""

    CLIENT_AUTH_METHODS: ClassVar[list[str]] = TOKEN_AUTH_METHODS

    def query_token(self, token_string: str, token_type_hint: str | None) -> Any:
        if token_type_hint == "access_token":
            return None
        return self.server.service.find_refresh_token(token_string)

    def revoke_token(self, token: Any, request: Any) -> None:
        self.server.service.revoke_refresh_token(token)


def allow_local_issuer(issuer: str) -> None:
    """Authlib refuses non-https request URLs unless told this is local
    testing. The configuration only accepts an http issuer on localhost, so
    that is the one case it is told."""
    parts = urlsplit(issuer)
    if parts.scheme == "http":
        os.environ.setdefault("AUTHLIB_INSECURE_TRANSPORT", "1")
