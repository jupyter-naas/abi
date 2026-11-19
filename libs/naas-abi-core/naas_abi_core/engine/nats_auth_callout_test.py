from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.nats_auth_callout import AuthCallout
from naas_abi_core.engine.nats_connection_warden import Admissions, Connection
from naas_abi_core.engine.nats_nkeys import PREFIX_USER, KeyPair, decode_jwt
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import (
    IAMStoreMemory,
)
from naas_abi_core.services.iam.IAMPorts import IAMError, KeyRefusedError
from naas_abi_core.services.iam.IAMService import IAMService

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


# -- the pass, and the admission the warden checks ------------------------------


def _module_key(expires_at: datetime | None = None) -> tuple[IAMService, str, str]:
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    with as_service_account("engine"):
        account = iam.create_service_account("module/default/people")
        key = iam.create_key(account.id, expires_at=expires_at)
    return iam, account.id, key.value


def _admit(callout: AuthCallout, key: str, client_id: int = 7) -> dict:
    request = _request(password=key)
    request["nats"]["client_info"]["id"] = client_id
    response = decode_jwt(callout.answer(request))
    return decode_jwt(response["nats"]["jwt"])


def test_a_pass_lasts_until_its_key_expires_and_no_longer_by_default():
    """Connections end on IAM changes (the warden), not on a timer."""
    iam, _, key = _module_key()
    callout = AuthCallout(iam, KeyPair.create().seed, "nats://127.0.0.1:1")
    assert "exp" not in _admit(callout, key)

    expiry = datetime.now(UTC) + timedelta(days=3)
    iam, _, key = _module_key(expires_at=expiry)
    callout = AuthCallout(iam, KeyPair.create().seed, "nats://127.0.0.1:1")
    assert _admit(callout, key)["exp"] == int(expiry.timestamp())


def test_each_admission_is_recorded_for_the_warden():
    iam, account_id, key = _module_key()
    admissions = Admissions()
    callout = AuthCallout(
        iam, KeyPair.create().seed, "nats://127.0.0.1:1", admissions=admissions
    )
    _admit(callout, key, client_id=42)
    admitted = admissions.get(Connection("SERVER", 42))
    assert admitted is not None
    assert admitted.principal_id == account_id
    assert admitted.key_id == key.split("_")[2]
    assert admitted.permissions == iam.connection_permissions(
        account_id, admitted.key_id
    )


def test_a_refused_connection_is_not_recorded():
    admissions = Admissions()
    callout = AuthCallout(
        SimpleNamespace(authenticate_key=_Failing(KeyRefusedError()).authenticate_key),
        KeyPair.create().seed,
        "nats://127.0.0.1:1",
        admissions=admissions,
    )
    callout.answer(_request())
    assert len(admissions) == 0
