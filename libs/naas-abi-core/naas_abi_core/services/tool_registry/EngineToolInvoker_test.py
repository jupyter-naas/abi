"""Running an engine tool for another process: every refusal, and no secret out.

No broker here; the same path over a real one is in
``engine/Engine_invoke_tools_nats_integration_test.py``.
"""

import asyncio
import json
import threading
import time

import pytest
from langchain_core.tools import StructuredTool, ToolException
from loguru import logger

from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.tool_registry import EngineToolInvoker as invoker_module
from naas_abi_core.services.tool_registry.EngineToolInvoker import (
    EngineToolInvoker,
    InvokeCaller,
    ToolInvocation,
    ToolInvokeError,
    scrub,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ConfigRequirement,
    PublishedTool,
    ToolDefinition,
    ToolRequirements,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)

CREDENTIAL = "ghp_platform_token_that_no_caller_may_ever_read"
OTHER = "sk-another-engine-secret-no-module-may-use"
DEFAULT_TOKEN = "ghp_the_modules_own_default_token_value"
GITHUB = "acme.github"
TRUSTED = InvokeCaller(
    "api",
    frozenset({"github:read", "github:admin"}),
    secrets=None,
    unscoped_tools=None,
)
MODULE = InvokeCaller(
    "partner",
    frozenset({"github:read"}),
    secrets=frozenset({"GITHUB_TOKEN"}),
    unscoped_tools=("acme.github/echo*",),
)


class Secrets:
    def __init__(self, values):
        self.values = values
        self.asked = []

    def resolve(self, key):
        self.asked.append(key)
        return self.values.get(key)


class Binding:
    """What a GitHub-style integration does: build a tool from a token."""

    def __init__(self, default_config=None, behaviour=None):
        self.default_config = (
            {"access_token": DEFAULT_TOKEN}
            if default_config is None
            else default_config
        )
        self.behaviour = behaviour or {}
        self.created = []

    def create(self, context, config):
        self.created.append((context, dict(config)))
        token = config.get("access_token", "")
        behaviour = self.behaviour

        def run(**arguments):
            if "wait" in behaviour:
                behaviour["wait"].wait(10)
            if "raise" in behaviour:
                raise behaviour["raise"]
            if "result" in behaviour:
                return behaviour["result"](token, arguments)
            return f"ok {arguments}"

        return StructuredTool.from_function(
            func=run,
            name="tool",
            description="A tool.",
            args_schema={
                "type": "object",
                "properties": {"repo": {"type": "string"}},
            },
        )


def definition(name, *, scopes=(), secret=True, remote=False, schema=None, **extra):
    return ToolDefinition(
        namespace=GITHUB,
        name=name,
        description=f"{name} on GitHub",
        module=GITHUB,
        input_schema=schema
        or {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "maxLength": 20},
                "count": {"type": "integer", "minimum": 0},
            },
            "required": ["repo"],
            "additionalProperties": False,
        },
        required_scopes=tuple(scopes),
        remote=remote,
        requirements=ToolRequirements(
            config=(
                ConfigRequirement(key="access_token", secret=secret),
                ConfigRequirement(key="base_url", required=False),
            )
        ),
        **extra,
    )


@pytest.fixture
def bindings():
    return {
        "get_issue": Binding({"access_token": DEFAULT_TOKEN}),
        "echo_token": Binding(
            behaviour={"result": lambda token, arguments: f"token={token}"}
        ),
        "delete_repo": Binding({"access_token": DEFAULT_TOKEN}),
        "remote_tool": Binding(),
        "slow": Binding(behaviour={}),
        "fails": Binding(behaviour={"raise": ToolException(f"bad {CREDENTIAL}")}),
        "boom": Binding(
            behaviour={"raise": RuntimeError(f"HTTP 401 for {CREDENTIAL}")}
        ),
    }


@pytest.fixture
def registry(bindings):
    registry = ToolRegistryService()
    registry.publish(
        GITHUB,
        [
            PublishedTool(
                definition("get_issue", scopes=("github:read",)), bindings["get_issue"]
            ),
            PublishedTool(definition("echo_token"), bindings["echo_token"]),
            PublishedTool(
                definition("delete_repo", scopes=("github:admin",)),
                bindings["delete_repo"],
            ),
            PublishedTool(definition("not_granted"), Binding()),
            PublishedTool(
                definition("remote_tool", remote=True), bindings["remote_tool"]
            ),
            PublishedTool(definition("slow"), bindings["slow"]),
            PublishedTool(definition("fails"), bindings["fails"]),
            PublishedTool(definition("boom"), bindings["boom"]),
            PublishedTool(
                definition("plain", secret=False, scopes=("github:read",)),
                Binding(),
            ),
        ],
    )
    return registry


@pytest.fixture
def secrets():
    return Secrets({"GITHUB_TOKEN": CREDENTIAL, "OTHER_SECRET": OTHER})


@pytest.fixture
def logs():
    """Every line the engine logs, at any level (loguru, not stdlib logging)."""
    lines = []
    sink = logger.add(lines.append, level="DEBUG", format="{message}")
    yield lines
    logger.remove(sink)


@pytest.fixture
def events():
    return []


@pytest.fixture
def invoker(registry, secrets, events):
    invoker = EngineToolInvoker(
        registry, secrets, max_concurrent=2, record_activity=events.append
    )
    yield invoker
    invoker.close()


def call(invoker, caller, tool, arguments=None, *, config=None, refs=None, **extra):
    invocation = ToolInvocation(
        tool=f"{GITHUB}/{tool}",
        arguments=json.dumps(
            {"repo": "abi"} if arguments is None else arguments
        ).encode(),
        config=json.dumps(config).encode() if config is not None else b"",
        secret_refs=refs or {},
        **extra,
    )
    return asyncio.run(invoker.invoke(caller, invocation))


def refused(invoker, caller, tool, code, *args, **kwargs):
    with pytest.raises(ToolInvokeError) as raised:
        call(invoker, caller, tool, *args, **kwargs)
    assert raised.value.code == code, raised.value
    return raised.value


# ---------------------------------------------------------------- the happy path
def test_a_secret_reference_is_resolved_on_the_engine(invoker, bindings, secrets):
    result = call(invoker, MODULE, "get_issue", refs={"access_token": "GITHUB_TOKEN"})

    assert json.loads(result) == "ok {'repo': 'abi'}"
    # The tool was built with the engine's secret; the caller sent only its name.
    assert bindings["get_issue"].created[0][1]["access_token"] == CREDENTIAL
    assert secrets.asked == ["GITHUB_TOKEN"]


def test_the_module_default_runs_without_any_reference(invoker, bindings, events):
    call(invoker, TRUSTED, "get_issue")

    assert bindings["get_issue"].created[0][1]["access_token"] == DEFAULT_TOKEN


def test_literal_non_secret_configuration_reaches_the_tool(invoker, bindings):
    call(invoker, TRUSTED, "get_issue", config={"base_url": "https://ghe.example"})

    assert bindings["get_issue"].created[0][1]["base_url"] == "https://ghe.example"


def test_the_version_names_the_tool_when_the_reference_has_none(invoker):
    call(invoker, TRUSTED, "get_issue", version="1")
    refused(invoker, TRUSTED, "get_issue", "TOOL_NOT_FOUND", version="9")
    error = refused(invoker, TRUSTED, "get_issue@1", "INVALID_ARGUMENT", version="2")
    assert "different versions" in error.message


# -------------------------------------------------------------- access refusals
def test_a_caller_without_the_required_scopes_cannot_run_the_tool(invoker, bindings):
    refused(invoker, MODULE, "delete_repo", "TOOL_NOT_FOUND")
    refused(
        invoker,
        InvokeCaller("nobody", frozenset(), secrets=None),
        "get_issue",
        "TOOL_NOT_FOUND",
    )
    assert bindings["delete_repo"].created == []


def test_the_policy_refusal_of_a_visible_tool_is_permission_denied(
    registry, secrets, bindings
):
    from naas_abi_core.services.tool_registry.ToolRegistryPort import (
        IToolAccessPolicy,
        ToolAccessDeniedError,
        ToolAction,
    )

    class ReadOnly(IToolAccessPolicy):
        def check(self, definition, context, action):
            if action is ToolAction.EXECUTE:
                raise ToolAccessDeniedError("no executing: it names github:read")

    registry._access_policy = ReadOnly()
    invoker = EngineToolInvoker(registry, secrets)
    error = refused(invoker, TRUSTED, "get_issue", "PERMISSION_DENIED")
    assert "github:read" not in error.message
    invoker.close()


def test_a_tool_that_needs_no_scope_is_denied_to_a_module_unless_granted(
    invoker, bindings
):
    error = refused(invoker, MODULE, "not_granted", "PERMISSION_DENIED")
    assert "not granted" in error.message
    # The grant is a pattern on <namespace>/<name>.
    call(invoker, MODULE, "echo_token", refs={"access_token": "GITHUB_TOKEN"})
    # The engine's own processes are not held to it.
    call(invoker, TRUSTED, "not_granted")


def test_a_tool_a_module_serves_is_not_run_through_the_engine(invoker, bindings):
    refused(invoker, TRUSTED, "remote_tool", "PERMISSION_DENIED")
    assert bindings["remote_tool"].created == []


def test_an_unknown_tool_is_not_found(invoker):
    refused(invoker, TRUSTED, "missing", "TOOL_NOT_FOUND")
    with pytest.raises(ToolInvokeError) as raised:
        asyncio.run(invoker.invoke(TRUSTED, ToolInvocation(tool="not a reference")))
    assert raised.value.code == "INVALID_ARGUMENT"
    with pytest.raises(ToolInvokeError):
        asyncio.run(invoker.invoke(TRUSTED, ToolInvocation(tool="")))


def test_only_the_engines_own_processes_may_name_a_user_or_a_workspace(invoker):
    refused(invoker, MODULE, "get_issue", "PERMISSION_DENIED", user_id="user-1")
    refused(invoker, MODULE, "get_issue", "PERMISSION_DENIED", workspace_id="w-1")
    refused(
        invoker,
        InvokeCaller("dagster", secrets=None, unscoped_tools=None),
        "echo_token",
        "PERMISSION_DENIED",
        user_id="user-1",
    )
    user_caller = InvokeCaller(
        "engine", secrets=None, unscoped_tools=None, may_name_user=True
    )
    call(invoker, user_caller, "echo_token", user_id="user-1", workspace_id="w-1")


def test_the_context_of_the_tool_carries_the_verified_scopes_and_user(
    invoker, bindings
):
    caller = InvokeCaller(
        "api",
        frozenset({"github:read"}),
        secrets=None,
        unscoped_tools=None,
        may_name_user=True,
    )
    call(invoker, caller, "get_issue", user_id="user-7")

    context = bindings["get_issue"].created[0][0]
    assert context.user_id == "user-7"
    assert context.scopes == {"github:read"}


# ------------------------------------------------------------------- secrets
def test_a_secret_the_caller_may_not_use_is_refused_before_any_lookup(
    invoker, secrets, bindings
):
    error = refused(
        invoker,
        MODULE,
        "get_issue",
        "PERMISSION_DENIED",
        refs={"access_token": "OTHER_SECRET"},
    )

    assert secrets.asked == []
    assert OTHER not in error.message
    assert bindings["get_issue"].created == []
    # A name nobody holds is refused the same way: nothing says which exist.
    refused(
        invoker, MODULE, "get_issue", "PERMISSION_DENIED", refs={"access_token": "NOPE"}
    )


def test_a_module_without_a_grant_references_no_secret(invoker, secrets):
    nobody = InvokeCaller("stranger", frozenset({"github:read"}))
    refused(
        invoker,
        nobody,
        "get_issue",
        "PERMISSION_DENIED",
        refs={"access_token": "GITHUB_TOKEN"},
    )
    assert secrets.asked == []


def test_inline_credentials_are_refused(invoker, bindings):
    error = refused(
        invoker,
        TRUSTED,
        "get_issue",
        "PERMISSION_DENIED",
        config={"access_token": "ghp_inline_value"},
    )

    assert "ghp_inline_value" not in error.message
    assert bindings["get_issue"].created == []


def test_a_secret_goes_only_to_a_key_the_tool_marks_secret(invoker, secrets):
    refused(
        invoker,
        TRUSTED,
        "plain",
        "INVALID_ARGUMENT",
        refs={"access_token": "GITHUB_TOKEN"},
    )
    refused(
        invoker,
        TRUSTED,
        "get_issue",
        "INVALID_ARGUMENT",
        refs={"base_url": "GITHUB_TOKEN"},
    )
    refused(
        invoker,
        TRUSTED,
        "get_issue",
        "INVALID_ARGUMENT",
        refs={"undeclared": "GITHUB_TOKEN"},
    )
    assert secrets.asked == []


def test_a_key_is_given_by_value_or_by_secret_not_both(invoker):
    # (an inline credential is refused first; a secret key sent as an empty string is not one)
    refused(
        invoker,
        TRUSTED,
        "get_issue",
        "PERMISSION_DENIED",
        config={"access_token": "x"},
        refs={"access_token": "GITHUB_TOKEN"},
    )


@pytest.mark.parametrize("name", ["", "has space", "1LEADING", "a" * 129, "../etc"])
def test_a_secret_reference_is_a_secret_name(invoker, name):
    refused(
        invoker, TRUSTED, "get_issue", "INVALID_ARGUMENT", refs={"access_token": name}
    )


def test_a_secret_that_is_not_set_is_reported_by_name_only(invoker):
    error = refused(
        invoker,
        TRUSTED,
        "get_issue",
        "INVALID_ARGUMENT",
        refs={"access_token": "UNSET_SECRET"},
    )
    assert "UNSET_SECRET" in error.message


def test_at_most_sixteen_references(invoker):
    refs = {f"key{i}": "GITHUB_TOKEN" for i in range(17)}
    refused(invoker, TRUSTED, "get_issue", "INVALID_ARGUMENT", refs=refs)


# ------------------------------------------------------------ never in the output
def test_a_tool_that_echoes_its_credential_returns_it_redacted(invoker, events):
    result = call(invoker, MODULE, "echo_token", refs={"access_token": "GITHUB_TOKEN"})

    assert CREDENTIAL not in result.decode()
    assert json.loads(result) == "token=[redacted]"


def test_the_modules_default_credential_is_redacted_too(invoker, bindings):
    bindings["get_issue"].behaviour["result"] = lambda token, arguments: {
        "echo": [token, {"nested": f"Bearer {token}"}]
    }

    result = call(invoker, TRUSTED, "get_issue")

    assert DEFAULT_TOKEN not in result.decode()
    assert json.loads(result) == {
        "echo": ["[redacted]", {"nested": "Bearer [redacted]"}]
    }


def test_a_tool_error_message_is_scrubbed(invoker):
    error = refused(
        invoker, TRUSTED, "fails", "TOOL_ERROR", refs={"access_token": "GITHUB_TOKEN"}
    )

    assert CREDENTIAL not in error.message
    assert error.message == "bad [redacted]"


def test_any_other_failure_reports_nothing_of_the_tool(invoker, logs):

    error = refused(
        invoker, TRUSTED, "boom", "TOOL_ERROR", refs={"access_token": "GITHUB_TOKEN"}
    )

    assert error.message == "Tool execution failed"
    assert logs and CREDENTIAL not in "".join(logs)


def test_no_secret_value_appears_in_logs_or_activity(invoker, events, bindings, logs):

    call(invoker, MODULE, "echo_token", refs={"access_token": "GITHUB_TOKEN"})
    refused(
        invoker, TRUSTED, "fails", "TOOL_ERROR", refs={"access_token": "GITHUB_TOKEN"}
    )
    refused(
        invoker,
        MODULE,
        "get_issue",
        "PERMISSION_DENIED",
        refs={"access_token": "OTHER_SECRET"},
    )

    assert len(logs) >= 3
    everything = "".join(logs) + repr(events)
    for secret in (CREDENTIAL, OTHER, DEFAULT_TOKEN):
        assert secret not in everything


def test_a_binding_failure_does_not_leak_what_it_was_built_with(registry, secrets):
    class Leaky:
        default_config = {}

        def create(self, context, config):
            raise RuntimeError(f"cannot connect with {config['access_token']}")

    registry.publish(
        "acme.leaky",
        [
            PublishedTool(
                definition("leak").model_copy(
                    update={"namespace": "acme.leaky", "module": "acme.leaky"}
                ),
                Leaky(),
            )
        ],
    )
    invoker = EngineToolInvoker(registry, secrets)

    with pytest.raises(ToolInvokeError) as raised:
        asyncio.run(
            invoker.invoke(
                TRUSTED,
                ToolInvocation(
                    tool="acme.leaky/leak",
                    arguments=b'{"repo": "abi"}',
                    secret_refs={"access_token": "GITHUB_TOKEN"},
                ),
            )
        )

    assert raised.value.code == "TOOL_ERROR"
    assert CREDENTIAL not in raised.value.message
    invoker.close()


def test_scrub_handles_every_json_shape_and_refuses_the_rest():
    value = {"a": ["xxxx-secret", 1, 2.5, True, None], "xxxx-secret": "k"}

    assert scrub(value, ["xxxx-secret", "ab"]) == {
        "a": ["[redacted]", 1, 2.5, True, None],
        "[redacted]": "k",
    }
    for bad in (b"bytes", {1: "int key"}, float("nan"), object()):
        with pytest.raises(TypeError):
            scrub(bad, [])


# ---------------------------------------------------------- arguments and sizes
def test_arguments_are_validated_against_the_input_schema(invoker, bindings):
    refused(invoker, TRUSTED, "get_issue", "INVALID_ARGUMENT", {})
    refused(invoker, TRUSTED, "get_issue", "INVALID_ARGUMENT", {"repo": 3})
    refused(invoker, TRUSTED, "get_issue", "INVALID_ARGUMENT", {"repo": "x" * 21})
    refused(
        invoker, TRUSTED, "get_issue", "INVALID_ARGUMENT", {"repo": "r", "count": -1}
    )
    refused(
        invoker, TRUSTED, "get_issue", "INVALID_ARGUMENT", {"repo": "r", "extra": 1}
    )
    assert bindings["get_issue"].created == []


@pytest.mark.parametrize(
    "raw", [b"[1]", b"not json", b'{"repo": NaN}', b'{"repo": Infinity}']
)
def test_arguments_are_a_finite_json_object(invoker, raw):
    with pytest.raises(ToolInvokeError) as raised:
        asyncio.run(
            invoker.invoke(
                TRUSTED, ToolInvocation(tool=f"{GITHUB}/get_issue", arguments=raw)
            )
        )
    assert raised.value.code == "INVALID_ARGUMENT"


def test_oversized_arguments_and_configuration_are_refused(invoker, bindings):
    with pytest.raises(ToolInvokeError) as raised:
        asyncio.run(
            invoker.invoke(
                TRUSTED,
                ToolInvocation(
                    tool=f"{GITHUB}/get_issue",
                    arguments=b'{"repo": "' + b"x" * (256 * 1024) + b'"}',
                ),
            )
        )
    assert raised.value.code == "PAYLOAD_TOO_LARGE"
    with pytest.raises(ToolInvokeError) as raised:
        asyncio.run(
            invoker.invoke(
                TRUSTED,
                ToolInvocation(
                    tool=f"{GITHUB}/get_issue",
                    arguments=b'{"repo": "r"}',
                    config=b'{"base_url": "' + b"x" * (64 * 1024) + b'"}',
                ),
            )
        )
    assert raised.value.code == "PAYLOAD_TOO_LARGE"
    assert bindings["get_issue"].created == []


def test_configuration_keys_must_be_declared_plain_values(invoker):
    refused(
        invoker, TRUSTED, "get_issue", "INVALID_ARGUMENT", config={"undeclared": "x"}
    )
    refused(
        invoker, TRUSTED, "get_issue", "INVALID_ARGUMENT", config={"base_url": {"a": 1}}
    )
    refused(
        invoker, TRUSTED, "get_issue", "INVALID_ARGUMENT", config={"base_url": ["a"]}
    )


def test_a_result_above_the_cap_is_refused(invoker, bindings):
    bindings["get_issue"].behaviour["result"] = lambda token, arguments: (
        "x" * (512 * 1024 + 1)
    )
    refused(invoker, TRUSTED, "get_issue", "PAYLOAD_TOO_LARGE")


def test_a_result_that_is_not_json_is_a_tool_error(invoker, bindings):
    bindings["get_issue"].behaviour["result"] = lambda token, arguments: object()
    refused(invoker, TRUSTED, "get_issue", "TOOL_ERROR")


def test_missing_required_configuration_is_reported_by_key(invoker, registry):
    registry.publish(
        "acme.strict",
        [
            PublishedTool(
                definition("strict").model_copy(
                    update={"namespace": "acme.strict", "module": "acme.strict"}
                ),
                Binding({}),
            )
        ],
    )
    with pytest.raises(ToolInvokeError) as raised:
        asyncio.run(
            invoker.invoke(
                TRUSTED,
                ToolInvocation(tool="acme.strict/strict", arguments=b'{"repo": "r"}'),
            )
        )
    assert raised.value.code == "INVALID_ARGUMENT"
    assert "access_token" in raised.value.message


# ------------------------------------------------------ deadline and admission
def test_a_deadline_ends_the_wait_and_keeps_the_slot_until_the_tool_returns(
    invoker, bindings
):
    gate = threading.Event()
    bindings["slow"].behaviour["wait"] = gate

    async def scenario():
        started = time.monotonic()
        with pytest.raises(ToolInvokeError) as raised:
            await invoker.invoke(
                TRUSTED,
                ToolInvocation(
                    tool=f"{GITHUB}/slow", arguments=b'{"repo": "r"}', timeout_ms=100
                ),
            )
        assert raised.value.code == "DEADLINE_EXCEEDED"
        assert time.monotonic() - started < 5
        assert invoker.in_flight == 1
        gate.set()
        for _ in range(100):
            if invoker.in_flight == 0:
                break
            await asyncio.sleep(0.02)
        assert invoker.in_flight == 0

    asyncio.run(scenario())


def test_calls_beyond_the_limit_are_refused_not_queued(invoker, bindings):
    gate = threading.Event()
    bindings["slow"].behaviour["wait"] = gate

    async def scenario():
        slow = ToolInvocation(tool=f"{GITHUB}/slow", arguments=b'{"repo": "r"}')
        running = [
            asyncio.ensure_future(invoker.invoke(TRUSTED, slow)) for _ in range(2)
        ]
        for _ in range(100):
            if invoker.in_flight == 2:
                break
            await asyncio.sleep(0.02)
        with pytest.raises(ToolInvokeError) as raised:
            await invoker.invoke(TRUSTED, slow)
        assert raised.value.code == "RESOURCE_EXHAUSTED"
        assert raised.value.retryable
        gate.set()
        await asyncio.gather(*running)
        await invoker.invoke(TRUSTED, slow)

    asyncio.run(scenario())


def test_the_deadline_is_clamped(registry, secrets):
    seen = []
    invoker = EngineToolInvoker(registry, secrets, default_timeout=7, max_timeout=9)

    async def scenario():
        original = asyncio.wait_for

        async def spy(awaitable, timeout):
            seen.append(timeout)
            return await original(awaitable, timeout)

        invoker_module.asyncio.wait_for = spy
        try:
            for ms in (0, 1000, 10_000_000):
                await invoker.invoke(
                    TRUSTED,
                    ToolInvocation(
                        tool=f"{GITHUB}/echo_token",
                        arguments=b'{"repo": "r"}',
                        timeout_ms=ms,
                    ),
                )
        finally:
            invoker_module.asyncio.wait_for = original

    asyncio.run(scenario())
    assert seen == [7, 1, 9]
    invoker.close()


def test_a_default_deadline_above_the_cap_is_lowered_to_it(registry, secrets):
    seen = []
    invoker = EngineToolInvoker(registry, secrets, default_timeout=60, max_timeout=30)

    async def scenario():
        original = asyncio.wait_for

        async def spy(awaitable, timeout):
            seen.append(timeout)
            return await original(awaitable, timeout)

        invoker_module.asyncio.wait_for = spy
        try:
            for ms in (0, 20_000, 120_000):
                await invoker.invoke(
                    TRUSTED,
                    ToolInvocation(
                        tool=f"{GITHUB}/echo_token",
                        arguments=b'{"repo": "r"}',
                        timeout_ms=ms,
                    ),
                )
        finally:
            invoker_module.asyncio.wait_for = original

    asyncio.run(scenario())
    assert seen == [30, 20, 30]
    invoker.close()


def test_the_contracts_limits_are_declared_once():
    from naas_abi_sdk import tools

    assert invoker_module.MAX_ARGUMENTS_BYTES is tools.MAX_ARGUMENTS_BYTES
    assert invoker_module.MAX_SECRET_REFS is tools.MAX_SECRET_REFS
    assert invoker_module.SECRET_NAME == tools.SECRET_NAME


@pytest.mark.parametrize(
    "name",
    ["create_issue", "a b", "a__b", "x.y", "héllo", "", "ok-name_1", "!!"],
)
def test_the_sdk_proxy_names_tools_as_the_publisher_does(name):
    from naas_abi_sdk.engine_tools import model_facing_name as sdk_name

    from naas_abi_core.services.tool_registry.adapters.primary.LangChainToolPublisher import (
        model_facing_name,
    )

    assert sdk_name(name) == model_facing_name(name)


# -------------------------------------------------------------------- activity
def test_each_call_leaves_one_activity_event_without_arguments_or_secrets(
    invoker, events
):
    call(
        invoker,
        MODULE,
        "echo_token",
        refs={"access_token": "GITHUB_TOKEN"},
        trace_id="trace-1",
    )
    refused(invoker, MODULE, "delete_repo", "TOOL_NOT_FOUND")

    ok, denied = events
    assert isinstance(ok, ActivityEvent)
    assert ok.actor_id == "service:partner"
    assert ok.event_type == "tool_registry.invoke"
    assert ok.correlation_id == "trace-1"
    assert ok.attributes["outcome"] == "ok"
    assert ok.attributes["tool"] == f"{GITHUB}/echo_token"
    assert denied.attributes["outcome"] == "error"
    assert denied.attributes["code"] == "TOOL_NOT_FOUND"
    assert "GITHUB_TOKEN" not in repr(events) and "abi" not in repr(
        [e.attributes for e in events]
    )


def test_a_failing_activity_log_never_fails_the_call(registry, secrets):
    def broken(event):
        raise RuntimeError("log down")

    invoker = EngineToolInvoker(registry, secrets, record_activity=broken)
    call(invoker, TRUSTED, "echo_token")
    invoker.close()
