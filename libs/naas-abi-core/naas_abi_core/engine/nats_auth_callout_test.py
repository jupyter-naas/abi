from types import SimpleNamespace

import pytest
from naas_abi_core.engine.nats_auth_callout import AuthCallout
from naas_abi_core.engine.nats_nkeys import PREFIX_USER, KeyPair, decode_jwt
from naas_abi_core.services.iam.IAMPorts import IAMError, KeyRefusedError

KEY = "abi_sk_aaaaaaaaaaaaaaaa_dGVzdC1vbmx5LXNlcnZpY2Uta2V5"


def _request(user: str = "sa", password: str = KEY) -> dict:
    return {
        "nats": {
            "user_nkey": KeyPair.create(PREFIX_USER).public_key,
            "server_id": {"id": "SERVER"},
            "client_info": {"host": "127.0.0.1"},
            "connect_opts": {"user": user, "pass": password},
        }
    }


class _Failing:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def authenticate_key(self, value):
        raise self.error


@pytest.mark.parametrize(
    "error",
    [
        KeyRefusedError(),
        IAMError("boom"),
        ValueError("a store returned nonsense"),
        RuntimeError("the store is down"),
    ],
)
def test_every_failure_is_answered_with_a_refusal(error):
    """An unanswered request would hold the connection until the server's
    own timeout, and kill the task silently."""
    callout = AuthCallout(
        SimpleNamespace(authenticate_key=_Failing(error).authenticate_key),
        KeyPair.create().seed,
        "nats://127.0.0.1:1",
    )
    response = decode_jwt(callout.answer(_request()))
    body = response["nats"]
    assert body["type"] == "authorization_response"
    assert body["error"] and "jwt" not in body
