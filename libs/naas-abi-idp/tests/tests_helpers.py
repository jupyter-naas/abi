"""Verify the provider's tokens the way a relying party does: against its JWKS."""

from __future__ import annotations

from authlib.jose import JsonWebKey, JsonWebToken


def verify_jwt(service, token: str, *, audience: str):
    keys = JsonWebKey.import_key_set(service.keys.jwks())
    claims = JsonWebToken(["ES256"]).decode(token, keys)
    claims.validate(now=int(service.clock()))
    aud = claims["aud"]
    assert audience in (aud if isinstance(aud, list) else [aud])
    return dict(claims)
