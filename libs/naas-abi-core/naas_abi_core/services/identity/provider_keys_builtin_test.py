import pytest

from naas_abi_core.services.identity.IdentityPorts import (
    IdentityProvider,
    ProviderUnavailableError,
)
from naas_abi_core.services.identity.provider_keys import parse_metadata

ISSUER = "http://localhost:9879/idp"


def document(**overrides):
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/jwks.json",
        **overrides,
    }


def provider(provisioning):
    return IdentityProvider(
        name="builtin",
        issuer=ISSUER,
        client_id="abi",
        client_secret="s",
        groups_claim=None,
        scopes=("openid",),
        provisioning=provisioning,
    )


def test_a_built_in_providers_endpoints_stay_below_its_issuer():
    assert (
        parse_metadata(provider("builtin"), document()).token_endpoint
        == f"{ISSUER}/token"
    )
    for key in ("token_endpoint", "jwks_uri", "authorization_endpoint"):
        with pytest.raises(ProviderUnavailableError, match="outside its issuer"):
            parse_metadata(
                provider("builtin"), document(**{key: "http://localhost:1/x"})
            )
    with pytest.raises(ProviderUnavailableError, match="outside its issuer"):
        parse_metadata(
            provider("builtin"), document(token_endpoint=f"{ISSUER}/../token")
        )


def test_another_provider_may_name_endpoints_elsewhere():
    meta = parse_metadata(
        provider("none"), document(token_endpoint="http://localhost:1/token")
    )
    assert meta.token_endpoint == "http://localhost:1/token"
