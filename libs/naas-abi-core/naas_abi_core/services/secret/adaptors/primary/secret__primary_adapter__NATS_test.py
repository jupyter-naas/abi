"""Unit tests for SecretPrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``.
"""

import asyncio
import threading

from naas_abi_core.engine.nats_auth import (
    issue_module_token,
    issue_service_token,
    module_key,
)
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
# Per-caller rights (docs/adr/20261024_secret-service-closed-to-sdk-modules.md).
# ---------------------------------------------------------------------------


def _module_token(identity: str = "billing") -> str:
    return issue_module_token(identity, module_key(SECRET, identity))


def _call(handler, request_cls, token: str, **fields):
    request = _FakeRequest(
        request_cls(**fields).SerializeToString(), headers={AUTH_HEADER: token}
    )
    asyncio.run(handler(request))
    return request.responses[0]


def _stub_with_engine_secrets() -> _StubAdapter:
    stub = _StubAdapter()
    stub.secrets.update(
        {
            "NATS_JWT_SECRET": "jwt",
            "OPENAI_API_KEY": "sk-1",
            "BILLING_TOKEN": "bt",
            "BILLING_CACHE": "c",
        }
    )
    return stub


def _grants_adapter(stub, **kwargs) -> SecretPrimaryAdapterNATS:
    return SecretPrimaryAdapterNATS(
        stub,
        SECRET,
        module_read={"billing": ["BILLING_TOKEN"]},
        module_write={"billing": ["BILLING_CACHE"]},
        **kwargs,
    )


def _get(adapter, token: str, key: str) -> secret_pb2.GetResponse:
    response = secret_pb2.GetResponse()
    response.ParseFromString(
        _call(adapter._handle_get, secret_pb2.GetRequest, token, key=key)
    )
    return response


def test_module_without_a_grant_reads_nothing():
    adapter = SecretPrimaryAdapterNATS(_stub_with_engine_secrets(), SECRET)

    response = _get(adapter, _module_token("nobody"), "NATS_JWT_SECRET")

    assert not response.HasField("error")
    assert not response.found.HasField("value")


def test_module_reads_a_granted_name_only():
    adapter = _grants_adapter(_stub_with_engine_secrets())
    token = _module_token()

    assert _get(adapter, token, "BILLING_TOKEN").found.value == "bt"
    ungranted = _get(adapter, token, "NATS_JWT_SECRET")
    assert not ungranted.HasField("error")
    assert not ungranted.found.HasField("value")


def test_ungranted_name_looks_the_same_as_one_that_does_not_exist():
    adapter = _grants_adapter(_stub_with_engine_secrets())
    token = _module_token()

    assert _get(adapter, token, "NATS_JWT_SECRET") == _get(adapter, token, "NOPE")


def test_write_grant_does_not_allow_reading():
    adapter = _grants_adapter(_stub_with_engine_secrets())

    response = _get(adapter, _module_token(), "BILLING_CACHE")

    assert not response.found.HasField("value")


def test_grants_belong_to_one_module_identity():
    adapter = _grants_adapter(_stub_with_engine_secrets())

    response = _get(adapter, _module_token("crm"), "BILLING_TOKEN")

    assert not response.found.HasField("value")


def test_module_list_returns_only_granted_readable_names():
    adapter = _grants_adapter(_stub_with_engine_secrets())
    response = secret_pb2.ListResponse()
    response.ParseFromString(
        _call(adapter._handle_list, secret_pb2.ListRequest, _module_token())
    )

    assert {e.key: e.value for e in response.found.entries} == {"BILLING_TOKEN": "bt"}


def test_module_list_without_a_grant_is_empty():
    adapter = SecretPrimaryAdapterNATS(_stub_with_engine_secrets(), SECRET)
    response = secret_pb2.ListResponse()
    response.ParseFromString(
        _call(adapter._handle_list, secret_pb2.ListRequest, _module_token())
    )

    assert not response.HasField("error")
    assert list(response.found.entries) == []


def test_module_sets_a_granted_name_and_only_that():
    stub = _stub_with_engine_secrets()
    adapter = _grants_adapter(stub)
    token = _module_token()

    ok = secret_pb2.SetResponse()
    ok.ParseFromString(
        _call(adapter._handle_set, secret_pb2.SetRequest, token, key="BILLING_CACHE", value="v")
    )
    denied = secret_pb2.SetResponse()
    denied.ParseFromString(
        _call(adapter._handle_set, secret_pb2.SetRequest, token, key="NATS_JWT_SECRET", value="x")
    )

    assert not ok.HasField("error")
    assert stub.secrets["BILLING_CACHE"] == "v"
    assert denied.error.code == "PERMISSION_DENIED"
    assert stub.secrets["NATS_JWT_SECRET"] == "jwt"


def test_read_grant_does_not_allow_writing():
    stub = _stub_with_engine_secrets()
    adapter = _grants_adapter(stub)
    response = secret_pb2.SetResponse()
    response.ParseFromString(
        _call(adapter._handle_set, secret_pb2.SetRequest, _module_token(), key="BILLING_TOKEN", value="x")
    )

    assert response.error.code == "PERMISSION_DENIED"
    assert stub.secrets["BILLING_TOKEN"] == "bt"


def test_denied_write_does_not_say_whether_the_name_exists():
    adapter = _grants_adapter(_stub_with_engine_secrets())
    token = _module_token()

    def code(key: str):
        response = secret_pb2.SetResponse()
        response.ParseFromString(
            _call(adapter._handle_set, secret_pb2.SetRequest, token, key=key, value="x")
        )
        return response.error

    assert code("NATS_JWT_SECRET") == code("NOPE")


def test_module_removes_a_granted_name_and_only_that():
    stub = _stub_with_engine_secrets()
    adapter = _grants_adapter(stub)
    token = _module_token()

    ok = secret_pb2.RemoveResponse()
    ok.ParseFromString(
        _call(adapter._handle_remove, secret_pb2.RemoveRequest, token, key="BILLING_CACHE")
    )
    denied = secret_pb2.RemoveResponse()
    denied.ParseFromString(
        _call(adapter._handle_remove, secret_pb2.RemoveRequest, token, key="OPENAI_API_KEY")
    )

    assert not ok.HasField("error")
    assert "BILLING_CACHE" not in stub.secrets
    assert denied.error.code == "PERMISSION_DENIED"
    assert "OPENAI_API_KEY" in stub.secrets


def test_first_party_processes_keep_full_access():
    stub = _stub_with_engine_secrets()
    adapter = _grants_adapter(stub)

    for identity in ("api", "engine", "dagster"):
        token = issue_service_token(identity, SECRET)
        assert _get(adapter, token, "NATS_JWT_SECRET").found.value == "jwt"
        listed = secret_pb2.ListResponse()
        listed.ParseFromString(
            _call(adapter._handle_list, secret_pb2.ListRequest, token)
        )
        assert {e.key for e in listed.found.entries} == set(stub.secrets)
        written = secret_pb2.SetResponse()
        written.ParseFromString(
            _call(adapter._handle_set, secret_pb2.SetRequest, token, key="NEW", value="1")
        )
        assert not written.HasField("error")


def test_a_project_secret_token_for_a_module_name_gets_that_modules_grants_only():
    # The project secret may assert any identity; rights still follow the identity.
    adapter = _grants_adapter(_stub_with_engine_secrets())
    token = issue_service_token("billing", SECRET)

    assert _get(adapter, token, "BILLING_TOKEN").found.value == "bt"
    assert not _get(adapter, token, "NATS_JWT_SECRET").found.HasField("value")


def test_grants_naming_a_first_party_identity_are_refused():
    import pytest

    with pytest.raises(ValueError, match="first-party"):
        SecretPrimaryAdapterNATS(_StubAdapter(), SECRET, module_read={"api": ["A"]})
    with pytest.raises(ValueError, match="first-party"):
        SecretPrimaryAdapterNATS(_StubAdapter(), SECRET, module_write={"engine": ["A"]})
