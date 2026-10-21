"""Tools an SDK module publishes, on a real broker (docs/adr/20261022_remote-module-tools.md).

An SDK module runs as the broker's ``module`` user, declares tools and serves them;
the engine, logged in as ``abi``, finds them through discovery and publishes them to
its tool registry while the module has a ready instance. Agents then search, enable
and call them over NATS, and the module decides who may run them.
"""

import asyncio
import json
import threading
import time

import pytest
from naas_abi_core.engine.nats_auth import (
    ServiceTokenSource,
    issue_service_token,
    module_key,
)
from naas_abi_core.engine.nats_test_server import (
    login,
    native_nats_server,
    nats_server_binary,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ToolAccessDeniedError,
    ToolAction,
    ToolContext,
    ToolNotFoundError,
)

SECRET = "remote-module-tools-test-secret-at-least-32-bytes"
CREDENTIAL = "sk-live-an-engine-secret-no-module-may-see"
PROJECT = "remote_tools"
MODULE = "acme_crm"
TICKET = f"{MODULE}/open_ticket@1"
FORECAST = f"{MODULE}/get_forecast@1"
CLOSE = f"{MODULE}/close_account@1"
PASSWORDS = {"abi": "remote-tools-abi-password", "module": "remote-tools-module-pw"}
USER = ToolContext(user_id="user-7")

ENGINE_MODULE = """
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
    concept_embedding_model,
)


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
                model_id="fake",
                provider="fixture",
                model=FakeListChatModel(responses=["hi"]),
            ),
        )
"""


@pytest.fixture
def engine_dir(tmp_path, monkeypatch):
    package = tmp_path / "modules" / "remote_probe"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(ENGINE_MODULE)
    monkeypatch.syspath_prepend(str(tmp_path / "modules"))
    work = tmp_path / "engine"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


@pytest.fixture
def broker(tmp_path):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with native_nats_server(tmp_path, jetstream=True, users=PASSWORDS) as url:
        yield url


def new_engine(url, *, role=None, remote="{refresh_seconds: 0.2}"):
    from naas_abi_core.engine.Engine import Engine

    settings = ", engine: {role: " + role + "}" if role else ""
    return Engine(
        "api: {}\n"
        "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
        "modules: [{module: remote_probe, enabled: true, config: {}}]\n"
        "services:\n"
        "  secret: {secret_adapters: []}\n"
        "  model_registry: {default_embedding_model: concepts, default_chat_model: probe-chat}\n"
        "  tool_registry: {collection_prefix: remote_tools}\n"
        f"nats: {{nats_url: '{login(url, 'abi', PASSWORDS['abi'])}', jwt_secret: {SECRET}, "
        f"discovery: {{project: {PROJECT}}}, "
        f"tool_registry: {{remote_modules: {remote}}}{settings}}}\n"
    )


@pytest.fixture
def serving(engine_dir, broker):
    engine = new_engine(broker)
    engine.load()
    yield engine
    engine.shutdown()


# ---------------------------------------------------------------- the SDK module

CALLS: list[tuple[dict, object]] = []
RECEIVED: list[tuple[bytes, dict]] = []


def build_module(*, authorize=None, module_id=MODULE):
    from naas_abi_sdk import (
        BaseModule,
        ToolConfig,
        ToolDescriptor,
        ToolError,
    )

    def open_ticket(arguments, call):
        CALLS.append((dict(arguments), call))
        return {
            "ticket": f"T-{len(CALLS)}",
            "title": arguments["title"],
            "region": call.config["region"],
            "caller": call.caller.identity,
            "user": call.caller.user_id,
        }

    async def get_forecast(arguments):
        if arguments["city"] == "Atlantis":
            raise ToolError("No such city")
        return f"Sunny in {arguments['city']}"

    class Crm(BaseModule):
        tools = (
            ToolDescriptor(
                "open_ticket",
                "Create a new ticket to report a bug or defect.",
                {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short title"},
                        "priority": {"type": "string", "enum": ["low", "high"]},
                    },
                    "required": ["title"],
                    "additionalProperties": False,
                },
                config=(ToolConfig("region", "Where the CRM runs"),),
            ),
            ToolDescriptor(
                "get_forecast",
                "Get the weather forecast for a city.",
                {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            ),
            ToolDescriptor(
                "close_account",
                "Close the account of a customer and send a receipt.",
                {"type": "object", "properties": {"account": {"type": "string"}}},
                required_scopes=("crm:admin",),
            ),
        )

        def on_initialized(self):
            self.expose_tool("open_ticket", open_ticket)
            self.expose_tool("get_forecast", get_forecast)
            self.expose_tool("close_account", lambda arguments: "closed")

        async def run(self):
            await asyncio.Event().wait()

    Crm.module_id = module_id
    if authorize is not None:
        Crm.authorize_tool = lambda self, name, caller: authorize(name, caller)
    return Crm


class RunningModule:
    """An SDK module process, as the broker's ``module`` user, on its own thread."""

    def __init__(self, url, module_type):
        self.url, self.module_type = url, module_type
        self.loop = None
        self.task = None
        self.started = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.error = None

    def _run(self):
        asyncio.run(self._main())

    async def _main(self):
        from naas_abi_sdk import DiscoveryConfiguration, run_module
        from naas_abi_sdk.service_token import ModuleToken

        module_id = self.module_type.module_id
        self.loop = asyncio.get_running_loop()
        self.task = asyncio.ensure_future(
            run_module(
                self.module_type,
                url=login(self.url, "module", PASSWORDS["module"]),
                token=ModuleToken(module_id, module_key(SECRET, module_id)),
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
        self.thread.start()
        assert self.started.wait(10)
        return self

    def stop(self):
        if self.thread.is_alive() and self.loop is not None:
            self.loop.call_soon_threadsafe(self.task.cancel)
            self.thread.join(30)
        assert not self.thread.is_alive()
        assert self.error is None, self.error


@pytest.fixture(autouse=True)
def clean_records():
    CALLS.clear()
    RECEIVED.clear()
    from naas_abi_sdk.tool_host import ToolHost

    original = ToolHost.respond

    async def recording(self, name, data, headers, **kwargs):
        RECEIVED.append((data, dict(headers)))
        return await original(self, name, data, headers, **kwargs)

    ToolHost.respond = recording
    yield
    ToolHost.respond = original


@pytest.fixture
def crm(serving, broker):
    running = RunningModule(broker, build_module()).start()
    wait_for(lambda: TICKET in published(serving))
    yield running
    running.stop()


def wait_for(predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("timed out waiting for the condition")


def published(engine) -> set[str]:
    return {str(d.id) for d in engine.services.tool_registry.list_definitions()}


# --------------------------------------------------------------------------- tests


def test_the_engines_search_finds_a_remote_tool_from_a_paraphrase(serving, crm):
    tools = serving.services.tool_registry
    found = tools.search_tools("report a defect in our software", USER, limit=3)
    assert found[0].tool_id == TICKET
    top = found[0].definition
    assert top.remote is True
    assert (top.namespace, top.module) == (MODULE, MODULE)
    assert top.input_schema["required"] == ["title"]
    assert [r.key for r in top.requirements.config] == ["region"]
    assert not any(r.secret for r in top.requirements.config)
    assert (
        tools.search_tools("what is the weather outside", USER, limit=1)[0].tool_id
        == FORECAST
    )


def test_a_client_engine_finds_it_and_runs_it_too(serving, crm, broker):
    client = new_engine(broker, role="client")
    client.load()
    try:
        wait_for(lambda: TICKET in published(client))
        tools = client.services.tool_registry
        assert tools.search_tools("report a bug", USER, limit=1)[0].tool_id == TICKET
        built = tools.resolve(TICKET, USER, config={"region": "eu"})
        out = json.loads(built.invoke({"title": "From a client engine"}))
        assert out["title"] == "From a client engine"
    finally:
        client.shutdown()


def test_a_capability_agent_finds_enables_and_calls_it(serving, crm):
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.memory import MemorySaver
    from naas_abi_core.services.agent.Agent import (
        AgentConfiguration,
        AgentSharedState,
    )
    from naas_abi_core.services.agent.CapabilityAgent import CapabilityAgent
    from naas_abi_core.services.agent.tests.scripted_chat_model import (
        ScriptedChatModel,
        ScriptRecorder,
    )

    def call(name, args, id):
        return AIMessage(
            content="",
            tool_calls=[{"name": name, "args": args, "id": id, "type": "tool_call"}],
        )

    recorder = ScriptRecorder(
        [
            call("search_capabilities", {"query": "report a bug in our product"}, "s1"),
            call("enable_capability", {"tool_id": TICKET}, "e1"),
            call("open_ticket", {"title": "Login fails", "priority": "high"}, "c1"),
            AIMessage(content="Ticket opened."),
        ]
    )
    agent = CapabilityAgent(
        name="capability_agent",
        description="Finds and enables the tools it needs",
        chat_model=ScriptedChatModel(recorder=recorder),
        tool_registry=serving.services.tool_registry,
        tools=[],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="remote-1"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        context_provider=lambda: USER,
        enable_default_tools=False,
        tool_config={TICKET: {"region": "eu"}},
    )
    assert agent.invoke("open a ticket about the login bug") == "Ticket opened."
    found = json.loads(recorder.tool_messages()[0].content)
    assert found[0]["tool_id"] == TICKET
    # Bound from the next model call on, with the module's own contract.
    assert recorder.bound[2] == sorted(
        [
            "disable_capability",
            "enable_capability",
            "list_enabled_capabilities",
            "open_ticket",
            "search_capabilities",
        ]
    )
    (arguments, seen) = CALLS[0]
    assert arguments == {"title": "Login fails", "priority": "high"}
    assert (seen.caller.identity, seen.caller.user_id) == ("engine", "user-7")
    assert seen.config == {"region": "eu"}
    result = json.loads(recorder.tool_messages()[-1].content)
    assert result["ticket"] == "T-1" and result["user"] == "user-7"


def test_a_composed_record_binds_it(serving, crm):
    from naas_abi_core.services.agent_composer.AgentComposerFactory import (
        AgentComposerFactory,
    )
    from naas_abi_core.services.agent_composer.AgentComposerPort import AgentSpec

    composer = AgentComposerFactory.FromEngine(serving)
    spec = AgentSpec.model_validate(
        {
            "name": "support",
            "prompt": "You support customers.",
            "tools": [
                {"tool": f"{MODULE}/open_ticket", "config": {"region": "us"}},
                f"{MODULE}/get_forecast",
            ],
        }
    )
    agent = composer.compose(spec, context=USER)
    by_name = {tool.name: tool for tool in agent.tools}
    ticket = json.loads(by_name["open_ticket"].invoke({"title": "Composed"}))
    assert ticket["region"] == "us" and ticket["user"] == "user-7"
    assert by_name["get_forecast"].invoke({"city": "Paris"}) == "Sunny in Paris"
    # A tool's error reaches the model as the tool's output.
    assert by_name["get_forecast"].invoke({"city": "Atlantis"}) == (
        "TOOL_ERROR: No such city"
    )
    # Arguments that break the contract are refused by the module.
    refused = by_name["open_ticket"].invoke({"title": "x", "priority": "urgent"})
    assert refused.startswith("INVALID_ARGUMENT")
    assert len(CALLS) == 1


def test_the_required_scopes_apply_as_for_local_tools(serving, crm):
    tools = serving.services.tool_registry
    assert CLOSE not in {
        str(d.id) for d in tools.list_definitions(ToolContext(user_id="user-7"))
    }
    with pytest.raises(ToolAccessDeniedError, match="crm:admin"):
        tools.resolve(CLOSE, ToolContext(user_id="user-7"), action=ToolAction.ENABLE)
    admin = ToolContext(user_id="user-7", scopes=frozenset({"crm:admin"}))
    built = tools.resolve(CLOSE, admin)
    assert built.invoke({"account": "A-1"}) == "closed"


def test_the_tool_disappears_when_the_module_stops(serving, broker):
    running = RunningModule(broker, build_module()).start()
    tools = serving.services.tool_registry
    try:
        wait_for(lambda: TICKET in published(serving))
        assert tools.search_tools("report a bug", USER, limit=1)[0].tool_id == TICKET
    finally:
        running.stop()
    wait_for(lambda: TICKET not in published(serving))
    assert published(serving) == set()
    assert tools.search_tools("report a bug", USER, limit=3) == []
    with pytest.raises(ToolNotFoundError):
        tools.resolve(TICKET, USER, config={"region": "eu"})
    # And comes back with the module.
    again = RunningModule(broker, build_module()).start()
    try:
        wait_for(lambda: TICKET in published(serving))
    finally:
        again.stop()


def test_a_tool_built_before_the_module_stopped_fails_cleanly(serving, broker):
    running = RunningModule(broker, build_module()).start()
    wait_for(lambda: TICKET in published(serving))
    built = serving.services.tool_registry.resolve(
        TICKET, USER, config={"region": "eu"}
    )
    running.stop()
    assert built.invoke({"title": "Too late"}).startswith("MODULE_UNAVAILABLE")


def sdk_client(url, identity, token_source=None):
    from naas_abi_sdk.discovery import DiscoveryClient, ModuleProxy
    from naas_abi_sdk.service_token import ModuleToken
    from naas_abi_sdk.transport import Transport

    transport = Transport(
        login(url, "module", PASSWORDS["module"]),
        token_source or ModuleToken(identity, module_key(SECRET, identity)),
        timeout=10,
    )
    return transport, ModuleProxy(DiscoveryClient(transport, PROJECT), MODULE)


def test_the_module_refuses_callers_it_does_not_trust(serving, crm, broker):
    from naas_abi_sdk.transport import RPCError

    class Replayed:
        """A token bound to some other instance, sent to this one."""

        def __call__(self):
            return issue_service_token("engine", SECRET)

        def for_audience(self, audience):
            return issue_service_token("engine", SECRET, audience="another-instance")

    async def scenario():
        refused = {}
        for label, source in (("module", None), ("replay", Replayed())):
            transport, proxy = sdk_client(broker, "intruder", source)
            try:
                with pytest.raises(RPCError) as error:
                    await proxy.call_tool(
                        "open_ticket", {"title": "x"}, config={"region": "eu"}
                    )
                refused[label] = error.value.code
            finally:
                await transport.close()
        return refused

    refused = asyncio.run(scenario())
    # By default only the engine's own processes run a module's tools.
    assert refused["module"] == "PERMISSION_DENIED"
    # A token that is not bound to this instance never gets past discovery.
    assert refused["replay"] == "UNAUTHENTICATED"
    assert CALLS == []


def test_a_modules_hook_can_refuse_the_engine_and_admit_a_module(serving, broker):
    seen = []

    def authorize(name, caller):
        seen.append((name, caller.identity))
        return caller.identity == "friend"

    running = RunningModule(broker, build_module(authorize=authorize)).start()
    try:
        wait_for(lambda: TICKET in published(serving))
        built = serving.services.tool_registry.resolve(
            TICKET, USER, config={"region": "eu"}
        )
        assert built.invoke({"title": "x"}).startswith("PERMISSION_DENIED")

        async def friend():
            transport, proxy = sdk_client(broker, "friend")
            try:
                return await proxy.call_tool(
                    "open_ticket", {"title": "from a friend"}, config={"region": "eu"}
                )
            finally:
                await transport.close()

        out = asyncio.run(friend())
        assert (out["caller"], out["user"]) == ("friend", None)
        assert ("open_ticket", "engine") in seen and ("open_ticket", "friend") in seen
    finally:
        running.stop()


def test_malformed_arguments_never_reach_the_handler(serving, crm, broker):
    from naas_abi_sdk.transport import RPCError

    async def scenario():
        transport = None
        try:
            from naas_abi_sdk.discovery import DiscoveryClient, ModuleProxy
            from naas_abi_sdk.transport import Transport

            transport = Transport(
                login(broker, "abi", PASSWORDS["abi"]),
                ServiceTokenSource("engine", SECRET),
                timeout=10,
            )
            proxy = ModuleProxy(DiscoveryClient(transport, PROJECT), MODULE)
            codes = []
            for arguments, config in (
                ({}, {"region": "eu"}),
                ({"title": 5}, {"region": "eu"}),
                ({"title": "x", "extra": 1}, {"region": "eu"}),
                ({"title": "x", "priority": "urgent"}, {"region": "eu"}),
                ({"title": "x"}, {}),
                ({"title": "x"}, {"region": "eu", "api_key": "k"}),
            ):
                with pytest.raises(RPCError) as error:
                    await proxy.call_tool("open_ticket", arguments, config=config)
                codes.append(error.value.code)
            ok = await proxy.call_tool(
                "open_ticket", {"title": "valid"}, config={"region": "eu"}
            )
            return codes, ok
        finally:
            if transport is not None:
                await transport.close()

    codes, ok = asyncio.run(scenario())
    assert codes == ["INVALID_ARGUMENT"] * 6
    assert [arguments for arguments, _ in CALLS] == [{"title": "valid"}]
    assert ok["caller"] == "engine"


def test_no_engine_secret_reaches_a_module(serving, crm):
    from naas_abi_core.services.agent_composer.AgentComposerFactory import (
        AgentComposerFactory,
    )
    from naas_abi_core.services.agent_composer.AgentComposerPort import (
        AgentCompositionError,
        AgentSpec,
    )

    composer = AgentComposerFactory.FromEngine(serving)
    spec = AgentSpec.model_validate(
        {
            "name": "support",
            "prompt": "You support customers.",
            "tools": [
                {
                    "tool": f"{MODULE}/open_ticket",
                    "config": {"region": {"secret": "CRM_API_KEY"}},
                }
            ],
        }
    )
    with pytest.raises(AgentCompositionError, match="never sent to a module"):
        composer.compose(spec)
    assert CALLS == [] and RECEIVED == []

    # A call that does go through carries the tool's arguments and plain
    # configuration, a token bound to the instance, and nothing else of the engine.
    agent = composer.compose(
        AgentSpec.model_validate(
            {
                "name": "support",
                "prompt": "You support customers.",
                "tools": [
                    {"tool": f"{MODULE}/open_ticket", "config": {"region": "eu"}}
                ],
            }
        ),
        context=USER,
    )
    next(t for t in agent.tools if t.name == "open_ticket").invoke({"title": "x"})
    assert len(RECEIVED) == 1
    for data, headers in RECEIVED:
        wire = data + json.dumps(headers).encode()
        assert SECRET.encode() not in wire
        assert CREDENTIAL.encode() not in wire
    # The token is a signed claim for the instance, not the key that signs it.
    token = RECEIVED[0][1]["Nats-Auth-Token"]
    import jwt

    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["sub"] == "engine" and claims["aud"]


def test_the_catalog_never_shows_a_module_a_configuration_value(serving, crm, broker):
    from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.service_token import ModuleToken

    async def scenario():
        client = ABIClient(
            login(broker, "module", PASSWORDS["module"]),
            ModuleToken("plain_module", module_key(SECRET, "plain_module")),
            timeout=30,
        )
        try:
            listed = await client.tool_registry.list_tools(pb.ListToolsRequest())
            return {t.definition.id: t.definition for t in listed.tools}
        finally:
            await client.close()

    definitions = asyncio.run(scenario())
    # An SDK module with no scopes sees the remote tool that needs none, flagged remote.
    assert definitions[TICKET].remote is True
    assert CLOSE not in definitions
