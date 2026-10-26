"""Remote callers run engine tools, on a real broker (docs/adr/20261023_remote-callers-run-engine-tools.md).

The engine holds GitHub-style tools (a module token as its default, a credential key a
caller may only name) and serves ``abi.svc.tool_registry.v1.invoke_tool``. An SDK
module, logged in as the broker's ``module`` user, finds them by search, binds one as a
LangChain tool in an SDK agent and runs it: the engine checks the module's verified
identity, resolves the secret reference on the engine and runs the tool there. The
refusals, and that no credential is ever sent back, are checked on the same path.
"""

import asyncio
import json
import threading
import time

import pytest
from loguru import logger
from naas_abi_core.engine.nats_auth import module_key
from naas_abi_core.engine.nats_test_server import (
    login,
    native_nats_server,
    nats_server_binary,
)

SECRET = "invoke-engine-tools-test-secret-at-least-32-bytes"
PROJECT = "invoke_tools"
PASSWORDS = {"abi": "invoke-tools-abi-password", "module": "invoke-tools-module-pw"}
# The module's own default token, and the engine secrets a caller can only name.
PLATFORM_TOKEN = "ghp_platform_default_token_no_caller_may_read"
ENGINE_TOKEN = "ghp_engine_secret_github_access_token_value"
OTHER_SECRET = "sk-another-engine-secret-no-module-may-use"
NAMESPACE = "github_probe"
CREATE = f"{NAMESPACE}/create_issue@1"
GRANTED = "partner"
UNGRANTED = "stranger"
TRUSTED = "trusted_partner"

ENGINE_MODULE = """
import asyncio
import threading

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.tools import StructuredTool
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import ConfigRequirement
from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
    concept_embedding_model,
)
from naas_abi_sdk.cancellation import current_cancellation

PLATFORM_TOKEN = "__PLATFORM_TOKEN__"
CALLS = []
# What the two tools that wait until they are cancelled saw (the test reads it).
PROBE = {"started": threading.Event(), "cleaned": threading.Event(), "told": None}


async def wait_async(**arguments):
    PROBE["started"].set()
    try:
        await asyncio.sleep(60)
    finally:
        PROBE["cleaned"].set()


def wait_sync(**arguments):
    PROBE["started"].set()
    PROBE["told"] = current_cancellation().wait(60)
    PROBE["cleaned"].set()
    return "stopped"


def make(name, description, properties, required, token, body):
    def run(**arguments):
        CALLS.append((name, token, dict(arguments)))
        return body(token, arguments)

    return StructuredTool(
        name=name,
        description=description,
        args_schema={
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        func=run,
    )


def tools(config):
    token = config["access_token"]
    repo = {"repo": {"type": "string", "maxLength": 100}}
    return [
        make(
            "create_issue",
            "Create a new issue to report a bug in a GitHub repository.",
            {**repo, "title": {"type": "string"}},
            ["repo", "title"],
            token,
            lambda t, a: {"url": f"https://github.com/{a['repo']}/issues/1", "title": a["title"]},
        ),
        make(
            "show_token",
            "Show the repository issues with the credential that was used.",
            repo,
            ["repo"],
            token,
            lambda t, a: f"issues of {a['repo']} fetched with token {t}",
        ),
        make(
            "delete_repo",
            "Delete a GitHub repository for good.",
            repo,
            ["repo"],
            token,
            lambda t, a: "deleted",
        ),
        make(
            "list_repos",
            "List all the repositories of the organisation.",
            {},
            [],
            token,
            lambda t, a: ["abi", "naas"],
        ),
        StructuredTool(
            name="wait_async",
            description="Wait without end, as a coroutine, until the call is cancelled.",
            args_schema={"type": "object", "properties": {}},
            coroutine=wait_async,
        ),
        StructuredTool(
            name="wait_sync",
            description="Wait without end, on a thread, until the call is cancelled.",
            args_schema={"type": "object", "properties": {}},
            func=wait_sync,
        ),
    ]


class ABIModule(BaseModule):
    dependencies = ModuleDependencies(modules=[], services=[])

    class Configuration(ModuleConfiguration):
        pass

    def on_load(self):
        registry = self._engine.services.model_registry
        registry.register("concepts", concept_embedding_model())
        registry.register(
            "probe-chat",
            ChatModel(
                model_id="fake", provider="fixture", model=FakeListChatModel(responses=["hi"])
            ),
        )

    def publish_tools(self, publisher):
        requirement = [ConfigRequirement(key="access_token", secret=True)]
        defaults = {"access_token": PLATFORM_TOKEN}
        for scopes, include in (
            (("github:write",), ["create_issue", "wait_async", "wait_sync"]),
            (("github:read",), ["show_token"]),
            (("github:admin",), ["delete_repo"]),
            ((), ["list_repos"]),
        ):
            publisher.add_factory(
                tools,
                default_config=defaults,
                requirements=requirement,
                required_scopes=scopes,
                include=include,
            )
""".replace("__PLATFORM_TOKEN__", PLATFORM_TOKEN)

MODULES = {
    GRANTED: "{secrets: [GITHUB_ACCESS_TOKEN]}",
    TRUSTED: f"{{secrets: [GITHUB_ACCESS_TOKEN], unscoped_tools: ['{NAMESPACE}/list_*']}}",
}


@pytest.fixture
def engine_dir(tmp_path, monkeypatch):
    package = tmp_path / "modules" / NAMESPACE
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(ENGINE_MODULE)
    monkeypatch.syspath_prepend(str(tmp_path / "modules"))
    work = tmp_path / "engine"
    work.mkdir()
    (work / ".env").write_text(
        f"GITHUB_ACCESS_TOKEN={ENGINE_TOKEN}\nOTHER_ENGINE_SECRET={OTHER_SECRET}\n"
    )
    monkeypatch.chdir(work)
    yield work
    import sys

    sys.modules.pop(NAMESPACE, None)


@pytest.fixture
def broker(tmp_path):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with native_nats_server(tmp_path, jetstream=True, users=PASSWORDS) as url:
        yield url


def engine_config(url, *, invoke=None, scopes=None):
    modules = ", ".join(f"{name}: {grant}" for name, grant in MODULES.items())
    scopes = scopes or {
        GRANTED: ["github:read", "github:write"],
        TRUSTED: ["github:read"],
        UNGRANTED: [],
    }
    return (
        "api: {}\n"
        "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
        f"modules: [{{module: {NAMESPACE}, enabled: true, config: {{}}}}]\n"
        "services:\n"
        "  secret: {secret_adapters: [{adapter: dotenv, config: {path: .env, read_only: true}}]}\n"
        "  model_registry: {default_embedding_model: concepts, default_chat_model: probe-chat}\n"
        "  tool_registry: {collection_prefix: invoke_tools}\n"
        f"nats: {{nats_url: '{login(url, 'abi', PASSWORDS['abi'])}', jwt_secret: {SECRET}, "
        f"discovery: {{project: {PROJECT}}}, "
        f"tool_registry: {{remote_modules: {{enabled: false}}, "
        f"module_scopes: {json.dumps(scopes)}, "
        f"invoke: {invoke or '{modules: {' + modules + '}}'}}}}}\n"
    )


@pytest.fixture
def serving(engine_dir, broker):
    from naas_abi_core.engine.Engine import Engine

    engine = Engine(engine_config(broker))
    engine.load()
    yield engine
    engine.shutdown()


@pytest.fixture
def calls(serving):
    import sys

    module = sys.modules[NAMESPACE]
    module.CALLS.clear()
    return module.CALLS


@pytest.fixture
def logs():
    lines = []
    sink = logger.add(lines.append, level="DEBUG", format="{message}")
    yield lines
    logger.remove(sink)


# ------------------------------------------------------------ what crosses the wire
WIRE: list[tuple[bytes, bytes]] = []


@pytest.fixture(autouse=True)
def record_wire(monkeypatch):
    """Every invoke request an SDK module sends, and what came back (bytes)."""
    from naas_abi_sdk.tool_registry import ToolRegistryClient
    from naas_abi_sdk.transport import RPCError

    WIRE.clear()
    original = ToolRegistryClient.invoke_tool

    async def recording(self, request, **kwargs):
        try:
            response = await original(self, request, **kwargs)
        except RPCError as exc:
            WIRE.append((request.SerializeToString(), str(exc).encode()))
            raise
        WIRE.append((request.SerializeToString(), response.SerializeToString()))
        return response

    monkeypatch.setattr(ToolRegistryClient, "invoke_tool", recording)


def never_on_the_wire():
    wire = b"".join(request + response for request, response in WIRE)
    for value in (ENGINE_TOKEN, PLATFORM_TOKEN, OTHER_SECRET, SECRET):
        assert value.encode() not in wire


# ----------------------------------------------------------------- an SDK module
INSTANCES: list = []


def build_module():
    from naas_abi_sdk import BaseModule, ModuleDependencies

    class Partner(BaseModule):
        dependencies = ModuleDependencies(services=("tool_registry",))

        def on_initialized(self):
            INSTANCES.append(self)

        async def run(self):
            await asyncio.Event().wait()

    Partner.module_id = GRANTED
    return Partner


class RunningModule:
    """An SDK module process, as the broker's ``module`` user, on its own thread."""

    def __init__(self, url):
        self.url = url
        self.loop = None
        self.task = None
        self.started = threading.Event()
        self.thread = threading.Thread(
            target=lambda: asyncio.run(self._main()), daemon=True
        )
        self.error = None

    async def _main(self):
        from naas_abi_sdk import DiscoveryConfiguration, run_module
        from naas_abi_sdk.service_token import ModuleToken

        self.loop = asyncio.get_running_loop()
        self.task = asyncio.ensure_future(
            run_module(
                build_module(),
                url=login(self.url, "module", PASSWORDS["module"]),
                token=ModuleToken(GRANTED, module_key(SECRET, GRANTED)),
                discovery=DiscoveryConfiguration(
                    project=PROJECT, refresh_seconds=0.2, startup_timeout=20
                ),
            )
        )
        self.started.set()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001 - reported to the test
            self.error = exc

    def start(self):
        INSTANCES.clear()
        self.thread.start()
        assert self.started.wait(10)
        deadline = time.monotonic() + 20
        while not INSTANCES and time.monotonic() < deadline:
            time.sleep(0.1)
        assert INSTANCES, "the module did not start"
        return self

    def run(self, scenario):
        """``scenario(module)`` on the module's own event loop."""
        return asyncio.run_coroutine_threadsafe(
            scenario(INSTANCES[-1]), self.loop
        ).result(60)

    def stop(self):
        if self.thread.is_alive() and self.loop is not None:
            self.loop.call_soon_threadsafe(self.task.cancel)
            self.thread.join(30)
        assert not self.thread.is_alive()
        assert self.error is None, self.error


@pytest.fixture
def partner(serving, broker):
    running = RunningModule(broker).start()
    yield running
    running.stop()


def as_module(url, identity, scenario):
    """``scenario(ToolRegistryService, ABIClient)`` as the SDK module ``identity``."""
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.service_token import ModuleToken
    from naas_abi_sdk.services.tool_registry import ToolRegistryService

    async def run():
        client = ABIClient(
            login(url, "module", PASSWORDS["module"]),
            ModuleToken(identity, module_key(SECRET, identity)),
            timeout=30,
        )
        try:
            return await scenario(ToolRegistryService(client.tool_registry), client)
        finally:
            await client.close()

    return asyncio.run(run())


# ------------------------------------------------------------------------ the tests
def test_an_sdk_agent_searches_binds_and_runs_an_engine_tool(
    serving, partner, calls, logs
):
    from langchain_core.messages import AIMessage
    from naas_abi_core.services.agent.tests.scripted_chat_model import (
        ScriptedChatModel,
        ScriptRecorder,
        tool_call,
    )
    from naas_abi_sdk.agents import Agent, AgentConfiguration

    async def scenario(module):
        registry = module.engine.services.tool_registry
        found = await registry.search_tools(
            "report a bug in our github repository", limit=3
        )
        top = found[0]
        # The proxy holds the definition, a secret NAME and nothing else.
        tool = await registry.as_tool(
            top, secrets={"access_token": "GITHUB_ACCESS_TOKEN"}
        )
        recorder = ScriptRecorder(
            [
                tool_call(
                    tool.name, {"repo": "naas/abi", "title": "Login fails"}, "call-1"
                ),
                AIMessage(content="Issue opened."),
            ]
        )
        agent = Agent(
            "support",
            "Opens issues for customers",
            ScriptedChatModel(recorder=recorder),
            tools=[tool],
            enable_default_tools=False,
            configuration=AgentConfiguration(system_prompt="You are under test."),
        )
        answer = await agent.invoke("please open an issue about the login bug")
        return (
            top.tool_id,
            top.definition.remote,
            answer,
            [m.content for m in recorder.tool_messages()],
            recorder.bound[0],
            repr(recorder.seen),
        )

    tool_id, remote, answer, results, bound, seen = partner.run(scenario)

    assert tool_id == CREATE and remote is False
    assert answer == "Issue opened."
    assert bound == ["create_issue"]
    assert json.loads(results[0]) == {
        "url": "https://github.com/naas/abi/issues/1",
        "title": "Login fails",
    }
    # The tool ran in the engine, built with the engine's secret, which the module only named.
    assert calls == [
        ("create_issue", ENGINE_TOKEN, {"repo": "naas/abi", "title": "Login fails"})
    ]
    request = next(r for r, _ in WIRE)
    assert b"GITHUB_ACCESS_TOKEN" in request
    never_on_the_wire()
    for value in (ENGINE_TOKEN, PLATFORM_TOKEN):
        assert value not in seen and value not in "".join(logs)


def test_the_module_default_runs_with_no_reference_and_never_leaves(
    serving, broker, calls, logs
):
    async def scenario(registry, client):
        return await registry.invoke(f"{NAMESPACE}/show_token", {"repo": "naas/abi"})

    result = as_module(broker, GRANTED, scenario)

    # The tool echoed the credential it ran with: the engine scrubbed it.
    assert result == "issues of naas/abi fetched with token [redacted]"
    assert calls[0][1] == PLATFORM_TOKEN
    never_on_the_wire()
    assert PLATFORM_TOKEN not in "".join(logs)


def test_a_referenced_secret_the_tool_echoes_is_redacted(serving, broker, calls, logs):
    async def scenario(registry, client):
        return await registry.invoke(
            f"{NAMESPACE}/show_token",
            {"repo": "naas/abi"},
            secrets={"access_token": "GITHUB_ACCESS_TOKEN"},
        )

    result = as_module(broker, GRANTED, scenario)

    assert result == "issues of naas/abi fetched with token [redacted]"
    assert calls[0][1] == ENGINE_TOKEN
    never_on_the_wire()
    assert ENGINE_TOKEN not in "".join(logs)


def test_a_caller_without_the_required_scopes_is_refused(serving, broker, calls):
    from naas_abi_sdk.services.errors import ToolNotFound

    def refused(refs):
        async def scenario(registry, client):
            codes = []
            for ref in refs:
                with pytest.raises(ToolNotFound) as error:
                    await registry.invoke(ref, {"repo": "naas/abi", "title": "x"})
                codes.append(error.value.code)
            return codes

        return scenario

    # `partner` holds read and write, not admin; `stranger` holds nothing.
    assert as_module(broker, GRANTED, refused([f"{NAMESPACE}/delete_repo"])) == [
        "TOOL_NOT_FOUND"
    ]
    assert (
        as_module(
            broker,
            UNGRANTED,
            refused([f"{NAMESPACE}/delete_repo", CREATE.split("@")[0]]),
        )
        == ["TOOL_NOT_FOUND"] * 2
    )
    assert calls == []


def test_a_secret_the_caller_may_not_use_is_refused(serving, broker, calls):
    from naas_abi_sdk.services.errors import ToolNotFound, ToolPermissionDenied

    async def scenario(registry, client):
        messages = []
        # A secret the operator never listed for the module: the engine holds it, the
        # module may not name it. The engine's own signing secret included.
        for name in ("OTHER_ENGINE_SECRET", "NATS_JWT_SECRET", "NO_SUCH_SECRET"):
            with pytest.raises(ToolPermissionDenied) as error:
                await registry.invoke(
                    f"{NAMESPACE}/show_token",
                    {"repo": "naas/abi"},
                    secrets={"access_token": name},
                )
            messages.append(str(error.value))
        return messages

    messages = as_module(broker, GRANTED, scenario)

    # Refused before any lookup: all alike, whether or not the engine holds the name.
    assert all("may not use secret" in m for m in messages)
    assert all(OTHER_SECRET not in m and SECRET not in m for m in messages)

    async def unlisted(registry, client):
        # `stranger` holds no scope at all, so the tool is not even visible to it.
        with pytest.raises(ToolNotFound):
            await registry.invoke(
                f"{NAMESPACE}/show_token",
                {"repo": "naas/abi"},
                secrets={"access_token": "GITHUB_ACCESS_TOKEN"},
            )

    as_module(broker, UNGRANTED, unlisted)
    assert calls == []
    never_on_the_wire()


def test_inline_credentials_are_refused(serving, broker, calls):
    from naas_abi_sdk.services.errors import ToolPermissionDenied

    async def scenario(registry, client):
        with pytest.raises(ToolPermissionDenied) as error:
            await registry.invoke(
                f"{NAMESPACE}/show_token",
                {"repo": "naas/abi"},
                config={"access_token": "ghp_written_inline_by_the_module"},
            )
        return str(error.value)

    message = as_module(broker, GRANTED, scenario)

    assert "ghp_written_inline_by_the_module" not in message
    assert "secret_refs" in message
    assert calls == []


def test_oversized_and_invalid_arguments_are_refused_by_the_engine(
    serving, broker, calls
):
    from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb
    from naas_abi_sdk.transport import RPCError

    async def scenario(registry, client):
        codes = []
        for arguments in (
            b'{"repo": 1}',
            b"{}",
            b'{"repo": "r", "extra": true}',
            b'{"repo": "' + b"x" * 101 + b'"}',
            b"[1, 2]",
            b'{"repo": "' + b"x" * (256 * 1024) + b'"}',
        ):
            with pytest.raises(RPCError) as error:
                # Raw, past the facade's own checks: the engine is the authority.
                await client.tool_registry.invoke_tool(
                    pb.InvokeToolRequest(
                        tool=f"{NAMESPACE}/show_token", arguments_json=arguments
                    )
                )
            codes.append(error.value.code)
        huge_config = b'{"base_url": "' + b"x" * (64 * 1024) + b'"}'
        with pytest.raises(RPCError) as error:
            await client.tool_registry.invoke_tool(
                pb.InvokeToolRequest(
                    tool=f"{NAMESPACE}/show_token",
                    arguments_json=b'{"repo": "r"}',
                    config_json=huge_config,
                )
            )
        return codes + [error.value.code]

    assert as_module(broker, GRANTED, scenario) == [
        "INVALID_ARGUMENT",
        "INVALID_ARGUMENT",
        "INVALID_ARGUMENT",
        "INVALID_ARGUMENT",
        "INVALID_ARGUMENT",
        "PAYLOAD_TOO_LARGE",
        "PAYLOAD_TOO_LARGE",
    ]
    assert calls == []


def test_a_module_cannot_name_a_user_a_workspace_or_a_trusted_identity(
    serving, broker, calls
):
    from naas_abi_proto.common.v1 import common_pb2
    from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb
    from naas_abi_sdk.transport import RPCError

    async def scenario(registry, client):
        codes = []
        for context in (
            common_pb2.CallContext(principal_id="admin-user"),
            common_pb2.CallContext(workspace_id="someone-elses"),
            common_pb2.CallContext(tenant_id="other", principal_id="x"),
        ):
            with pytest.raises(RPCError) as error:
                await client.tool_registry.invoke_tool(
                    pb.InvokeToolRequest(
                        context=context,
                        tool=f"{NAMESPACE}/show_token",
                        arguments_json=b'{"repo": "r"}',
                    )
                )
            codes.append(error.value.code)
        return codes

    assert as_module(broker, GRANTED, scenario) == ["PERMISSION_DENIED"] * 3
    assert calls == []


def test_a_tool_that_needs_no_scope_runs_only_where_the_operator_granted_it(
    serving, broker, calls
):
    from naas_abi_sdk.services.errors import ToolPermissionDenied

    async def scenario(registry, client):
        return await registry.invoke(f"{NAMESPACE}/list_repos")

    async def refused(registry, client):
        with pytest.raises(ToolPermissionDenied):
            await registry.invoke(f"{NAMESPACE}/list_repos")

    as_module(broker, GRANTED, refused)
    assert calls == []
    assert as_module(broker, TRUSTED, scenario) == ["abi", "naas"]
    assert calls[0][1] == PLATFORM_TOKEN


def test_the_engines_own_processes_run_tools_too(serving, broker, calls):
    from naas_abi_core.engine.nats_auth import ServiceTokenSource
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.services.tool_registry import ToolRegistryService

    async def scenario():
        client = ABIClient(
            login(broker, "abi", PASSWORDS["abi"]),
            ServiceTokenSource("engine", SECRET),
            timeout=30,
        )
        try:
            registry = ToolRegistryService(client.tool_registry)
            # It holds every scope and any secret; unscoped tools are open to it.
            admin = await registry.invoke(
                f"{NAMESPACE}/delete_repo", {"repo": "naas/abi"}
            )
            repos = await registry.invoke(f"{NAMESPACE}/list_repos")
            return admin, repos
        finally:
            await client.close()

    assert asyncio.run(scenario()) == ("deleted", ["abi", "naas"])


def test_without_a_token_nothing_runs(serving, broker, calls):
    import nats
    from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb

    async def scenario():
        nc = await nats.connect(login(broker, "abi", PASSWORDS["abi"]))
        try:
            reply = await nc.request(
                "abi.svc.tool_registry.v1.invoke_tool",
                pb.InvokeToolRequest(
                    tool=f"{NAMESPACE}/delete_repo", arguments_json=b'{"repo": "r"}'
                ).SerializeToString(),
                timeout=10,
            )
            return pb.InvokeToolResponse.FromString(reply.data)
        finally:
            await nc.close()

    assert asyncio.run(scenario()).error.code == "UNAUTHENTICATED"
    assert calls == []


def test_a_busy_engine_refuses_instead_of_queueing(engine_dir, broker):
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_sdk.services.errors import ServiceError

    config = engine_config(
        broker,
        invoke=(
            "{max_concurrent: 1, modules: {partner: {secrets: [GITHUB_ACCESS_TOKEN]}}}"
        ),
    )
    engine = Engine(config)
    engine.load()
    try:
        import sys

        release = threading.Event()
        module = sys.modules[NAMESPACE]

        class Blocking(list):
            def append(self, item):
                super().append(item)
                release.wait(20)

        module.CALLS = Blocking()

        async def scenario(registry, client):
            first = asyncio.ensure_future(
                registry.invoke(f"{NAMESPACE}/show_token", {"repo": "r"}, timeout=30)
            )
            for _ in range(100):
                if module.CALLS:
                    break
                await asyncio.sleep(0.05)
            with pytest.raises(ServiceError) as error:
                await registry.invoke(
                    f"{NAMESPACE}/show_token", {"repo": "r"}, timeout=30
                )
            release.set()
            return error.value.code, await first

        code, result = as_module(broker, GRANTED, scenario)
        assert code == "RESOURCE_EXHAUSTED"
        assert "token" in result
    finally:
        release.set()
        engine.shutdown()


def test_a_tool_that_outlasts_its_deadline_is_deadline_exceeded(engine_dir, broker):
    import sys

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_sdk.services.errors import ServiceError

    engine = Engine(engine_config(broker))
    engine.load()
    release = threading.Event()
    try:
        module = sys.modules[NAMESPACE]

        class Blocking(list):
            def append(self, item):
                super().append(item)
                release.wait(30)

        module.CALLS = Blocking()

        async def scenario(registry, client):
            started = time.monotonic()
            with pytest.raises(ServiceError) as error:
                await registry.invoke(
                    f"{NAMESPACE}/show_token", {"repo": "r"}, timeout=1
                )
            return error.value.code, time.monotonic() - started

        code, seconds = as_module(broker, GRANTED, scenario)

        # The engine's own verdict, not the caller giving up at the same instant.
        assert code == "DEADLINE_EXCEEDED"
        assert 0.9 < seconds < 5
        never_on_the_wire()
    finally:
        release.set()
        engine.shutdown()


def test_the_operator_can_turn_running_tools_off(engine_dir, broker):
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_sdk.services.errors import ToolPermissionDenied

    engine = Engine(engine_config(broker, invoke="{enabled: false}"))
    engine.load()
    try:

        async def scenario(registry, client):
            with pytest.raises(ToolPermissionDenied):
                await registry.invoke(f"{NAMESPACE}/list_repos")

        as_module(broker, GRANTED, scenario)
    finally:
        engine.shutdown()


def test_no_python_object_crosses_the_wire(serving, broker, calls):
    """The request and the response are protobuf JSON bytes: nothing is pickled, and a
    tool's result is whatever JSON it returned."""
    from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb

    async def scenario(registry, client):
        return await registry.invoke(
            CREATE.split("@")[0], {"repo": "naas/abi", "title": "t"}, secrets={}
        )

    as_module(broker, GRANTED, scenario)

    request, response = WIRE[0]
    message = pb.InvokeToolRequest.FromString(request)
    assert json.loads(message.arguments_json) == {"repo": "naas/abi", "title": "t"}
    assert json.loads(pb.InvokeToolResponse.FromString(response).result_json)
    for payload in (request, response):
        assert b"\x80\x04" not in payload  # a pickle protocol marker
        assert b"pickle" not in payload and b"__reduce__" not in payload


# ------------------------------------------------------------------- cancelling
@pytest.fixture
def probe(serving):
    import sys

    probe = sys.modules[NAMESPACE].PROBE
    probe["started"].clear()
    probe["cleaned"].clear()
    probe["told"] = None
    return probe


@pytest.mark.parametrize("tool", ["wait_async", "wait_sync"])
def test_a_module_that_gives_up_cancels_the_engine_tool(serving, partner, probe, tool):
    """The module's task is cancelled; the engine stops the tool it runs for it: the
    coroutine at its await (its ``finally`` runs), the synchronous one through its
    cancellation."""

    async def scenario(module):
        registry = module.engine.services.tool_registry
        running = asyncio.ensure_future(registry.invoke(f"{NAMESPACE}/{tool}", {}))
        assert await asyncio.to_thread(probe["started"].wait, 15)
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        return await asyncio.to_thread(probe["cleaned"].wait, 15)

    assert partner.run(scenario) is True
    if tool == "wait_sync":
        assert probe["told"] is True


@pytest.mark.parametrize("tool", ["wait_async", "wait_sync"])
def test_the_deadline_stops_the_engine_tool_too(serving, partner, probe, tool):
    from naas_abi_sdk.services.errors import ServiceError

    async def scenario(module):
        registry = module.engine.services.tool_registry
        with pytest.raises(ServiceError) as raised:
            await registry.invoke(f"{NAMESPACE}/{tool}", {}, timeout=1)
        cleaned = await asyncio.to_thread(probe["cleaned"].wait, 15)
        return raised.value.code, cleaned

    code, cleaned = partner.run(scenario)
    assert code == "DEADLINE_EXCEEDED" and cleaned
    if tool == "wait_sync":
        assert probe["told"] is True


def test_a_module_cannot_cancel_a_call_it_did_not_start(
    serving, partner, probe, broker, monkeypatch
):
    """Another module's cancel, with the call's real id, tells nothing and stops
    nothing; the owner's own cancel does."""
    from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb
    from naas_abi_sdk.tool_registry import ToolRegistryClient

    ids: list[str] = []
    original = ToolRegistryClient.invoke_tool

    async def noting(self, request, **kwargs):
        ids.append(request.call_id)
        return await original(self, request, **kwargs)

    monkeypatch.setattr(ToolRegistryClient, "invoke_tool", noting)

    async def start(module):
        registry = module.engine.services.tool_registry
        running = asyncio.ensure_future(
            registry.invoke(f"{NAMESPACE}/wait_async", {}, timeout=30)
        )
        assert await asyncio.to_thread(probe["started"].wait, 15)
        return running

    async def stranger(registry, client):
        answer = await client.tool_registry.cancel_tool(
            pb.CancelToolRequest(call_id=ids[0])
        )
        return answer.cancelled, answer.HasField("error")

    running = partner.run(start)
    assert ids and ids[0]
    assert as_module(broker, UNGRANTED, stranger) == (False, False)
    time.sleep(0.3)
    assert not probe["cleaned"].is_set() and not running.done()

    async def owner(registry, client):
        answer = await client.tool_registry.cancel_tool(
            pb.CancelToolRequest(call_id=ids[0])
        )
        return answer.cancelled

    # The owner is the module that started it: the same identity, a new connection.
    assert as_module(broker, GRANTED, owner) is True
    assert probe["cleaned"].wait(15)
    partner.loop.call_soon_threadsafe(running.cancel)
