"""The tool catalog over NATS, on a real broker: a client engine and an SDK module
read the serving engine's registry (docs/adr/20261021_tool-catalog-over-nats.md).

The serving engine publishes the tools; the client engine's own modules publish
none (or one of its own). What both read through ``abi.svc.tool_registry.v1`` must
rank like an in-process search of the serving engine.
"""

import asyncio
import sys
import textwrap
from pathlib import Path

import pytest
from naas_abi_core.engine.nats_auth import (
    issue_module_token,
    issue_service_token,
    module_key,
)
from naas_abi_core.engine.nats_test_server import (
    login,
    native_nats_server,
    nats_server_binary,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ToolAction,
    ToolContext,
    ToolNotFoundError,
    ToolResolutionError,
)

SECRET = "engine-tool-catalog-test-secret-at-least-32-bytes"
CREDENTIAL = "sk-live-never-leaves-the-serving-engine"
ISSUE = "catalog_serving/create_issue@1"
FORECAST = "catalog_serving/get_forecast@1"
EMAIL = "catalog_serving/send_email@1"
REFUND = "catalog_serving/refund_payment@1"
SYNC = "catalog_serving/sync_contacts@1"
LOCAL = "catalog_client/close_ticket@1"
BILLING = frozenset({"billing:write"})

SERVING_MODULE = textwrap.dedent(
    '''
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langchain_core.tools import tool
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

    BUILDS = []


    @tool
    def create_issue(title: str) -> str:
        """Create a new issue in a GitHub repository."""
        return title


    @tool
    def get_forecast(city: str) -> str:
        """Get the weather forecast for a city."""
        return city


    @tool
    def send_email(recipient: str) -> str:
        """Send an email message to a recipient."""
        return recipient


    @tool
    def refund_payment(payment: str) -> str:
        """Refund a payment and send the customer a receipt."""
        return payment


    @tool
    def sync_contacts(source: str) -> str:
        """Create and update the contacts of a CRM from a list."""
        return source


    def contacts_factory(config):
        BUILDS.append(config)
        return [sync_contacts]


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

        def publish_tools(self, publisher):
            publisher.add_tools([create_issue, get_forecast, send_email])
            publisher.add_tool(refund_payment, required_scopes=["billing:write"])
            publisher.add_factory(
                contacts_factory,
                default_config={"api_key": "sk-live-never-leaves-the-serving-engine"},
                requirements=[ConfigRequirement(key="api_key", secret=True)],
                tags=("crm",),
            )
    '''
)

CLIENT_MODULE = textwrap.dedent(
    '''
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langchain_core.tools import tool
    from naas_abi_core.models.Model import ChatModel
    from naas_abi_core.module.Module import (
        BaseModule,
        ModuleConfiguration,
        ModuleDependencies,
    )
    from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
        concept_embedding_model,
    )


    @tool
    def close_ticket(ticket: str) -> str:
        """Close a resolved issue ticket and notify the reporter."""
        return ticket


    class ABIModule(BaseModule):
        dependencies = ModuleDependencies(modules=[], services=[])

        class Configuration(ModuleConfiguration):
            publish_a_tool: bool = False

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

        def publish_tools(self, publisher):
            if self.configuration.publish_a_tool:
                publisher.add_tools([close_ticket])
    '''
)


@pytest.fixture
def modules(tmp_path, monkeypatch) -> None:
    for name, source in (
        ("catalog_serving", SERVING_MODULE),
        ("catalog_client", CLIENT_MODULE),
    ):
        package = tmp_path / "modules" / name
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(source)
    monkeypatch.syspath_prepend(str(tmp_path / "modules"))


@pytest.fixture
def engine_dir(tmp_path, monkeypatch) -> Path:
    work = tmp_path / "engine"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


@pytest.fixture
def broker(tmp_path):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with native_nats_server(tmp_path, jetstream=True) as url:
        yield url


def new_engine(url, module, *, role=None, engine="", module_config="{}", scopes=""):
    from naas_abi_core.engine.Engine import Engine

    settings = ", engine: {" + (f"role: {role}, " if role else "") + engine + "}"
    return Engine(
        "api: {}\n"
        "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
        f"modules: [{{module: {module}, enabled: true, config: {module_config}}}]\n"
        "services:\n"
        "  secret: {secret_adapters: []}\n"
        "  model_registry: {default_embedding_model: concepts, default_chat_model: probe-chat}\n"
        "  tool_registry: {collection_prefix: catalog_tools}\n"
        f"nats: {{nats_url: '{url}', jwt_secret: {SECRET}{settings}{scopes}}}\n"
    )


@pytest.fixture
def serving(modules, engine_dir, broker):
    engine = new_engine(
        broker,
        "catalog_serving",
        scopes=", tool_registry: {module_scopes: {billing_module: ['billing:write']}}",
    )
    engine.load()
    yield engine
    engine.shutdown()


@pytest.fixture
def client(serving, broker):
    engine = new_engine(broker, "catalog_client", role="client")
    engine.load()
    yield engine
    engine.shutdown()


QUERIES = (
    "report a bug in our codebase",
    "what is the weather outside",
    "send a message to a customer",
    "update the contacts of the crm",
)


def ids(results) -> list[str]:
    return [result.tool_id for result in results]


def serving_ids(serving, query, limit, context):
    """The serving engine's own search, in process, as the reference."""
    return ids(serving.services.tool_registry.search_tools(query, context, limit=limit))


def test_a_client_engine_searches_the_serving_engines_registry(serving, client):
    tools = client.services.tool_registry
    assert tools.catalog_available
    assert not serving.services.tool_registry.catalog_available
    for query in QUERIES:
        for limit in (1, 2, 3, 5):
            found = ids(tools.search_tools(query, ToolContext(), limit=limit))
            assert found == serving_ids(serving, query, limit, ToolContext())
            assert len(found) <= limit
    assert ids(tools.search_tools("report a bug", ToolContext(), limit=1)) == [ISSUE]


def test_a_client_engine_reads_the_catalog(serving, client):
    tools = client.services.tool_registry
    assert [str(d.id) for d in tools.list_definitions()] == [
        str(d.id) for d in serving.services.tool_registry.list_definitions()
    ]
    assert str(tools.get_definition("catalog_serving/create_issue").id) == ISSUE
    assert tools.get_definition(ISSUE) == serving.services.tool_registry.get_definition(
        ISSUE
    )
    with pytest.raises(ToolNotFoundError):
        tools.get_definition("catalog_serving/nothing@1")
    assert tools.availability(SYNC).available
    assert tools.availability(ISSUE).available


def test_the_callers_scopes_filter_what_a_client_engine_reads(serving, client):
    tools = client.services.tool_registry
    assert REFUND not in {str(d.id) for d in tools.list_definitions(ToolContext())}
    assert REFUND in {str(d.id) for d in tools.list_definitions()}
    assert REFUND in {
        str(d.id) for d in tools.list_definitions(ToolContext(scopes=BILLING))
    }
    assert REFUND not in ids(
        tools.search_tools("refund a payment", ToolContext(), limit=5)
    )
    assert REFUND in ids(
        tools.search_tools("refund a payment", ToolContext(scopes=BILLING), limit=5)
    )
    for context in (ToolContext(), ToolContext(scopes=BILLING)):
        assert ids(tools.search_tools("refund a payment", context, limit=5)) == (
            serving_ids(serving, "refund a payment", 5, context)
        )


def test_searching_and_reading_never_builds_a_tool(serving, client):
    serving_module = sys.modules["catalog_serving"]
    built = len(serving_module.BUILDS)
    tools = client.services.tool_registry
    for query in QUERIES:
        tools.search_tools(query, ToolContext(scopes=BILLING), limit=5)
    tools.list_definitions()
    tools.get_definition(SYNC)
    tools.availability(SYNC)
    assert len(serving_module.BUILDS) == built


def test_what_the_serving_engine_found_runs_only_there(serving, client):
    tools = client.services.tool_registry
    with pytest.raises(ToolResolutionError, match="another engine process"):
        tools.resolve(ISSUE, ToolContext())
    # ...and the serving engine's own tools still resolve in its own process.
    built = serving.services.tool_registry.resolve(ISSUE, ToolContext())
    assert built.name == "create_issue"


def test_a_client_engine_keeps_the_tools_it_published_itself(
    modules, engine_dir, broker, serving
):
    own = new_engine(
        broker,
        "catalog_client",
        role="client",
        module_config="{publish_a_tool: true}",
    )
    own.load()
    try:
        tools = own.services.tool_registry
        found = ids(
            tools.search_tools("close a resolved ticket", ToolContext(), limit=5)
        )
        assert LOCAL in found and ISSUE in found
        listed = [str(d.id) for d in tools.list_definitions()]
        assert LOCAL in listed and ISSUE in listed and listed == sorted(listed)
        # What this engine published resolves here; the other tools do not.
        assert tools.resolve(LOCAL, ToolContext()).name == "close_ticket"
        tools.check_access(LOCAL, ToolContext(), ToolAction.EXECUTE)
        # The serving engine does not see it: publication stays in the process.
        assert LOCAL not in {
            str(d.id) for d in serving.services.tool_registry.list_definitions()
        }
    finally:
        own.shutdown()


# ------------------------------------------------------------------ SDK module


def sdk_session(url, identity):
    """An SDK module's view: its own module token, as a module process holds it."""
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.services.tool_registry import ToolRegistryService

    client = ABIClient(
        url, issue_module_token(identity, module_key(SECRET, identity)), timeout=30
    )
    return client, ToolRegistryService(client.tool_registry)


def test_an_sdk_module_searches_the_serving_engines_registry(serving, broker):
    async def scenario():
        client, tools = sdk_session(broker, "plain_module")
        try:
            for query in QUERIES:
                for limit in (1, 3, 5):
                    found = await tools.search_tools(query, limit=limit)
                    assert [m.tool_id for m in found] == serving_ids(
                        serving, query, limit, ToolContext()
                    )
            top = (await tools.search_tools("report a bug", limit=1))[0]
            assert top.tool_id == ISSUE and top.score > 0
            assert top.definition.input_schema["properties"]["title"]
            assert top.availability.available
            entries = await tools.list_tools()
            assert [e.definition.id for e in entries] == [
                str(d.id)
                for d in serving.services.tool_registry.list_definitions(ToolContext())
            ]
            assert (
                await tools.get_tool("catalog_serving/get_forecast")
            ).definition.id == (FORECAST)
        finally:
            await client.close()

    asyncio.run(scenario())


def test_an_sdk_modules_scopes_come_from_its_identity_only(serving, broker):
    from naas_abi_proto.common.v1 import common_pb2
    from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb
    from naas_abi_sdk.services.errors import ToolNotFound

    async def scenario():
        plain, plain_tools = sdk_session(broker, "plain_module")
        billing, billing_tools = sdk_session(broker, "billing_module")
        try:
            assert REFUND not in [
                m.tool_id
                for m in await plain_tools.search_tools("refund a payment", limit=10)
            ]
            with pytest.raises(ToolNotFound):
                await plain_tools.get_tool(REFUND)
            # Nothing in the request widens them.
            widened = await plain.tool_registry.search_tools(
                pb.SearchToolsRequest(
                    query="refund a payment",
                    limit=10,
                    context=common_pb2.CallContext(
                        principal_id="billing_module", workspace_id="billing:write"
                    ),
                    filter=pb.ToolFilter(tags=["billing:write"]),
                )
            )
            assert REFUND not in [m.tool.definition.id for m in widened.matches]
            # The scopes configured for the identity do.
            found = await billing_tools.search_tools("refund a payment", limit=10)
            assert REFUND in [m.tool_id for m in found]
            assert (
                await billing_tools.get_tool(REFUND)
            ).definition.required_scopes == ("billing:write",)
        finally:
            await plain.close()
            await billing.close()

    asyncio.run(scenario())


def test_an_sdk_module_cannot_assert_the_engines_identity(serving, broker):
    from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.transport import RPCError

    async def scenario():
        forged = ABIClient(
            broker, issue_module_token("engine", module_key(SECRET, "plain_module"))
        )
        engine = ABIClient(broker, issue_service_token("engine", SECRET))
        try:
            with pytest.raises(RPCError) as refused:
                await forged.tool_registry.list_tools(pb.ListToolsRequest())
            assert refused.value.code == "UNAUTHENTICATED"
            everything = await engine.tool_registry.list_tools(pb.ListToolsRequest())
            assert REFUND in [t.definition.id for t in everything.tools]
        finally:
            await forged.close()
            await engine.close()

    asyncio.run(scenario())


def test_no_definition_carries_a_credential(serving, client, broker):
    from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb

    async def scenario():
        sdk, tools = sdk_session(broker, "billing_module")
        try:
            replies = [
                (await sdk.tool_registry.list_tools(pb.ListToolsRequest())),
                (await sdk.tool_registry.get_tool(pb.GetToolRequest(ref=SYNC))),
                (
                    await sdk.tool_registry.search_tools(
                        pb.SearchToolsRequest(query="update the contacts", limit=5)
                    )
                ),
            ]
            return [
                reply.SerializeToString() for reply in replies
            ], await tools.get_tool(SYNC)
        finally:
            await sdk.close()

    payloads, entry = asyncio.run(scenario())
    assert all(CREDENTIAL.encode() not in payload for payload in payloads)
    (requirement,) = entry.definition.config
    assert (requirement.key, requirement.secret) == ("api_key", True)
    assert entry.availability.available
    remote = client.services.tool_registry.get_definition(SYNC)
    assert CREDENTIAL not in repr(remote)


def test_a_module_logged_in_as_the_brokers_module_user_needs_no_extra_permission(
    modules, engine_dir, tmp_path
):
    """``MODULE_PERMISSIONS`` forbids subscribing to ``abi.svc.>``, not calling it:
    the catalog needs no change to the broker's configuration."""
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    passwords = {"abi": "tool-catalog-abi-password", "module": "tool-catalog-module"}
    with native_nats_server(tmp_path, jetstream=True, users=passwords) as url:
        engine = new_engine(login(url, "abi", passwords["abi"]), "catalog_serving")
        engine.load()
        try:

            async def scenario():
                from naas_abi_sdk.client import ABIClient
                from naas_abi_sdk.services.tool_registry import ToolRegistryService

                client = ABIClient(
                    login(url, "module", passwords["module"]),
                    issue_module_token(
                        "plain_module", module_key(SECRET, "plain_module")
                    ),
                    timeout=30,
                )
                try:
                    found = await ToolRegistryService(
                        client.tool_registry
                    ).search_tools("report a bug", limit=2)
                    assert found[0].tool_id == ISSUE
                finally:
                    await client.close()

            asyncio.run(scenario())
        finally:
            engine.shutdown()
