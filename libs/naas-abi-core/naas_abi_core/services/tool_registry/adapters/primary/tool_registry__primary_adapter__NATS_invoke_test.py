"""``invoke_tool`` on the catalog's primary: who the caller is, and what it gets back.

The checks themselves are ``EngineToolInvoker``'s (``EngineToolInvoker_test.py``);
here the identity comes from the verified token only, the wire fields reach the
invoker, and a failure is answered with its code and nothing else. No broker; the
real one is ``engine/Engine_invoke_tools_nats_integration_test.py``.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.tools import StructuredTool
from naas_abi_core.engine.nats_auth import (
    issue_module_token,
    issue_service_token,
    module_key,
)
from naas_abi_core.services.tool_registry.adapters.primary.tool_registry__primary_adapter__NATS import (
    ToolRegistryPrimaryAdapterNATS,
)
from naas_abi_core.services.tool_registry.EngineToolInvoker import EngineToolInvoker
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ConfigRequirement,
    PublishedTool,
    ToolDefinition,
    ToolRequirements,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb

SECRET = "tool-registry-invoke-test-secret-at-least-32-bytes"
CREDENTIAL = "ghp_platform_token_that_no_caller_may_ever_read"


class Secrets:
    def resolve(self, key):
        return {"GITHUB_TOKEN": CREDENTIAL, "OTHER": "other-secret-value"}.get(key)


class Binding:
    default_config: dict = {}

    def __init__(self):
        self.contexts = []

    def create(self, context, config):
        self.contexts.append((context, dict(config)))
        return StructuredTool.from_function(
            func=lambda **arguments: f"{arguments['title']} with {config['token']}",
            name="open_issue",
            description="Open an issue.",
            args_schema={
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
        )


def definition(name, scopes=()):
    return ToolDefinition(
        namespace="acme.github",
        name=name,
        description=f"{name} on GitHub",
        module="acme.github",
        input_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
        required_scopes=scopes,
        requirements=ToolRequirements(
            config=(ConfigRequirement(key="token", secret=True),)
        ),
    )


@pytest.fixture
def binding():
    return Binding()


@pytest.fixture
def primary(binding):
    registry = ToolRegistryService()
    registry.publish(
        "acme.github",
        [
            PublishedTool(definition("open_issue", ("github:write",)), binding),
            PublishedTool(definition("unscoped"), binding),
        ],
    )
    invoker = EngineToolInvoker(registry, Secrets(), max_concurrent=2)
    primary = ToolRegistryPrimaryAdapterNATS(
        registry,
        SECRET,
        module_scopes={"partner": ["github:write"], "other_partner": []},
        invoker=invoker,
        module_secrets={"partner": ["GITHUB_TOKEN"]},
        module_unscoped_tools={"partner": ["acme.github/unscoped"]},
    )
    yield primary
    invoker.close()
    primary._dispatch.close()


def token(identity):
    if identity in ("engine", "api", "dagster"):
        return issue_service_token(identity, SECRET)
    return issue_module_token(identity, module_key(SECRET, identity))


def invoke(
    primary, identity="partner", *, tool="acme.github/open_issue", auth=True, **fields
):
    context = fields.pop("context", common_pb2.CallContext())
    secret_refs = fields.pop("secret_refs", {"token": "GITHUB_TOKEN"})
    message = pb.InvokeToolRequest(
        context=context,
        tool=tool,
        arguments_json=fields.pop("arguments", b'{"title": "bug"}'),
        secret_refs=secret_refs,
        **fields,
    )
    request = SimpleNamespace(
        data=message.SerializeToString(),
        headers={"Nats-Auth-Token": token(identity)} if auth else {},
        respond=AsyncMock(),
        _msg=SimpleNamespace(_client=None),
    )
    asyncio.run(primary._handle(request, operation="invoke_tool"))
    return pb.InvokeToolResponse.FromString(request.respond.call_args.args[0])


def test_a_module_runs_a_tool_with_a_secret_resolved_on_the_engine(primary, binding):
    response = invoke(primary)

    assert not response.HasField("error")
    assert json.loads(response.result_json) == "bug with [redacted]"
    assert binding.contexts[0][1] == {"token": CREDENTIAL}
    assert CREDENTIAL not in response.SerializeToString().decode("latin-1")


def test_a_call_without_a_valid_token_is_refused(primary, binding):
    assert invoke(primary, auth=False).error.code == "UNAUTHENTICATED"
    forged = issue_module_token("api", module_key(SECRET, "partner"))
    request = SimpleNamespace(
        data=pb.InvokeToolRequest().SerializeToString(),
        headers={"Nats-Auth-Token": forged},
        respond=AsyncMock(),
        _msg=SimpleNamespace(_client=None),
    )
    asyncio.run(primary._handle(request, operation="invoke_tool"))
    response = pb.InvokeToolResponse.FromString(request.respond.call_args.args[0])
    assert response.error.code == "UNAUTHENTICATED"
    assert binding.contexts == []


def test_the_identity_decides_the_rights_never_the_request(primary, binding):
    # A module naming a user, a workspace or an engine-looking context gains nothing.
    for context in (
        common_pb2.CallContext(principal_id="user-1"),
        common_pb2.CallContext(workspace_id="w-1"),
    ):
        assert invoke(primary, context=context).error.code == "PERMISSION_DENIED"
    assert invoke(primary, "other_partner").error.code == "TOOL_NOT_FOUND"
    assert invoke(primary, "stranger").error.code == "TOOL_NOT_FOUND"
    assert binding.contexts == []


def test_the_engines_own_processes_name_the_user(primary, binding):
    context = common_pb2.CallContext(principal_id="user-9", workspace_id="w-9")

    assert not invoke(primary, "api", context=context).HasField("error")
    seen = binding.contexts[0][0]
    assert (seen.user_id, seen.workspace_id) == ("user-9", "w-9")
    assert invoke(primary, "dagster", context=context).error.code == "PERMISSION_DENIED"


def test_the_grants_of_one_module_are_not_another_modules(primary):
    assert (
        invoke(primary, "other_partner", tool="acme.github/unscoped").error.code
        == "PERMISSION_DENIED"
    )
    assert not invoke(primary, tool="acme.github/unscoped").HasField("error")
    response = invoke(primary, secret_refs={"token": "OTHER"})
    assert response.error.code == "PERMISSION_DENIED"
    assert "other-secret-value" not in response.error.message


def test_inline_credentials_oversized_and_invalid_arguments_are_refused(
    primary, binding
):
    assert (
        invoke(
            primary, secret_refs={}, config_json=b'{"token": "ghp_inline"}'
        ).error.code
        == "PERMISSION_DENIED"
    )
    assert invoke(primary, arguments=b'{"title": 1}').error.code == "INVALID_ARGUMENT"
    assert invoke(primary, arguments=b"{}").error.code == "INVALID_ARGUMENT"
    big = b'{"title": "' + b"x" * (256 * 1024) + b'"}'
    assert invoke(primary, arguments=big).error.code == "PAYLOAD_TOO_LARGE"
    huge = b'{"title": "' + b"x" * (520 * 1024) + b'"}'
    assert invoke(primary, arguments=huge).error.code == "PAYLOAD_TOO_LARGE"
    assert binding.contexts == []


def test_a_malformed_request_is_invalid(primary):
    request = SimpleNamespace(
        data=b"\xff\xff not protobuf",
        headers={"Nats-Auth-Token": token("partner")},
        respond=AsyncMock(),
        _msg=SimpleNamespace(_client=None),
    )
    asyncio.run(primary._handle(request, operation="invoke_tool"))
    response = pb.InvokeToolResponse.FromString(request.respond.call_args.args[0])
    assert response.error.code == "INVALID_ARGUMENT"


def test_a_busy_engine_says_so_and_may_be_retried(primary, binding):
    primary._invoker._in_flight = 2

    response = invoke(primary)

    assert response.error.code == "RESOURCE_EXHAUSTED"
    assert response.error.retryable


def test_without_an_invoker_nothing_runs(binding):
    registry = ToolRegistryService()
    registry.publish("acme.github", [PublishedTool(definition("open_issue"), binding)])
    primary = ToolRegistryPrimaryAdapterNATS(registry, SECRET)
    try:
        response = invoke(primary, "api")
        assert response.error.code == "PERMISSION_DENIED"
        assert binding.contexts == []
    finally:
        primary._dispatch.close()


def test_first_party_callers_hold_every_scope_and_secret_modules_only_their_grants(
    primary,
):
    api = primary.invoke_caller("api")
    assert api.secrets is None and api.unscoped_tools is None and api.may_name_user
    assert "github:write" in api.scopes
    assert not primary.invoke_caller("dagster").may_name_user
    partner = primary.invoke_caller("partner")
    assert partner.secrets == {"GITHUB_TOKEN"}
    assert partner.scopes == {"github:write"} and not partner.may_name_user
    nobody = primary.invoke_caller("stranger")
    assert nobody.secrets == frozenset() and nobody.scopes == frozenset()
    assert nobody.unscoped_tools == ()


# ------------------------------------------------------------- cancel_tool
class SlowBinding:
    """A coroutine tool that runs until it is cancelled."""

    default_config: dict = {}

    def __init__(self):
        self.started = asyncio.Event()
        self.cleaned = False

    def create(self, context, config):
        binding = self

        async def run(**arguments):
            binding.started.set()
            try:
                await asyncio.sleep(30)
            finally:
                binding.cleaned = True

        return StructuredTool.from_function(
            coroutine=run,
            name="slow",
            description="Runs until cancelled.",
            args_schema={"type": "object", "properties": {}},
        )


def _request(identity, message, *, auth=True):
    return SimpleNamespace(
        data=message.SerializeToString(),
        headers={"Nats-Auth-Token": token(identity)} if auth else {},
        respond=AsyncMock(),
        _msg=SimpleNamespace(_client=None),
    )


@pytest.fixture
def slow_primary():
    registry = ToolRegistryService()
    slow = SlowBinding()
    registry.publish(
        "acme.slow",
        [
            PublishedTool(
                ToolDefinition(
                    namespace="acme.slow",
                    name="slow",
                    description="slow on GitHub",
                    module="acme.slow",
                    input_schema={"type": "object", "properties": {}},
                    required_scopes=("slow:run",),
                ),
                slow,
            )
        ],
    )
    invoker = EngineToolInvoker(registry, Secrets(), max_concurrent=2)
    primary = ToolRegistryPrimaryAdapterNATS(
        registry,
        SECRET,
        module_scopes={"partner": ["slow:run"], "other_partner": ["slow:run"]},
        invoker=invoker,
    )
    yield primary, slow
    invoker.close()
    primary._dispatch.close()


async def _cancel(primary, identity, call_id, *, auth=True):
    request = _request(identity, pb.CancelToolRequest(call_id=call_id), auth=auth)
    await primary._handle(request, operation="cancel_tool")
    return pb.CancelToolResponse.FromString(request.respond.call_args.args[0])


def test_a_caller_cancels_its_own_running_tool(slow_primary):
    primary, slow = slow_primary

    async def scenario():
        request = _request(
            "partner", pb.InvokeToolRequest(tool="acme.slow/slow", call_id="c-1")
        )
        running = asyncio.ensure_future(
            primary._handle(request, operation="invoke_tool")
        )
        await asyncio.wait_for(slow.started.wait(), 5)
        answer = await _cancel(primary, "partner", "c-1")
        await asyncio.wait_for(running, 5)
        return answer, pb.InvokeToolResponse.FromString(
            request.respond.call_args.args[0]
        )

    answer, response = asyncio.run(scenario())
    assert answer.cancelled and not answer.HasField("error")
    assert response.error.code == "CANCELLED"
    assert slow.cleaned


def test_another_identity_cannot_cancel_a_call_it_did_not_start(slow_primary):
    primary, slow = slow_primary

    async def scenario():
        request = _request(
            "partner", pb.InvokeToolRequest(tool="acme.slow/slow", call_id="c-1")
        )
        running = asyncio.ensure_future(
            primary._handle(request, operation="invoke_tool")
        )
        await asyncio.wait_for(slow.started.wait(), 5)
        stranger = await _cancel(primary, "other_partner", "c-1")
        # Even the engine's processes cancel only their own calls.
        engine = await _cancel(primary, "engine", "c-1")
        await asyncio.sleep(0.05)
        still_running = not running.done()
        owner = await _cancel(primary, "partner", "c-1")
        await asyncio.wait_for(running, 5)
        return stranger, engine, still_running, owner

    stranger, engine, still_running, owner = asyncio.run(scenario())
    assert not stranger.cancelled and not engine.cancelled and still_running
    assert owner.cancelled
    assert not stranger.HasField("error")  # nothing tells whether the id exists


def test_a_cancel_needs_a_valid_token_and_a_valid_id(slow_primary):
    primary, _ = slow_primary

    async def scenario():
        return (
            await _cancel(primary, "partner", "c-1", auth=False),
            await _cancel(primary, "partner", "not valid!"),
            await _cancel(primary, "partner", ""),
        )

    unauthenticated, bad, empty = asyncio.run(scenario())
    assert unauthenticated.error.code == "UNAUTHENTICATED"
    assert bad.error.code == "INVALID_ARGUMENT"
    assert empty.error.code == "INVALID_ARGUMENT"


def test_an_engine_that_runs_no_tools_runs_no_cancel_either():
    registry = ToolRegistryService()
    primary = ToolRegistryPrimaryAdapterNATS(registry, SECRET)

    async def scenario():
        return await _cancel(primary, "partner", "c-1")

    try:
        assert asyncio.run(scenario()).error.code == "PERMISSION_DENIED"
    finally:
        primary._dispatch.close()
