"""Unit tests for CodingEnvironmentPrimaryAdapterNATS's auth/dispatch/
error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option used for
``ObjectStoragePrimaryAdapterNATS``.
"""

import asyncio

import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.coding_environment.v1 import coding_environment_pb2
from naas_abi_core.services.coding_environment.adapters.primary.coding_environment__primary_adapter__NATS import (
    AUTH_HEADER,
    CodingEnvironmentPrimaryAdapterNATS,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    PHASE_RUNNING,
    PHASE_STOPPED,
    AccessDeniedError,
    AgentNeverConnectedError,
    ICodingEnvironmentAdapter,
    ProvisionFailedError,
    ProvisionTimeoutError,
    QuotaExceededError,
    TemplateNotFoundError,
    WorkspaceAccess,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
    WorkspaceStatus,
    WorkspaceTemplate,
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
        subject: str = "abi.svc.coding_environment.v1.ensure_user",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(ICodingEnvironmentAdapter):
    """Minimal in-memory ICodingEnvironmentAdapter for driving the handlers.

    ``next_error``, when set, is raised by every method -- enough to drive
    the shared error-mapping table in ``_handle`` regardless of which
    endpoint a given test exercises.
    """

    def __init__(self) -> None:
        self.next_error: Exception | None = None
        self.templates: list[WorkspaceTemplate] = []
        self.environments: dict[str, WorkspaceStatus] = {}
        self.logs: dict[str, list[str]] = {}
        self.last_params: dict[str, str] | None | object = "unset"

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        if self.next_error is not None:
            raise self.next_error
        return f"user-{external_id}"

    def list_templates(self) -> list[WorkspaceTemplate]:
        if self.next_error is not None:
            raise self.next_error
        return self.templates

    def provision(
        self,
        *,
        user_id: str,
        template_id: str,
        name: str,
        params: dict[str, str] | None = None,
    ) -> WorkspaceStatus:
        if self.next_error is not None:
            raise self.next_error
        self.last_params = params
        status = WorkspaceStatus(
            id=f"ws-{name}", name=name, phase=PHASE_RUNNING, agent_ready=True
        )
        self.environments[status.id] = status
        return status

    def start(
        self, *, workspace_id: str, params: dict[str, str] | None = None
    ) -> WorkspaceStatus:
        if self.next_error is not None:
            raise self.next_error
        self.last_params = params
        return WorkspaceStatus(
            id=workspace_id, name=workspace_id, phase=PHASE_RUNNING, agent_ready=True
        )

    def stop(self, *, workspace_id: str) -> WorkspaceStatus:
        if self.next_error is not None:
            raise self.next_error
        return WorkspaceStatus(
            id=workspace_id, name=workspace_id, phase=PHASE_STOPPED, agent_ready=False
        )

    def delete(self, *, workspace_id: str) -> None:
        if self.next_error is not None:
            raise self.next_error
        self.environments.pop(workspace_id, None)

    def list_environments(self, *, user_id: str) -> list[WorkspaceStatus]:
        if self.next_error is not None:
            raise self.next_error
        return list(self.environments.values())

    def get_status(self, *, workspace_id: str) -> WorkspaceStatus:
        if self.next_error is not None:
            raise self.next_error
        return self.environments[workspace_id]

    def get_logs(self, *, workspace_id: str) -> list[str]:
        if self.next_error is not None:
            raise self.next_error
        return self.logs.get(workspace_id, [])

    def get_access(
        self, *, workspace_id: str, user_id: str, app_slug: str
    ) -> WorkspaceAccess:
        if self.next_error is not None:
            raise self.next_error
        return WorkspaceAccess(
            url=f"https://{workspace_id}.example.com/{app_slug}",
            token="scoped-token",
            expires_at="2099-01-01T00:00:00Z",
        )


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


def _ensure_user_request(
    external_id: str = "ext-1", email: str = "a@b.com", username: str = "alice"
) -> bytes:
    return coding_environment_pb2.EnsureUserRequest(
        external_id=external_id, email=email, username=username
    ).SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = CodingEnvironmentPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_ensure_user_request(), headers=None)

    asyncio.run(adapter._handle_ensure_user(request))

    response = coding_environment_pb2.EnsureUserResponse()
    response.ParseFromString(request.responses[0])
    assert response.HasField("error")
    assert response.error.code == "UNAUTHENTICATED"
    assert response.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = CodingEnvironmentPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_ensure_user_request(), headers={AUTH_HEADER: ""})

    asyncio.run(adapter._handle_ensure_user(request))

    response = coding_environment_pb2.EnsureUserResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = CodingEnvironmentPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=_ensure_user_request(), headers={AUTH_HEADER: "not-a-jwt"}
    )

    asyncio.run(adapter._handle_ensure_user(request))

    response = coding_environment_pb2.EnsureUserResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = CodingEnvironmentPrimaryAdapterNATS(_StubAdapter(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    request = _FakeRequest(
        data=_ensure_user_request(), headers={AUTH_HEADER: wrong_secret_token}
    )

    asyncio.run(adapter._handle_ensure_user(request))

    response = coding_environment_pb2.EnsureUserResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path.
# ---------------------------------------------------------------------------


def test_successful_ensure_user_returns_user_id_with_no_error():
    stub = _StubAdapter()
    adapter = CodingEnvironmentPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_ensure_user_request("ext-42", "x@y.com", "xavier"),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_ensure_user(request))

    response = coding_environment_pb2.EnsureUserResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.user_id == "user-ext-42"


def test_list_environments_round_trips_statuses():
    stub = _StubAdapter()
    stub.environments["ws-a"] = WorkspaceStatus(
        id="ws-a", name="a", phase=PHASE_RUNNING, agent_ready=True
    )
    adapter = CodingEnvironmentPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=coding_environment_pb2.ListEnvironmentsRequest(
            user_id="u1"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.coding_environment.v1.list_environments",
    )

    asyncio.run(adapter._handle_list_environments(request))

    response = coding_environment_pb2.ListEnvironmentsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert [e.id for e in response.environments.environments] == ["ws-a"]
    assert response.environments.environments[0].phase == PHASE_RUNNING
    assert response.environments.environments[0].agent_ready is True


# ---------------------------------------------------------------------------
# params: an empty/absent proto3 map collapses to None for the local call.
# ---------------------------------------------------------------------------


def test_provision_with_no_params_calls_adapter_with_none():
    stub = _StubAdapter()
    adapter = CodingEnvironmentPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=coding_environment_pb2.ProvisionRequest(
            user_id="u1", template_id="t1", name="n1"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.coding_environment.v1.provision",
    )

    asyncio.run(adapter._handle_provision(request))

    assert stub.last_params is None


def test_provision_with_params_calls_adapter_with_dict():
    stub = _StubAdapter()
    adapter = CodingEnvironmentPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=coding_environment_pb2.ProvisionRequest(
            user_id="u1", template_id="t1", name="n1", params={"cpu": "2"}
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.coding_environment.v1.provision",
    )

    asyncio.run(adapter._handle_provision(request))

    assert stub.last_params == {"cpu": "2"}


# ---------------------------------------------------------------------------
# Business error mapping -- must stay exactly symmetric with the client's
# _raise_for_error. Each domain exception carries a status (or None); the
# CallError.status field must round-trip it exactly (HasField-style: unset
# when the exception's status is None, present and equal otherwise).
# ---------------------------------------------------------------------------

_ERROR_MAPPING = [
    (ProvisionFailedError, "PROVISION_FAILED", False),
    (ProvisionTimeoutError, "PROVISION_TIMEOUT", True),
    (AgentNeverConnectedError, "AGENT_NEVER_CONNECTED", True),
    (TemplateNotFoundError, "TEMPLATE_NOT_FOUND", False),
    (WorkspaceNotFoundError, "WORKSPACE_NOT_FOUND", False),
    (WorkspaceNameConflictError, "WORKSPACE_NAME_CONFLICT", False),
    (QuotaExceededError, "QUOTA_EXCEEDED", False),
    (AccessDeniedError, "ACCESS_DENIED", False),
]


@pytest.mark.parametrize(("exc_cls", "code", "retryable"), _ERROR_MAPPING)
def test_domain_exception_maps_to_call_error_with_status(exc_cls, code, retryable):
    stub = _StubAdapter()
    stub.next_error = exc_cls("boom", status=404)
    adapter = CodingEnvironmentPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_ensure_user_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_ensure_user(request))

    response = coding_environment_pb2.EnsureUserResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == code
    assert response.error.retryable is retryable
    assert response.error.HasField("status")
    assert response.error.status == 404


@pytest.mark.parametrize(("exc_cls", "code", "retryable"), _ERROR_MAPPING)
def test_domain_exception_without_status_leaves_status_unset(exc_cls, code, retryable):
    stub = _StubAdapter()
    stub.next_error = exc_cls("boom")
    adapter = CodingEnvironmentPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_ensure_user_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_ensure_user(request))

    response = coding_environment_pb2.EnsureUserResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == code
    assert not response.error.HasField("status")


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    stub = _StubAdapter()
    stub.next_error = RuntimeError("some sensitive internal detail")
    adapter = CodingEnvironmentPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_ensure_user_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_ensure_user(request))

    response = coding_environment_pb2.EnsureUserResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert not response.error.HasField("status")
    assert "sensitive internal detail" not in response.error.message


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = CodingEnvironmentPrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())  # must not raise


@pytest.mark.parametrize(
    "method_name",
    [
        "wait_until_ready",
        "get_workspace_ui_url",
        "get_runtime_binding",
        "get_harness_binding",
    ],
)
def test_optional_local_only_methods_are_not_wired_to_any_endpoint(method_name):
    # Defence-in-depth check on the primary adapter itself: it never
    # registers an endpoint for any of these (see the module docstring), so
    # there is no handler exercising them at all.
    adapter = CodingEnvironmentPrimaryAdapterNATS(_StubAdapter(), SECRET)
    assert not hasattr(adapter, f"_handle_{method_name}")
