"""Engine tokens for tests: one signing key, its verifier and token sources.

Tests that served or called NATS endpoints with a shared HS256 secret use
``TEST_TOKENS`` instead: ``TEST_TOKENS.verifier`` for primaries,
``TEST_TOKENS.source("api")`` for clients, ``TEST_TOKENS.token("api")`` for a
raw ``Nats-Auth-Token`` header. A token's subject is the name it is issued
for (``"api"``), so the caller a primary sees is ``service_account("api")``
as before IAM assigned ``sa_`` ids. ``TestTokens()`` is another issuer: its
tokens fail ``TEST_TOKENS.verifier``.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

from naas_abi_core.engine.nats_auth import (
    AGENT_AUDIENCE,
    KERNEL_AUDIENCES,
    MAX_TOKEN_SECONDS,
    NATS_AUDIENCE,
    IssuedToken,
    JWKSVerifier,
    RenewingTokenSource,
    SigningKey,
    TokenClaims,
    new_token_id,
    sign_token,
)


class TestTokens:
    __test__ = False  # not a pytest class

    def __init__(self, issuer: str = "urn:abi:engine:test") -> None:
        self.issuer = issuer
        self.key = SigningKey.generate()
        self.verifier = self.verifier_for()

    def jwks(self) -> dict:
        return {"issuer": self.issuer, "keys": [self.key.public_jwk()]}

    def verifier_for(self, audiences: Iterable[str] = KERNEL_AUDIENCES) -> JWKSVerifier:
        """By default what every kernel endpoint accepts: a service's own token
        and a delegation for a user."""
        return JWKSVerifier(self.jwks, audiences=audiences)

    def issue(
        self,
        name: str = "api",
        *,
        subject: str | None = None,
        kind: str = "service_account",
        audience: str = NATS_AUDIENCE,
        issued_at: int | None = None,
        ttl: int = MAX_TOKEN_SECONDS,
        actor: str | None = None,
        actor_name: str | None = None,
        groups: tuple[str, ...] = (),
    ) -> IssuedToken:
        now = int(time.time()) if issued_at is None else issued_at
        claims = TokenClaims(
            issuer=self.issuer,
            subject=subject or name,
            audience=audience,
            kind=kind,
            token_id=new_token_id(),
            issued_at=now,
            expires_at=now + ttl,
            name=name if kind == "service_account" else None,
            actor=actor,
            actor_name=actor_name,
            groups=groups,
        )
        return IssuedToken(
            sign_token(self.key, claims), float(now + ttl), claims.subject, name
        )

    def token(self, name: str = "api", **options) -> str:
        return self.issue(name, **options).token

    def source(
        self,
        name: str = "api",
        *,
        subject: str | None = None,
        delegating: bool | None = None,
    ) -> RenewingTokenSource:
        """``subject``: the principal id IAM issued the account (``sa_...``);
        by default the name, as before IAM assigned ids. ``delegating``: the
        source carries the users it serves in delegations, as ``api`` and
        ``engine`` do (by default exactly those two)."""
        delegate = None
        if delegating if delegating is not None else name in ("api", "engine"):

            def delegate(user, recipient, scope=None):  # type: ignore[misc]
                return self.issue(
                    user.id,
                    kind="user",
                    audience=AGENT_AUDIENCE,
                    actor=subject or name,
                    actor_name=name,
                    groups=tuple(sorted(user.groups)),
                )

        return RenewingTokenSource(
            name, lambda: self.issue(name, subject=subject), delegate=delegate
        )


TEST_TOKENS = TestTokens()
# Another issuer: its tokens fail TEST_TOKENS.verifier, as a forged or foreign
# token does.
OTHER_TOKENS = TestTokens("urn:abi:engine:other")
# A well-formed service key no engine knows: what nats_rpc adapter
# configurations name in tests that never connect.
TEST_SERVICE_KEY = "abi_sk_aaaaaaaaaaaaaaaa_dGVzdC1vbmx5LXNlcnZpY2Uta2V5"
