"""Unit tests for CachePrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option called
out for this adapter.
"""

import asyncio

import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.cache.v1 import cache_pb2
from naas_abi_core.services.cache.adapters.primary.cache__primary_adapter__NATS import (
    AUTH_HEADER,
    CachePrimaryAdapterNATS,
)
from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheExpiredError,
    CacheNotFoundError,
    DataType,
    ICacheAdapter,
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
        subject: str = "abi.svc.cache.v1.get",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(ICacheAdapter):
    """Minimal in-memory ICacheAdapter for driving the handlers."""

    def __init__(self) -> None:
        self.entries: dict[str, CachedData] = {}

    def get(self, key: str) -> CachedData:
        try:
            return self.entries[key]
        except KeyError:
            raise CacheNotFoundError(f"{key} not found") from None

    def set(self, key: str, value: CachedData) -> None:
        self.entries[key] = value

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        if key in self.entries:
            return False
        self.entries[key] = value
        return True

    def delete(self, key: str) -> None:
        try:
            del self.entries[key]
        except KeyError:
            raise CacheNotFoundError(f"{key} not found") from None

    def exists(self, key: str) -> bool:
        return key in self.entries


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


def _get_request(key: str = "k") -> bytes:
    return cache_pb2.GetRequest(key=key).SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = CachePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_get_request(), headers=None)

    asyncio.run(adapter._handle_get(request))

    response = cache_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.HasField("error")
    assert response.error.code == "UNAUTHENTICATED"
    assert response.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = CachePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_get_request(), headers={AUTH_HEADER: ""})

    asyncio.run(adapter._handle_get(request))

    response = cache_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = CachePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_get_request(), headers={AUTH_HEADER: "not-a-jwt"})

    asyncio.run(adapter._handle_get(request))

    response = cache_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = CachePrimaryAdapterNATS(_StubAdapter(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    request = _FakeRequest(
        data=_get_request(), headers={AUTH_HEADER: wrong_secret_token}
    )

    asyncio.run(adapter._handle_get(request))

    response = cache_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path + business error mapping.
# ---------------------------------------------------------------------------


def test_successful_get_returns_value_with_no_error():
    stub = _StubAdapter()
    stub.entries["k"] = CachedData(key="k", data="hello", data_type=DataType.TEXT)
    adapter = CachePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_get_request("k"), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_get(request))

    response = cache_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.value.key == "k"
    assert response.value.data == "hello"
    assert response.value.data_type == cache_pb2.DATA_TYPE_TEXT


def test_cache_not_found_maps_to_call_error():
    adapter = CachePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=_get_request("missing"), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_get(request))

    response = cache_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "CACHE_NOT_FOUND"
    assert response.error.retryable is False


def test_cache_expired_maps_to_call_error():
    class _ExpiredAdapter(_StubAdapter):
        def get(self, key: str) -> CachedData:
            raise CacheExpiredError(f"{key} expired")

    adapter = CachePrimaryAdapterNATS(_ExpiredAdapter(), SECRET)
    request = _FakeRequest(
        data=_get_request("k"), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_get(request))

    response = cache_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "CACHE_EXPIRED"
    assert response.error.retryable is False


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BoomAdapter(_StubAdapter):
        def get(self, key: str) -> CachedData:
            raise RuntimeError("some sensitive internal detail")

    adapter = CachePrimaryAdapterNATS(_BoomAdapter(), SECRET)
    request = _FakeRequest(data=_get_request(), headers={AUTH_HEADER: _valid_token()})

    asyncio.run(adapter._handle_get(request))

    response = cache_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert "sensitive internal detail" not in response.error.message


def test_set_stores_value_and_returns_no_error():
    stub = _StubAdapter()
    adapter = CachePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=cache_pb2.SetRequest(
            key="k",
            value=cache_pb2.CachedData(
                key="k", data="hello", data_type=cache_pb2.DATA_TYPE_TEXT
            ),
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.cache.v1.set",
    )

    asyncio.run(adapter._handle_set(request))

    response = cache_pb2.SetResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert stub.entries["k"].data == "hello"
    assert stub.entries["k"].data_type == DataType.TEXT


def test_set_if_absent_returns_true_when_written():
    stub = _StubAdapter()
    adapter = CachePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=cache_pb2.SetIfAbsentRequest(
            key="k",
            value=cache_pb2.CachedData(
                key="k", data="hello", data_type=cache_pb2.DATA_TYPE_TEXT
            ),
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.cache.v1.set_if_absent",
    )

    asyncio.run(adapter._handle_set_if_absent(request))

    response = cache_pb2.SetIfAbsentResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.value is True


def test_set_if_absent_returns_false_when_already_present():
    stub = _StubAdapter()
    stub.entries["k"] = CachedData(key="k", data="existing", data_type=DataType.TEXT)
    adapter = CachePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=cache_pb2.SetIfAbsentRequest(
            key="k",
            value=cache_pb2.CachedData(
                key="k", data="new", data_type=cache_pb2.DATA_TYPE_TEXT
            ),
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.cache.v1.set_if_absent",
    )

    asyncio.run(adapter._handle_set_if_absent(request))

    response = cache_pb2.SetIfAbsentResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.value is False
    assert stub.entries["k"].data == "existing"


def test_delete_removes_entry():
    stub = _StubAdapter()
    stub.entries["k"] = CachedData(key="k", data="hello", data_type=DataType.TEXT)
    adapter = CachePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=cache_pb2.DeleteRequest(key="k").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.cache.v1.delete",
    )

    asyncio.run(adapter._handle_delete(request))

    response = cache_pb2.DeleteResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert "k" not in stub.entries


def test_delete_missing_key_maps_to_call_error():
    adapter = CachePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=cache_pb2.DeleteRequest(key="missing").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.cache.v1.delete",
    )

    asyncio.run(adapter._handle_delete(request))

    response = cache_pb2.DeleteResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "CACHE_NOT_FOUND"
    assert response.error.retryable is False


def test_exists_round_trips():
    stub = _StubAdapter()
    stub.entries["k"] = CachedData(key="k", data="hello", data_type=DataType.TEXT)
    adapter = CachePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=cache_pb2.ExistsRequest(key="k").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.cache.v1.exists",
    )

    asyncio.run(adapter._handle_exists(request))

    response = cache_pb2.ExistsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.value is True


def test_exists_returns_false_for_missing_key():
    adapter = CachePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=cache_pb2.ExistsRequest(key="missing").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.cache.v1.exists",
    )

    asyncio.run(adapter._handle_exists(request))

    response = cache_pb2.ExistsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.value is False


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = CachePrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())  # must not raise


_EXPECTED_PB_DATA_TYPE = {
    DataType.TEXT: cache_pb2.DATA_TYPE_TEXT,
    DataType.JSON: cache_pb2.DATA_TYPE_JSON,
    DataType.BINARY: cache_pb2.DATA_TYPE_BINARY,
    DataType.PICKLE: cache_pb2.DATA_TYPE_PICKLE,
}


@pytest.mark.parametrize("data_type", list(DataType))
def test_data_type_round_trips_through_pb_for_every_value(data_type):
    stub = _StubAdapter()
    stub.entries["k"] = CachedData(key="k", data="payload", data_type=data_type)
    adapter = CachePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_get_request("k"), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_get(request))

    response = cache_pb2.GetResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.value.data_type == _EXPECTED_PB_DATA_TYPE[data_type]


def test_owner_emits_mutation_events_once_and_only_when_written():
    from naas_abi_core.services.cache.ontologies.modules.CacheEventOntology import (
        CacheDeleted,
        CacheSet,
    )

    events = []
    primary = CachePrimaryAdapterNATS(
        _StubAdapter(), SECRET, event_publisher=events.append, tier_name="hot"
    )
    req = cache_pb2.SetIfAbsentRequest(
        key="key",
        value=cache_pb2.CachedData(
            key="key", data="value", data_type=cache_pb2.DATA_TYPE_TEXT
        ),
    )
    assert primary._call_set_if_absent(req).value
    assert not primary._call_set_if_absent(req).value
    primary._call_delete(cache_pb2.DeleteRequest(key="key"))
    assert [type(event) for event in events] == [CacheSet, CacheDeleted]
    assert all(event.tier == "hot" for event in events)
