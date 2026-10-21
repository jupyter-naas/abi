import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("jsonschema")
from jsonschema.exceptions import SchemaError
from naas_abi_proto.tool.v1 import tool_pb2 as pb

from naas_abi_sdk.discovery import ModuleInstance, ModuleProxy, module_descriptor
from naas_abi_sdk.module import BaseModule
from naas_abi_sdk.tool_host import ToolHost
from naas_abi_sdk.tools import (
    ToolConfig,
    ToolDescriptor,
    ToolError,
    tool_subject,
)
from naas_abi_sdk.transport import RPCError

LOOKUP = ToolDescriptor(
    "lookup",
    "Look a customer up by email.",
    {
        "type": "object",
        "properties": {"email": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["email"],
        "additionalProperties": False,
    },
    config=(ToolConfig("region"), ToolConfig("tier", required=False)),
)


class Session:
    """What the host needs of a discovery session: the verdict of authorize_tool."""

    def __init__(self, identity="engine", admin=False, refuse=None):
        self.instance_id, self.lease_token = "instance-1", "lease"
        self.authorizations = []
        self.client = SimpleNamespace(project="acme", _call=self._call)
        self.identity, self.admin, self.refuse = identity, admin, refuse

    async def _call(self, operation, request, response_type):
        self.authorizations.append((operation, request))
        if self.refuse:
            raise RPCError(self.refuse, "refused")
        return response_type(caller_identity=self.identity, caller_admin=self.admin)


def request(arguments=None, config=None, user="", **fields):
    fields.setdefault("tool", "lookup")
    value = pb.InvokeToolRequest(
        arguments_json=json.dumps(
            {"email": "a@b.c"} if arguments is None else arguments
        ).encode(),
        config_json=json.dumps(
            config if config is not None else {"region": "eu"}
        ).encode(),
        **fields,
    )
    value.context.principal_id = user
    return value


def host(handler=None, *, session=None, authorize=None, descriptor=LOOKUP, **kwargs):
    calls = []

    async def default(arguments, call):
        calls.append((arguments, call))
        return {"found": arguments["email"]}

    return (
        ToolHost(
            session or Session(),
            {descriptor.name: (descriptor, handler or default)},
            authorize or (lambda name, caller: caller.engine),
            **kwargs,
        ),
        calls,
    )


def invoke(tool_host, value, token="token"):
    data = value if isinstance(value, bytes) else value.SerializeToString()
    return asyncio.run(tool_host.respond("lookup", data, {"Nats-Auth-Token": token}))


def test_a_tool_runs_with_its_validated_arguments_and_the_callers_identity():
    tool_host, calls = host(session=Session("api"))
    response = invoke(tool_host, request(user="user-7"))
    assert not response.error.code
    assert json.loads(response.result_json) == {"found": "a@b.c"}
    ((arguments, call),) = calls
    assert arguments == {"email": "a@b.c"}
    assert call.config == {"region": "eu"}
    assert (call.caller.identity, call.caller.user_id) == ("api", "user-7")
    # Discovery was asked about this instance, this tool and the caller's token.
    ((operation, asked),) = tool_host.session.authorizations
    assert operation == "authorize_tool"
    assert (
        asked.instance_id,
        asked.lease_token,
        asked.tool_name,
        asked.caller_token,
    ) == (
        "instance-1",
        "lease",
        "lookup",
        "token",
    )


def test_synchronous_handlers_run_on_a_thread_and_may_skip_the_call():
    seen = {}

    def handler(arguments):
        seen["thread"] = threading.current_thread()
        return len(arguments["email"])

    tool_host, _ = host(handler)
    assert json.loads(invoke(tool_host, request()).result_json) == 5
    assert seen["thread"] is not threading.main_thread()


@pytest.mark.parametrize(
    "arguments",
    [
        {},  # required property missing
        {"email": 3},
        {"email": "a@b.c", "limit": "ten"},
        {"email": "a@b.c", "extra": True},
        [],
        "text",
    ],
)
def test_malformed_arguments_are_rejected_before_the_handler_runs(arguments):
    tool_host, calls = host()
    response = invoke(tool_host, request(arguments))
    assert response.error.code == "INVALID_ARGUMENT"
    assert not response.result_json
    assert calls == []


def test_arguments_that_are_not_json_never_reach_the_handler():
    tool_host, calls = host()
    for raw in (b"{nope", b'{"email": NaN}', b"\xff\xfe"):
        value = request()
        value.arguments_json = raw
        assert invoke(tool_host, value).error.code == "INVALID_ARGUMENT"
    assert calls == []


def test_size_limits_are_enforced_before_the_handler():
    tool_host, calls = host()
    big = request({"email": "x" * (256 * 1024)})
    assert invoke(tool_host, big).error.code == "PAYLOAD_TOO_LARGE"
    huge_config = request(config={"region": "x" * (64 * 1024)})
    assert invoke(tool_host, huge_config).error.code == "PAYLOAD_TOO_LARGE"
    assert invoke(tool_host, b"x" * (512 * 1024 + 1)).error.code == "PAYLOAD_TOO_LARGE"
    uploaded = asyncio.run(
        tool_host.respond("lookup", request().SerializeToString(), {}, uploaded=True)
    )
    assert uploaded.error.code == "PAYLOAD_TOO_LARGE"
    assert invoke(tool_host, b"\xff\xff\xff").error.code == "INVALID_ARGUMENT"
    assert calls == []


def test_the_configuration_is_checked_against_the_descriptor():
    tool_host, calls = host()
    assert invoke(tool_host, request(config={})).error.code == "INVALID_ARGUMENT"
    assert (
        invoke(tool_host, request(config={"region": "eu", "api_key": "k"})).error.code
        == "INVALID_ARGUMENT"
    )
    assert not invoke(
        tool_host, request(config={"region": "eu", "tier": "x"})
    ).error.code
    assert len(calls) == 1


def test_a_caller_discovery_refuses_never_reaches_the_handler():
    for code in ("UNAUTHENTICATED", "PERMISSION_DENIED", "LEASE_EXPIRED"):
        tool_host, calls = host(session=Session(refuse=code))
        assert invoke(tool_host, request()).error.code == code
        assert calls == []


def test_the_modules_hook_decides_who_may_run_a_tool():
    tool_host, calls = host(session=Session("some-module"))
    # By default only the engine's own processes.
    assert invoke(tool_host, request()).error.code == "PERMISSION_DENIED"
    seen = []

    async def allow_billing(name, caller):
        seen.append((name, caller.identity))
        return caller.identity == "some-module"

    tool_host, calls = host(session=Session("some-module"), authorize=allow_billing)
    assert not invoke(tool_host, request()).error.code
    assert seen == [("lookup", "some-module")]
    # The hook replaces the default: it may refuse the engine too.
    tool_host, calls = host(session=Session("engine"), authorize=lambda n, c: False)
    assert invoke(tool_host, request()).error.code == "PERMISSION_DENIED"
    assert calls == []
    # Only True allows.
    tool_host, calls = host(authorize=lambda n, c: "yes")
    assert invoke(tool_host, request()).error.code == "PERMISSION_DENIED"


def test_only_the_engines_processes_speak_for_a_user():
    tool_host, calls = host(session=Session("some-module"), authorize=lambda n, c: True)
    assert invoke(tool_host, request(user="user-7")).error.code == "PERMISSION_DENIED"
    assert calls == []
    assert not invoke(tool_host, request()).error.code
    tool_host, calls = host(session=Session("dagster"))
    assert invoke(tool_host, request(user="user-7")).error.code == "PERMISSION_DENIED"


def test_a_handlers_failure_reaches_the_caller_without_its_internals():
    def broken(arguments):
        raise RuntimeError("password=hunter2 at /srv/secret.py")

    tool_host, _ = host(broken)
    response = invoke(tool_host, request())
    assert response.error.code == "TOOL_ERROR"
    assert "hunter2" not in response.error.message
    assert "secret.py" not in response.error.message

    def rpc(arguments):
        raise RPCError("PERMISSION_DENIED", "vault token expired")

    tool_host, _ = host(rpc)
    response = invoke(tool_host, request())
    assert (response.error.code, response.error.message) == (
        "TOOL_ERROR",
        "Tool execution failed",
    )

    def refused(arguments):
        raise ToolError("Customer is archived")

    tool_host, _ = host(refused)
    response = invoke(tool_host, request())
    assert (response.error.code, response.error.message) == (
        "TOOL_ERROR",
        "Customer is archived",
    )


def test_a_slow_handler_hits_the_callers_deadline():
    async def slow(arguments, call):
        await asyncio.sleep(5)

    tool_host, _ = host(slow)
    value = request()
    value.context.timeout_ms = 50
    response = invoke(tool_host, value)
    assert response.error.code == "DEADLINE_EXCEEDED"


def test_results_must_be_json_and_bounded():
    for result, code in (
        (object(), "TOOL_ERROR"),
        (float("nan"), "TOOL_ERROR"),
        ("x" * (512 * 1024), "PAYLOAD_TOO_LARGE"),
    ):
        tool_host, _ = host(lambda arguments, result=result: result)
        assert invoke(tool_host, request()).error.code == code
    tool_host, _ = host(lambda arguments: None)
    assert invoke(tool_host, request()).result_json == b"null"


def test_a_result_must_match_the_declared_output_schema():
    descriptor = ToolDescriptor(
        "lookup",
        "Look a customer up.",
        LOOKUP.input_schema,
        output_schema={"type": "object", "required": ["id"]},
        config=LOOKUP.config,
    )
    tool_host, _ = host(lambda a: {"id": 1}, descriptor=descriptor)
    assert not invoke(tool_host, request()).error.code
    tool_host, _ = host(lambda a: {"name": "x"}, descriptor=descriptor)
    assert invoke(tool_host, request()).error.code == "TOOL_ERROR"


def test_the_request_must_name_this_tool_and_its_declared_version():
    tool_host, calls = host()
    assert invoke(tool_host, request(tool="other")).error.code == "INVALID_ARGUMENT"
    assert invoke(tool_host, request(version="2")).error.code == "TOOL_NOT_FOUND"
    assert not invoke(tool_host, request(version="1")).error.code
    assert len(calls) == 1


def test_a_draining_host_takes_no_new_call():
    tool_host, calls = host()
    tool_host.closing = True
    assert invoke(tool_host, request()).error.code == "MODULE_UNAVAILABLE"
    assert calls == []


def test_an_invalid_schema_fails_before_the_module_is_ready():
    broken = ToolDescriptor("lookup", "x", {"type": "object", "required": "email"})
    with pytest.raises(SchemaError):
        host(descriptor=broken)


def test_the_descriptor_round_trips_through_discovery_in_canonical_form():
    class Crm(BaseModule):
        module_id = "acme.crm"
        tools = (LOOKUP,)

    descriptor = module_descriptor(Crm, "acme.crm", ())
    (declared,) = descriptor.tools
    assert declared.id == "acme.crm/lookup@1"
    assert (declared.namespace, declared.module) == ("acme.crm", "acme.crm")
    assert not declared.requirements.config[0].secret
    assert ToolDescriptor.from_pb(declared) == LOOKUP
    # Replicas serialise alike, whatever order their schemas were written in.
    reordered = ToolDescriptor(
        "lookup",
        LOOKUP.description,
        dict(reversed(list(LOOKUP.input_schema.items()))),
        config=LOOKUP.config,
    )
    assert reordered.to_pb("acme.crm") == declared


def test_a_module_binds_each_declared_tool_once():
    class Crm(BaseModule):
        tools = (LOOKUP,)

    module = Crm(SimpleNamespace(), Crm.Configuration())
    with pytest.raises(ValueError, match="Declare a ToolDescriptor"):
        module.expose_tool("other", lambda arguments: 1)
    with pytest.raises(TypeError):
        module.expose_tool("lookup", "not callable")
    module.expose_tool("lookup", lambda arguments: 1)
    with pytest.raises(ValueError, match="already registered"):
        module.expose_tool("lookup", lambda arguments: 2)


def test_the_default_hook_is_the_engine_only():
    from naas_abi_sdk.tools import ToolCaller

    class Crm(BaseModule):
        tools = (LOOKUP,)

    module = Crm(SimpleNamespace(), Crm.Configuration())
    assert module.authorize_tool("lookup", ToolCaller("engine"))
    assert module.authorize_tool("lookup", ToolCaller("api"))
    assert not module.authorize_tool("lookup", ToolCaller("some-module"))


def test_descriptors_are_validated_when_declared():
    for args in (
        ("bad name", "d"),
        ("ok", " "),
        ("ok", "d", {"type": "array"}),
    ):
        with pytest.raises(ValueError):
            ToolDescriptor(*args)
    with pytest.raises(ValueError):
        ToolDescriptor("ok", "d", version="v1")
    with pytest.raises(ValueError):
        ToolConfig("not-an-identifier")


def test_a_module_proxy_calls_the_serving_instance():
    async def scenario():
        instance = ModuleInstance(
            "acme.crm", "instance-1", "0.0.0", 1, "READY", 0.0, (), tools=(LOOKUP,)
        )
        response = pb.InvokeToolResponse(result_json=b'{"found": true}')
        transport = SimpleNamespace(call=AsyncMock(return_value=response))
        proxy = ModuleProxy(
            SimpleNamespace(
                project="acme",
                transport=transport,
                get_module=AsyncMock(return_value=(instance,)),
            ),
            "acme.crm",
        )
        result = await proxy.call_tool(
            "lookup", {"email": "a@b.c"}, config={"region": "eu"}
        )
        assert result == {"found": True}
        subject, sent, _ = transport.call.await_args.args
        assert subject == tool_subject("acme", "instance-1", "lookup")
        assert transport.call.await_args.kwargs == {"instance_id": "instance-1"}
        assert json.loads(sent.arguments_json) == {"email": "a@b.c"}
        assert json.loads(sent.config_json) == {"region": "eu"}
        with pytest.raises(RPCError, match="TOOL_NOT_FOUND"):
            await proxy.call_tool("missing")

    asyncio.run(scenario())
