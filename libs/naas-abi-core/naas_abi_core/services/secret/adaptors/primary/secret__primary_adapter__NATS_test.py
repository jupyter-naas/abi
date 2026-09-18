"""Unit tests for SecretPrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``.
"""

import asyncio

from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.secret.v1 import secret_pb2
from naas_abi_core.services.secret.adaptors.primary.secret__primary_adapter__NATS import (
    AUTH_HEADER,
    SecretPrimaryAdapterNATS,
)
from naas_abi_core.services.secret.SecretPorts import (
    ISecretAdapter,
    SecretAuthenticationError,
)

SECRET = "test-shared-secret"


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
    return issue_service_token("api", SECRET)


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
    token = issue_service_token("api", "a-different-secret")
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
    entries = {e.key: (e.value if e.HasField("value") else None) for e in response.found.entries}
    assert entries == {"A": "1", "B": None}


# ---------------------------------------------------------------------------
# Error mapping.
# ---------------------------------------------------------------------------


def test_secret_authentication_error_maps_to_call_error():
    stub = _StubAdapter()
    stub.raise_auth_error = True
    adapter = SecretPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        _get_request(), headers={AUTH_HEADER: _valid_token()}
    )

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
