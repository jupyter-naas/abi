import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("jsonschema")
from jsonschema.exceptions import SchemaError
from naas_abi_proto.tool.v1 import tool_pb2 as pb

from naas_abi_sdk.cancellation import current_cancellation
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


def request(arguments=None, config=None, user="", context_workspace="", **fields):
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
    value.context.workspace_id = context_workspace
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


def test_only_the_engines_processes_name_a_workspace_either():
    tool_host, calls = host(session=Session("some-module"), authorize=lambda n, c: True)
    assert (
        invoke(tool_host, request(context_workspace="w-1")).error.code
        == "PERMISSION_DENIED"
    )
    assert calls == []
    tool_host, calls = host(session=Session("api"))
    assert not invoke(tool_host, request(context_workspace="w-1")).error.code
    assert calls[0][1].caller.workspace_id == "w-1"


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


def test_a_timeout_the_handler_raises_itself_is_a_tool_failure_not_the_deadline():
    async def async_timeout(arguments):
        raise TimeoutError("upstream took too long")

    def sync_timeout(arguments):
        raise TimeoutError("upstream took too long")

    async def asyncio_timeout(arguments):
        raise asyncio.TimeoutError()

    for handler in (async_timeout, sync_timeout, asyncio_timeout):
        tool_host, _ = host(handler)
        response = invoke(tool_host, request())
        assert response.error.code == "TOOL_ERROR"
        assert response.error.message == "Tool execution failed"
        assert "deadline" not in response.error.message


def test_close_cancels_running_calls_even_when_the_connection_is_lost():
    async def scenario():
        tool_host, _ = host()

        class Lost:
            async def unsubscribe(self):
                raise ConnectionError("connection closed")

        tool_host.subscriptions = [Lost(), Lost()]
        cancelled = []

        async def cancel():
            cancelled.append(True)

        tool_host.calls.cancel = cancel
        await tool_host.close()
        assert cancelled == [True] and tool_host.subscriptions == []

    asyncio.run(scenario())


def test_a_start_that_fails_reports_its_own_error():
    async def scenario():
        tool_host, _ = host()

        class Lost:
            async def unsubscribe(self):
                raise ConnectionError("connection closed")

        class Connection:
            def __init__(self):
                self.count = 0

            async def subscribe(self, subject, cb):
                self.count += 1
                return Lost()

            @property
            def max_payload(self):
                return 1 << 20

        async def connect():
            return Connection()

        tool_host.session.client.transport = SimpleNamespace(connect=connect)
        original = RuntimeError("flush failed")

        async def broken(nc):
            raise original

        import naas_abi_sdk.tool_host as module

        saved, module.flush_to_broker = module.flush_to_broker, broken
        try:
            with pytest.raises(RuntimeError) as raised:
                await tool_host.start()
        finally:
            module.flush_to_broker = saved
        assert raised.value is original

    asyncio.run(scenario())


def _proxy(instances, response=None):
    transport = SimpleNamespace(
        call=AsyncMock(return_value=response or pb.InvokeToolResponse(result_json=b"1"))
    )
    proxy = ModuleProxy(
        SimpleNamespace(
            project="acme",
            transport=transport,
            get_module=AsyncMock(return_value=tuple(instances)),
        ),
        "acme.crm",
    )
    return proxy, transport


def test_call_tool_uses_its_timeout_as_the_wait_and_the_handlers_deadline():
    async def scenario():
        instance = ModuleInstance(
            "acme.crm", "i-1", "0.0.0", 1, "READY", 0.0, (), tools=(LOOKUP,)
        )
        proxy, transport = _proxy([instance])
        await proxy.call_tool("lookup", {"email": "a@b.c"}, timeout=7.5)
        assert transport.call.await_args.kwargs["timeout"] == 7.5
        sent = transport.call.await_args.args[1]
        assert sent.version == "1"
        await proxy.call_tool("lookup", {"email": "a@b.c"})
        assert "timeout" not in transport.call.await_args.kwargs

    asyncio.run(scenario())


def test_call_tool_refuses_what_is_not_json_before_sending():
    async def scenario():
        instance = ModuleInstance(
            "acme.crm", "i-1", "0.0.0", 1, "READY", 0.0, (), tools=(LOOKUP,)
        )
        proxy, transport = _proxy([instance])
        for arguments in ({"limit": float("nan")}, {"x": object()}):
            with pytest.raises(RPCError, match="INVALID_ARGUMENT"):
                await proxy.call_tool("lookup", arguments)
        with pytest.raises(RPCError, match="INVALID_ARGUMENT"):
            await proxy.call_tool("lookup", {}, config={"n": float("inf")})
        transport.call.assert_not_awaited()

    asyncio.run(scenario())


def test_call_tool_spreads_calls_over_the_replicas():
    async def scenario():
        instances = [
            ModuleInstance(
                "acme.crm", f"i-{n}", "0.0.0", 1, "READY", 0.0, (), tools=(LOOKUP,)
            )
            for n in range(4)
        ]
        proxy, transport = _proxy(instances)
        for _ in range(80):
            await proxy.call_tool("lookup", {"email": "a@b.c"})
        used = {call.kwargs["instance_id"] for call in transport.call.await_args_list}
        assert len(used) > 1

    asyncio.run(scenario())


def test_the_transports_per_call_timeout_is_the_deadline_sent_and_waited():
    from naas_abi_sdk.transport import Transport

    async def scenario():
        transport = Transport("nats://127.0.0.1:1", "token", timeout=30)
        seen = {}

        async def exchange(
            subject, payload, headers, response_type, transfer=None, **kw
        ):
            seen["timeout"] = kw.get("timeout")
            seen["request"] = pb.InvokeToolRequest.FromString(payload)
            return pb.InvokeToolResponse(result_json=b"1")

        async def overflowing(
            subject, payload, headers, response_type, trace, *, timeout
        ):
            return await exchange(
                subject, payload, headers, response_type, timeout=timeout
            )

        transport._overflowing = overflowing
        transport.token = SimpleNamespace(
            for_audience=lambda audience: "bound", __call__=lambda: "t"
        )
        await transport.call(
            "abi.mod.acme.i-1.tool.lookup.invoke",
            pb.InvokeToolRequest(),
            pb.InvokeToolResponse,
            instance_id="i-1",
            timeout=4,
        )
        assert seen["timeout"] == 4
        assert seen["request"].context.timeout_ms == 4000
        with pytest.raises(ValueError):
            await transport.call(
                "abi.mod.acme.i-1.tool.lookup.invoke",
                pb.InvokeToolRequest(),
                pb.InvokeToolResponse,
                instance_id="i-1",
                timeout=0,
            )

    asyncio.run(scenario())


# --------------------------------------------------------------- cancellation
def cancel_request(call_id="c1"):
    return pb.CancelToolRequest(call_id=call_id).SerializeToString()


def cancel(tool_host, call_id="c1", token="token"):
    return tool_host.respond_cancel(
        "lookup", cancel_request(call_id), {"Nats-Auth-Token": token}
    )


async def until(condition, seconds=5.0):
    deadline = asyncio.get_running_loop().time() + seconds
    while not condition():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.005)


def test_a_cancelled_async_handler_is_really_cancelled_at_its_await():
    state = {"finished": False, "cleaned": False}

    async def scenario():
        started = asyncio.Event()

        async def slow(arguments, call):
            started.set()
            try:
                await asyncio.sleep(30)
                state["finished"] = True
            finally:
                state["cleaned"] = True

        tool_host, _ = host(slow)
        running = asyncio.ensure_future(
            tool_host.respond(
                "lookup",
                request(call_id="c1").SerializeToString(),
                {"Nats-Auth-Token": "token"},
            )
        )
        await started.wait()
        answer = await cancel(tool_host)
        assert answer.cancelled and not answer.error.code
        response = await asyncio.wait_for(running, 5)
        assert response.error.code == "CANCELLED"
        assert state["cleaned"] and not state["finished"]

    asyncio.run(scenario())


def test_a_cancelled_synchronous_handler_is_told_and_the_wait_ends():
    state = {"seen": None}

    async def scenario():
        started, done = threading.Event(), threading.Event()

        def slow(arguments, call):
            started.set()
            # Both ways of reading it name the same token.
            state["seen"] = call.cancellation.wait(30)
            state["same"] = call.cancellation is current_cancellation()
            done.set()

        tool_host, _ = host(slow)
        running = asyncio.ensure_future(
            tool_host.respond(
                "lookup",
                request(call_id="c1").SerializeToString(),
                {"Nats-Auth-Token": "token"},
            )
        )
        await until(started.is_set)
        started_at = asyncio.get_running_loop().time()
        assert (await cancel(tool_host)).cancelled
        response = await asyncio.wait_for(running, 5)
        assert response.error.code == "CANCELLED"
        assert await asyncio.to_thread(done.wait, 5)
        assert asyncio.get_running_loop().time() - started_at < 5
        assert state["seen"] is True and state["same"] is True

    asyncio.run(scenario())


def test_a_synchronous_handler_that_raises_toolcancelled_is_cancelled_not_failed():
    async def scenario():
        started = threading.Event()

        def slow(arguments, call):
            started.set()
            call.cancellation.wait(30)
            call.cancellation.raise_if_cancelled()  # raises ToolCancelled

        tool_host, _ = host(slow)
        running = asyncio.ensure_future(
            tool_host.respond(
                "lookup",
                request(call_id="c1").SerializeToString(),
                {"Nats-Auth-Token": "token"},
            )
        )
        await until(started.is_set)
        await cancel(tool_host)
        assert (await asyncio.wait_for(running, 5)).error.code == "CANCELLED"

    asyncio.run(scenario())


def test_only_the_identity_that_started_a_call_can_cancel_it():
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def slow(arguments, call):
            started.set()
            await release.wait()
            return "done"

        session = Session("engine")
        tool_host, _ = host(slow, session=session)
        running = asyncio.ensure_future(
            tool_host.respond(
                "lookup",
                request(call_id="c1").SerializeToString(),
                {"Nats-Auth-Token": "token"},
            )
        )
        await started.wait()
        session.identity = "partner"
        stranger = await cancel(tool_host)
        assert not stranger.cancelled and not stranger.error.code
        assert not running.done()
        session.identity = "engine"
        release.set()
        assert json.loads((await running).result_json) == "done"

    asyncio.run(scenario())


def test_cancelling_an_unknown_or_finished_call_answers_false():
    async def scenario():
        tool_host, _ = host()
        assert not (await cancel(tool_host, "nothing")).cancelled
        response = await tool_host.respond(
            "lookup",
            request(call_id="c2").SerializeToString(),
            {"Nats-Auth-Token": "token"},
        )
        assert not response.error.code
        assert not (await cancel(tool_host, "c2")).cancelled

    asyncio.run(scenario())


def test_a_cancel_that_arrives_before_its_call_cancels_it_when_it_does():
    async def scenario():
        tool_host, calls = host()
        assert not (await cancel(tool_host, "early")).cancelled
        response = await tool_host.respond(
            "lookup",
            request(call_id="early").SerializeToString(),
            {"Nats-Auth-Token": "token"},
        )
        assert response.error.code == "CANCELLED"
        assert calls == []  # the handler never ran

    asyncio.run(scenario())


def test_a_call_id_running_twice_is_refused_and_a_bad_one_too():
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def slow(arguments, call):
            started.set()
            await release.wait()
            return 1

        tool_host, _ = host(slow)
        first = asyncio.ensure_future(
            tool_host.respond(
                "lookup",
                request(call_id="same").SerializeToString(),
                {"Nats-Auth-Token": "token"},
            )
        )
        await started.wait()
        second = await tool_host.respond(
            "lookup",
            request(call_id="same").SerializeToString(),
            {"Nats-Auth-Token": "token"},
        )
        assert second.error.code == "INVALID_ARGUMENT"
        bad = await tool_host.respond(
            "lookup",
            request(call_id="no spaces").SerializeToString(),
            {"Nats-Auth-Token": "token"},
        )
        assert bad.error.code == "INVALID_ARGUMENT"
        release.set()
        assert not (await first).error.code
        # The id is free again.
        again = await tool_host.respond(
            "lookup",
            request(call_id="same").SerializeToString(),
            {"Nats-Auth-Token": "token"},
        )
        assert not again.error.code

    asyncio.run(scenario())


def test_a_cancel_is_authenticated_like_a_call():
    async def scenario():
        tool_host, _ = host(session=Session(refuse="UNAUTHENTICATED"))
        answer = await cancel(tool_host)
        assert answer.error.code == "UNAUTHENTICATED" and not answer.cancelled
        malformed = await host()[0].respond_cancel("lookup", b"\xff\xff", {})
        assert malformed.error.code == "INVALID_ARGUMENT"
        bad_id = await host()[0].respond_cancel(
            "lookup", cancel_request("not valid!"), {"Nats-Auth-Token": "t"}
        )
        assert bad_id.error.code == "INVALID_ARGUMENT"

    asyncio.run(scenario())


def test_the_deadline_stops_the_handler_too():
    state = {"cleaned": False, "told": None}

    async def scenario():
        async def slow(arguments, call):
            try:
                await asyncio.sleep(30)
            finally:
                state["cleaned"] = True

        tool_host, _ = host(slow)
        value = request(call_id="d1")
        value.context.timeout_ms = 50
        response = await tool_host.respond(
            "lookup", value.SerializeToString(), {"Nats-Auth-Token": "token"}
        )
        assert response.error.code == "DEADLINE_EXCEEDED"
        assert state["cleaned"]

        told = threading.Event()

        def blocking(arguments, call):
            state["told"] = call.cancellation.wait(30)
            told.set()

        tool_host, _ = host(blocking)
        response = await tool_host.respond(
            "lookup", value.SerializeToString(), {"Nats-Auth-Token": "token"}
        )
        assert response.error.code == "DEADLINE_EXCEEDED"
        assert await asyncio.to_thread(told.wait, 5) and state["told"] is True

    asyncio.run(scenario())


def test_a_call_without_an_id_runs_as_before():
    async def scenario():
        tool_host, _ = host()
        response = await tool_host.respond(
            "lookup", request().SerializeToString(), {"Nats-Auth-Token": "token"}
        )
        assert not response.error.code
        # An empty id names nothing: a cancel for it is a malformed request.
        assert (await cancel(tool_host, "")).error.code == "INVALID_ARGUMENT"

    asyncio.run(scenario())


def test_closing_the_host_cancels_the_handlers_it_runs():
    state = {"cleaned": False}

    async def scenario():
        started = asyncio.Event()

        async def slow(arguments, call):
            started.set()
            try:
                await asyncio.sleep(30)
            finally:
                state["cleaned"] = True

        tool_host, _ = host(slow)
        running = asyncio.ensure_future(
            tool_host.respond(
                "lookup",
                request(call_id="c1").SerializeToString(),
                {"Nats-Auth-Token": "token"},
            )
        )
        await started.wait()
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert state["cleaned"]

    asyncio.run(scenario())


def test_start_subscribes_each_tool_to_its_cancel_subject_outside_the_call_limit():
    async def scenario():
        tool_host, _ = host(max_concurrency=1)
        subscribed = {}

        class Subscription:
            async def unsubscribe(self):
                return None

        class Connection:
            max_payload = 1 << 20

            async def subscribe(self, subject, cb):
                subscribed[subject] = cb
                return Subscription()

        async def connect():
            return Connection()

        tool_host.session.client.transport = SimpleNamespace(connect=connect)

        async def flushed(nc):
            return None

        import naas_abi_sdk.tool_host as module

        saved, module.flush_to_broker = module.flush_to_broker, flushed
        try:
            await tool_host.start()
        finally:
            module.flush_to_broker = saved
        assert set(subscribed) == {
            "abi.mod.acme.instance-1.tool.lookup.invoke",
            "abi.mod.acme.instance-1.tool.lookup.cancel",
        }
        # The cancel's callback is not the call callback: it does not wait for a slot.
        assert (
            subscribed["abi.mod.acme.instance-1.tool.lookup.cancel"]
            is not subscribed["abi.mod.acme.instance-1.tool.lookup.invoke"]
        )

    asyncio.run(scenario())


# ------------------------------------------------- the caller that gives up
class RecordingTransport:
    """What ModuleToolClient sees of the broker: calls recorded, one behaviour."""

    def __init__(self, behaviour):
        self.behaviour, self.calls = behaviour, []

    async def call(self, subject, request, response_type, **kwargs):
        self.calls.append((subject, request, response_type, kwargs))
        if subject.endswith(".cancel"):
            return pb.CancelToolResponse(cancelled=True)
        return await self.behaviour()


def _client(behaviour):
    from naas_abi_sdk.tools import ModuleToolClient

    transport = RecordingTransport(behaviour)
    return (
        ModuleToolClient(
            transport, tool_subject("acme", "instance-1", "lookup"), "instance-1"
        ),
        transport,
    )


def test_a_client_names_its_call_and_leaves_the_callers_request_alone():
    async def done():
        return pb.InvokeToolResponse(result_json=b"1")

    async def scenario():
        client, transport = _client(done)
        original = request()
        await client.invoke(original)
        ((_, sent, _, _),) = transport.calls
        assert sent.call_id and not original.call_id
        # A caller's own id is kept.
        await client.invoke(request(call_id="mine"))
        assert transport.calls[1][1].call_id == "mine"
        assert len(transport.calls) == 2  # no cancel after a call that answered

    asyncio.run(scenario())


def test_a_caller_that_is_cancelled_cancels_the_call_on_the_module():
    async def forever():
        await asyncio.sleep(30)

    async def scenario():
        client, transport = _client(forever)
        running = asyncio.ensure_future(client.invoke(request()))
        await until(lambda: transport.calls)
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        (_, sent, _, _), (subject, cancelled, response_type, kwargs) = transport.calls
        assert subject == "abi.mod.acme.instance-1.tool.lookup.cancel"
        assert cancelled.call_id == sent.call_id
        assert response_type is pb.CancelToolResponse
        assert kwargs["instance_id"] == "instance-1"

    asyncio.run(scenario())


def test_a_caller_whose_wait_ran_out_cancels_the_call_too():
    async def slow():
        raise asyncio.TimeoutError()

    async def scenario():
        client, transport = _client(slow)
        with pytest.raises(asyncio.TimeoutError):
            await client.invoke(request())
        assert transport.calls[1][0].endswith(".tool.lookup.cancel")

    asyncio.run(scenario())


def test_an_error_the_module_answered_is_not_followed_by_a_cancel():
    async def refused():
        raise RPCError("PERMISSION_DENIED", "no")

    async def scenario():
        client, transport = _client(refused)
        with pytest.raises(RPCError):
            await client.invoke(request())
        assert len(transport.calls) == 1

    asyncio.run(scenario())


def test_a_cancel_that_cannot_be_sent_never_hides_the_callers_exit():
    async def scenario():
        from naas_abi_sdk.tools import ModuleToolClient

        gate = asyncio.Event()

        class Broken:
            def __init__(self):
                self.calls = 0

            async def call(self, subject, request, response_type, **kwargs):
                self.calls += 1
                if subject.endswith(".cancel"):
                    raise ConnectionError("gone")
                gate.set()
                await asyncio.sleep(30)

        transport = Broken()
        client = ModuleToolClient(
            transport, tool_subject("acme", "instance-1", "lookup"), "instance-1"
        )
        running = asyncio.ensure_future(client.invoke(request()))
        await gate.wait()
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert transport.calls == 2

    asyncio.run(scenario())
