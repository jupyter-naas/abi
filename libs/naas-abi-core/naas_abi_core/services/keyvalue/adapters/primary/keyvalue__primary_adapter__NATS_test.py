"""Unit tests for KeyValuePrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option called
out for this adapter.
"""

import asyncio

import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.keyvalue.v1 import keyvalue_pb2
from naas_abi_core.services.keyvalue.adapters.primary.keyvalue__primary_adapter__NATS import (
    AUTH_HEADER,
    KeyValuePrimaryAdapterNATS,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import (
    IKeyValueAdapter,
    KVLockTimeoutError,
    KVNotFoundError,
)

SECRET = "test-shared-secret"


class _FakeRequest:
    """Stands in for nats.micro.request.Request: same ``.data``/``.headers``
    surface, and ``respond`` just records the payload instead of publishing
    it anywhere."""

    def __init__(
        self,
        data: bytes,
        headers: dict[str, str] | None = None,
        subject: str = "abi.svc.keyvalue.v1.get",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(IKeyValueAdapter):
    """Minimal in-memory IKeyValueAdapter for driving the handlers."""

    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def get(self, key: str) -> bytes:
        try:
            return self.values[key]
        except KeyError:
            raise KVNotFoundError(f"Key not found: {key}") from None

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        self.values[key] = value

    def set_if_not_exists(
        self, key: str, value: bytes, ttl: int | None = None
    ) -> bool:
        if key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, key: str) -> None:
        try:
            del self.values[key]
        except KeyError:
            raise KVNotFoundError(f"Key not found: {key}") from None

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        if self.values.get(key) != value:
            return False
        del self.values[key]
        return True

    def exists(self, key: str) -> bool:
        return key in self.values


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


def _get_request(key: str = "k") -> bytes:
    return keyvalue_pb2.GetRequest(key=key).SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = KeyValuePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_get_request(), headers=None)

    asyncio.run(adapter._handle_get(request))

    response = keyvalue_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.HasField("error")
    assert response.error.code == "UNAUTHENTICATED"
    assert response.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = KeyValuePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_get_request(), headers={AUTH_HEADER: ""})

    asyncio.run(adapter._handle_get(request))

    response = keyvalue_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = KeyValuePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_get_request(), headers={AUTH_HEADER: "not-a-jwt"})

    asyncio.run(adapter._handle_get(request))

    response = keyvalue_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = KeyValuePrimaryAdapterNATS(_StubAdapter(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    request = _FakeRequest(
        data=_get_request(), headers={AUTH_HEADER: wrong_secret_token}
    )

    asyncio.run(adapter._handle_get(request))

    response = keyvalue_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path + business error mapping.
# ---------------------------------------------------------------------


def test_successful_get_returns_value_with_no_error():
    stub = _StubAdapter()
    stub.set("k", b"hello")
    adapter = KeyValuePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_get_request("k"), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_get(request))

    response = keyvalue_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.value == b"hello"


def test_key_not_found_maps_to_call_error():
    adapter = KeyValuePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=_get_request("missing"),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_get(request))

    response = keyvalue_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "KV_NOT_FOUND"
    assert response.error.retryable is False


def test_lock_timeout_maps_to_call_error_with_detail():
    class _LockTimeoutAdapter(_StubAdapter):
        def set_if_not_exists(
            self, key: str, value: bytes, ttl: int | None = None
        ) -> bool:
            raise KVLockTimeoutError(key=key, attempts=3, timeout=1.5)

    adapter = KeyValuePrimaryAdapterNATS(_LockTimeoutAdapter(), SECRET)
    request = _FakeRequest(
        data=keyvalue_pb2.SetIfNotExistsRequest(
            key="k", value=b"x"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.keyvalue.v1.set_if_not_exists",
    )

    asyncio.run(adapter._handle_set_if_not_exists(request))

    response = keyvalue_pb2.SetIfNotExistsResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "KV_LOCK_TIMEOUT"
    assert response.error.retryable is True
    assert response.HasField("lock_timeout_detail")
    assert response.lock_timeout_detail.key == "k"
    assert response.lock_timeout_detail.attempts == 3
    assert response.lock_timeout_detail.timeout_seconds == 1.5


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BoomAdapter(_StubAdapter):
        def get(self, key: str) -> bytes:
            raise RuntimeError("some sensitive internal detail")

    adapter = KeyValuePrimaryAdapterNATS(_BoomAdapter(), SECRET)
    request = _FakeRequest(
        data=_get_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_get(request))

    response = keyvalue_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert "sensitive internal detail" not in response.error.message


def test_set_if_not_exists_round_trips_true_on_write():
    stub = _StubAdapter()
    adapter = KeyValuePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=keyvalue_pb2.SetIfNotExistsRequest(
            key="k", value=b"v"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.keyvalue.v1.set_if_not_exists",
    )

    asyncio.run(adapter._handle_set_if_not_exists(request))

    response = keyvalue_pb2.SetIfNotExistsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.ok_value is True


def test_exists_round_trips_bool():
    stub = _StubAdapter()
    stub.set("k", b"v")
    adapter = KeyValuePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=keyvalue_pb2.ExistsRequest(key="k").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.keyvalue.v1.exists",
    )

    asyncio.run(adapter._handle_exists(request))

    response = keyvalue_pb2.ExistsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.ok_value is True


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = KeyValuePrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())  # must not raise


@pytest.mark.parametrize("method_name", ["lock"])
def test_stub_adapter_does_not_expose_client_side_only_lock_helper(method_name):
    # Defence-in-depth check on the test double itself: KeyValueService.lock()
    # is not part of IKeyValueAdapter (see the module docstring), so the
    # primary adapter never registers an endpoint for it -- there is no
    # handler exercising it at all.
    adapter = KeyValuePrimaryAdapterNATS(_StubAdapter(), SECRET)
    assert not hasattr(adapter, f"_handle_{method_name}")
