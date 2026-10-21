"""The engine's side of a remote tool call: what each failure is reported as."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi_core.services.tool_registry.adapters.secondary.RemoteToolsSecondaryAdapterNATS import (
    RemoteToolsSecondaryAdapterNATS,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    RemoteToolError,
    ToolContext,
    ToolDefinition,
)
from naas_abi_proto.tool.v1 import tool_pb2 as pb
from naas_abi_sdk.discovery import ModuleInstance
from naas_abi_sdk.tools import ToolDescriptor
from naas_abi_sdk.transport import RPCError
from nats.errors import NoRespondersError

DESCRIPTOR = ToolDescriptor("lookup", "Look a customer up.")
DEFINITION = ToolDefinition(
    namespace="acme.crm",
    name="lookup",
    description="Look a customer up.",
    module="acme.crm",
    remote=True,
)


def ready(instance_id: str = "i-1") -> ModuleInstance:
    return ModuleInstance(
        "acme.crm", instance_id, "0.0.0", 1, "READY", 0.0, (), tools=(DESCRIPTOR,)
    )


def adapter(*, instances=None, discovery_error=None, call=None):
    """An adapter whose discovery and transport are scripted."""
    result = RemoteToolsSecondaryAdapterNATS("nats://x", "secret", "acme")

    async def get_module(module_id, major):
        if discovery_error is not None:
            raise discovery_error
        return tuple(instances if instances is not None else [ready()])

    async def send(*args: Any, **kwargs: Any):
        if isinstance(call, Exception):
            raise call
        return call if call is not None else pb.InvokeToolResponse(result_json=b"1")

    discovery = SimpleNamespace(get_module=get_module)
    result._clients = lambda: (discovery, SimpleNamespace(call=send))  # type: ignore[method-assign]
    return result


def run(adapter_: RemoteToolsSecondaryAdapterNATS):
    request = adapter_._request(DEFINITION, {"email": "a@b.c"}, {}, ToolContext())
    return asyncio.run(adapter_._call(DEFINITION, 1, request))


def test_a_result_is_the_modules_json():
    assert run(adapter()) == 1


@pytest.mark.parametrize("raw", [b"", b"{not json", b"\xff"])
def test_a_result_that_is_not_json_is_reported_as_such(raw):
    with pytest.raises(RemoteToolError, match="not JSON") as error:
        run(adapter(call=pb.InvokeToolResponse(result_json=raw)))
    assert error.value.code == "TOOL_ERROR"


def test_a_value_error_that_is_not_about_the_result_is_not_called_one():
    # A bad token source or identity raises ValueError in Transport._token; a
    # lookup may too. Neither is the tool's result.
    for failing in (
        adapter(call=ValueError("A call to a module needs a token bound to it")),
        adapter(discovery_error=ValueError("Not a module instance id")),
    ):
        with pytest.raises(ValueError, match="token bound|instance id"):
            run(failing)


def test_a_module_without_a_ready_instance_is_unavailable():
    for failing in (
        adapter(instances=[]),
        adapter(discovery_error=RPCError("MODULE_NOT_FOUND", "acme.crm")),
    ):
        with pytest.raises(RemoteToolError) as error:
            run(failing)
        assert error.value.code == "MODULE_UNAVAILABLE"


def test_transport_failures_have_their_own_codes():
    cases = {
        "MODULE_UNAVAILABLE": NoRespondersError(),
        "DEADLINE_EXCEEDED": TimeoutError(),
        "PERMISSION_DENIED": RPCError("PERMISSION_DENIED", "Caller may not run it"),
    }
    for code, failure in cases.items():
        with pytest.raises(RemoteToolError) as error:
            run(adapter(call=failure))
        assert error.value.code == code
    with pytest.raises(RemoteToolError, match="may still have run"):
        run(adapter(call=TimeoutError()))


def test_a_modules_error_text_is_bounded():
    with pytest.raises(RemoteToolError) as error:
        run(adapter(call=RPCError("TOOL_ERROR", "x" * 5000)))
    assert len(error.value.reason) <= 1024


def test_arguments_that_are_not_json_never_leave_the_engine():
    with pytest.raises(RemoteToolError) as error:
        RemoteToolsSecondaryAdapterNATS._request(
            DEFINITION, {"n": float("nan")}, {}, ToolContext()
        )
    assert error.value.code == "INVALID_ARGUMENT"
    with pytest.raises(RemoteToolError) as error:
        RemoteToolsSecondaryAdapterNATS._request(
            DEFINITION, {"x": "y" * 300_000}, {}, ToolContext()
        )
    assert error.value.code == "PAYLOAD_TOO_LARGE"


def test_the_request_carries_the_callers_user_and_workspace_only():
    request = RemoteToolsSecondaryAdapterNATS._request(
        DEFINITION,
        {"email": "a@b.c"},
        {"region": "eu"},
        ToolContext(user_id="user-7", workspace_id="ws-1", scopes=frozenset({"s"})),
    )
    assert (request.context.principal_id, request.context.workspace_id) == (
        "user-7",
        "ws-1",
    )
    assert request.tool == "lookup" and request.version == "1"
    assert b"scopes" not in request.SerializeToString()
