import asyncio
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.identity.v1 import identity_pb2 as pb

from naas_abi_sdk.catalog import OPERATIONS
from naas_abi_sdk.services import IdentityService
from naas_abi_sdk.services.errors import SignInFailed, Suspended, TokenRejected
from naas_abi_sdk.transport import RPCError


def run(coro):
    return asyncio.run(coro)


def test_every_identity_operation_has_a_facade_method():
    missing = [op for op in OPERATIONS["identity"] if not hasattr(IdentityService, op)]
    assert missing == []


def test_authenticate_returns_the_user_as_a_dictionary():
    client = AsyncMock()
    client.authenticate.return_value = pb.AuthenticateResponse(
        user=pb.AuthenticatedUser(
            principal_id="usr_01",
            token=pb.VerifiedToken(provider="acme", issuer="https://idp", subject="s1"),
            group_ids=["grp_01"],
        )
    )
    user = run(IdentityService(client).authenticate("a.b.c", nonce="n"))
    assert user["principal_id"] == "usr_01"
    assert user["token"]["subject"] == "s1"
    assert user["group_ids"] == ["grp_01"]
    request = client.authenticate.call_args.args[0]
    assert (request.token, request.nonce) == ("a.b.c", "n")


def test_authorization_url_is_a_string():
    client = AsyncMock()
    client.authorization_url.return_value = pb.AuthorizationUrlResponse(
        url="https://idp/authorize?x=1"
    )
    url = run(
        IdentityService(client).authorization_url(
            "acme",
            redirect_uri="https://n/cb",
            state="s",
            nonce="n",
            code_challenge="c",
        )
    )
    assert url == "https://idp/authorize?x=1"


@pytest.mark.parametrize(
    ("code", "error"),
    [
        ("TOKEN_EXPIRED", TokenRejected),
        ("TOKEN_WRONG_AUDIENCE", TokenRejected),
        ("SUSPENDED", Suspended),
        ("SIGN_IN_FAILED", SignInFailed),
    ],
)
def test_identity_errors_are_typed(code, error):
    client = AsyncMock()
    client.verify_token.side_effect = RPCError(code, "refused")
    with pytest.raises(error) as raised:
        run(IdentityService(client).verify_token("a.b.c"))
    if error is TokenRejected:
        assert raised.value.reason == code.removeprefix("TOKEN_").lower()
