"""Unit tests for SecretPrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``.
"""

import asyncio
import threading

from naas_abi_core.engine.nats_test_tokens import OTHER_TOKENS, TEST_TOKENS
from naas_abi_core.proto.secret.v1 import secret_pb2
from naas_abi_core.services.secret.adaptors.primary.secret__primary_adapter__NATS import (
    AUTH_HEADER,
    SecretPrimaryAdapterNATS,
)
from naas_abi_core.services.secret.SecretPorts import (
    ISecretAdapter,
    SecretAuthenticationError,
)

SECRET = TEST_TOKENS.verifier


class _FakeRequest:
    def __init__(
        self,
        data: bytes,
        headers: dict[str, str] | None = None,
        subject: str = "abi.svc.secret.v1.get",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(ISecretAdapter):
    """Minimal in-memory ISecretAdapter for driving the handlers."""

    def __init__(self) -> None:
        self.secrets: dict[str, str | None] = {}
        self.raise_auth_error = False

    def get(self, key: str, default=None):
        if self.raise_auth_error:
            raise SecretAuthenticationError("bad credentials")
        return self.secrets.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.secrets[key] = value

    def remove(self, key: str) -> None:
        self.secrets.pop(key, None)

    def list(self) -> dict[str, str | None]:
        return dict(self.secrets)


def _valid_token() -> str:
    return TEST_TOKENS.token("api")


def _get_request(key: str = "k") -> bytes:
    return secret_pb2.GetRequest(key=key).SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = SecretPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(_get_request(), headers={})

    asyncio.run(adapter._handle_get(request))

    response = secret_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_wrong_secret_returns_unauthenticated():
    adapter = SecretPrimaryAdapterNATS(_StubAdapter(), SECRET)
    token = OTHER_TOKENS.token("api")
    request = _FakeRequest(_get_request(), headers={AUTH_HEADER: token})

    asyncio.run(adapter._handle_get(request))

    response = secret_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Success paths.
# ---------------------------------------------------------------------------


def test_get_returns_value_when_present():
    stub = _StubAdapter()
    stub.secrets["API_KEY"] = "sk-123"
    adapter = SecretPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        secret_pb2.GetRequest(key="API_KEY").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_get(request))

    response = secret_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.found.HasField("value")
    assert response.found.value == "sk-123"


def test_get_reports_unset_value_when_missing():
    adapter = SecretPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        secret_pb2.GetRequest(key="NOPE").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_get(request))

    response = secret_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert not response.found.HasField("value")


def test_set_then_get_round_trips():
    stub = _StubAdapter()
    adapter = SecretPrimaryAdapterNATS(stub, SECRET)
    set_request = _FakeRequest(
        secret_pb2.SetRequest(key="K", value="V").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.secret.v1.set",
    )

    asyncio.run(adapter._handle_set(set_request))

    response = secret_pb2.SetResponse()
    response.ParseFromString(set_request.responses[0])
    assert not response.HasField("error")
    assert stub.secrets["K"] == "V"


def test_remove_deletes_the_key():
    stub = _StubAdapter()
    stub.secrets["K"] = "V"
    adapter = SecretPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        secret_pb2.RemoveRequest(key="K").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.secret.v1.remove",
    )

    asyncio.run(adapter._handle_remove(request))

    response = secret_pb2.RemoveResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert "K" not in stub.secrets


def test_list_round_trips_entries_including_none_values():
    stub = _StubAdapter()
    stub.secrets["A"] = "1"
    stub.secrets["B"] = None
    adapter = SecretPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        secret_pb2.ListRequest().SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.secret.v1.list",
    )

    asyncio.run(adapter._handle_list(request))

    response = secret_pb2.ListResponse()
    response.ParseFromString(request.responses[0])
    entries = {
        e.key: (e.value if e.HasField("value") else None)
        for e in response.found.entries
    }
    assert entries == {"A": "1", "B": None}


# ---------------------------------------------------------------------------
# Error mapping.
# ---------------------------------------------------------------------------


def test_secret_authentication_error_maps_to_call_error():
    stub = _StubAdapter()
    stub.raise_auth_error = True
    adapter = SecretPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(_get_request(), headers={AUTH_HEADER: _valid_token()})

    asyncio.run(adapter._handle_get(request))

    response = secret_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "SECRET_AUTH_FAILED"
    assert response.error.retryable is False


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BrokenAdapter(_StubAdapter):
        def get(self, key, default=None):
            raise RuntimeError("filesystem is on fire")

    adapter = SecretPrimaryAdapterNATS(_BrokenAdapter(), SECRET)
    request = _FakeRequest(_get_request(), headers={AUTH_HEADER: _valid_token()})

    asyncio.run(adapter._handle_get(request))

    response = secret_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert "filesystem is on fire" not in response.error.message


def test_stop_without_start_is_a_noop():
    adapter = SecretPrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())


def test_domain_call_runs_off_the_event_loop_so_the_loop_stays_responsive():
    """Same guarantee as the object_storage primary: the synchronous adapter
    call must run on a worker thread, never inline on the shared
    ``nats_runtime`` loop (see object_storage__primary_adapter__NATS_test)."""
    entered = threading.Event()
    release = threading.Event()
    call_threads: list[threading.Thread] = []

    class _SlowAdapter(_StubAdapter):
        def get(self, key: str, default=None):
            call_threads.append(threading.current_thread())
            entered.set()
            if not release.wait(timeout=2.0):
                raise TimeoutError("event loop never got to release the call")
            return "slow-but-served"

    adapter = SecretPrimaryAdapterNATS(_SlowAdapter(), SECRET)
    request = _FakeRequest(
        secret_pb2.GetRequest(key="API_KEY").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
    )

    async def scenario() -> threading.Thread:
        loop_thread = threading.current_thread()
        handler = asyncio.create_task(adapter._handle_get(request))
        for _ in range(500):
            if entered.is_set():
                break
            await asyncio.sleep(0.01)
        release.set()
        await asyncio.wait_for(handler, timeout=5.0)
        return loop_thread

    loop_thread = asyncio.run(scenario())

    response = secret_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error"), response.error
    assert response.found.value == "slow-but-served"
    assert call_threads and call_threads[0] is not loop_thread


# ---------------------------------------------------------------------------
# Reserved names: IAM's and the IdP's secrets open to their owner only.
# ---------------------------------------------------------------------------


def _call(handler, message, *, account: str, subject: str):
    stub = message[1]
    adapter = SecretPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        message[0],
        headers={AUTH_HEADER: TEST_TOKENS.token(account)},
        subject=subject,
    )
    asyncio.run(getattr(adapter, handler)(request))
    return request.responses[0]


def _stub_with_reserved() -> _StubAdapter:
    stub = _StubAdapter()
    stub.secrets.update(
        {
            "iam/signing-keys/20261018-abcd1234": "PEM",
            "iam/job-trigger-seal": "seal",
            "idp/signing-key": "idp-pem",
            "PLAIN": "value",
        }
    )
    return stub


def test_a_module_cannot_read_write_remove_or_list_reserved_secrets():
    for key in (
        "iam/signing-keys/20261018-abcd1234",
        "iam/job-trigger-seal",
        "IAM/job-trigger-seal",
        " iam/service-keys/engine",
        "idp/signing-key",
    ):
        stub = _stub_with_reserved()
        raw = _call(
            "_handle_get",
            (secret_pb2.GetRequest(key=key).SerializeToString(), stub),
            account="module/p/m",
            subject="abi.svc.secret.v1.get",
        )
        response = secret_pb2.GetResponse()
        response.ParseFromString(raw)
        assert response.error.code == "PERMISSION_DENIED", key
        assert not response.found.HasField("value"), key

        raw = _call(
            "_handle_set",
            (secret_pb2.SetRequest(key=key, value="x").SerializeToString(), stub),
            account="module/p/m",
            subject="abi.svc.secret.v1.set",
        )
        response = secret_pb2.SetResponse()
        response.ParseFromString(raw)
        assert response.error.code == "PERMISSION_DENIED", key
        assert stub.secrets.get(key) != "x"

        raw = _call(
            "_handle_remove",
            (secret_pb2.RemoveRequest(key=key).SerializeToString(), stub),
            account="module/p/m",
            subject="abi.svc.secret.v1.remove",
        )
        response = secret_pb2.RemoveResponse()
        response.ParseFromString(raw)
        assert response.error.code == "PERMISSION_DENIED", key

    stub = _stub_with_reserved()
    raw = _call(
        "_handle_list",
        (secret_pb2.ListRequest().SerializeToString(), stub),
        account="module/p/m",
        subject="abi.svc.secret.v1.list",
    )
    response = secret_pb2.ListResponse()
    response.ParseFromString(raw)
    assert {e.key for e in response.found.entries} == {"PLAIN"}


def test_the_api_account_cannot_read_iam_secrets_either():
    raw = _call(
        "_handle_get",
        (
            secret_pb2.GetRequest(key="iam/job-trigger-seal").SerializeToString(),
            _stub_with_reserved(),
        ),
        account="api",
        subject="abi.svc.secret.v1.get",
    )
    response = secret_pb2.GetResponse()
    response.ParseFromString(raw)
    assert response.error.code == "PERMISSION_DENIED"


def test_each_reserved_name_opens_to_its_owner_only():
    for account, key, allowed in (
        ("engine", "iam/job-trigger-seal", True),
        ("engine", "idp/signing-key", False),
        ("idp", "idp/signing-key", True),
        ("idp", "iam/job-trigger-seal", False),
    ):
        raw = _call(
            "_handle_get",
            (secret_pb2.GetRequest(key=key).SerializeToString(), _stub_with_reserved()),
            account=account,
            subject="abi.svc.secret.v1.get",
        )
        response = secret_pb2.GetResponse()
        response.ParseFromString(raw)
        assert (response.error.code == "") is allowed, (account, key)
