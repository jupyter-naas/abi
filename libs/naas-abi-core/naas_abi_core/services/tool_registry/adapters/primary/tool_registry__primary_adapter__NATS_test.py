"""The catalog's primary adapter: validation, identity-bound access and reply size.

No broker here; the real-broker tests are in
``engine/Engine_tool_registry_nats_integration_test.py``.
"""

import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_core.engine.nats_auth import (
    issue_module_token,
    issue_service_token,
    module_key,
)
from naas_abi_core.services.tool_registry.adapters.primary.tool_registry__primary_adapter__NATS import (
    ToolRegistryPrimaryAdapterNATS,
)
from naas_abi_core.services.tool_registry.adapters.secondary.InMemoryToolIndexAdapter import (
    InMemoryToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.adapters.tool_registry_nats_codec import (
    definition_from_pb,
)
from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
    CountingConceptEmbedder,
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
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb

SECRET = "tool-registry-primary-test-secret-32-bytes"
CREDENTIAL = "sk-live-must-never-leave-the-engine"
RESPONSES = {
    "list_tools": pb.ListToolsResponse,
    "get_tool": pb.GetToolResponse,
    "search_tools": pb.SearchToolsResponse,
}


class Binding:
    def __init__(self, default_config=None):
        self.default_config = default_config or {}
        self.built = 0

    def create(self, context, config):
        self.built += 1
        raise AssertionError("a catalog read must never build a tool")


def publish(registry, module, name, description, binding=None, **definition):
    registry.publish(
        module,
        [
            *[
                tool
                for tool in registry._tools.values()
                if tool.definition.module == module
            ],
            PublishedTool(
                definition=ToolDefinition(
                    namespace=module,
                    name=name,
                    description=description,
                    module=module,
                    **definition,
                ),
                binding=binding or Binding(),
            ),
        ],
    )


@pytest.fixture
def bindings():
    return {"billing": Binding({"api_key": CREDENTIAL})}


@pytest.fixture
def registry(bindings):
    registry = ToolRegistryService(
        embedder=CountingConceptEmbedder(), index=InMemoryToolIndexAdapter()
    )
    publish(
        registry, "acme.github", "create_issue", "Create a new issue in a repository."
    )
    publish(
        registry, "acme.weather", "get_forecast", "Get the weather forecast for a city."
    )
    publish(
        registry,
        "acme.billing",
        "refund",
        "Refund a customer payment and send the receipt by email.",
        bindings["billing"],
        required_scopes=("billing:write",),
        requirements=ToolRequirements(
            config=(ConfigRequirement(key="api_key", secret=True),)
        ),
    )
    return registry


@pytest.fixture
def primary(registry):
    primary = ToolRegistryPrimaryAdapterNATS(
        registry, SECRET, module_scopes={"billing_module": ["billing:write"]}
    )
    yield primary
    primary._dispatch.close()


def token(identity="engine"):
    if identity in ("engine", "api", "dagster"):
        return issue_service_token(identity, SECRET)
    return issue_module_token(identity, module_key(SECRET, identity))


def call(primary, operation, message, identity="engine", *, auth=True, limit=None):
    msg_client = SimpleNamespace(max_payload=limit) if limit else None
    request = SimpleNamespace(
        data=message if isinstance(message, bytes) else message.SerializeToString(),
        headers={"Nats-Auth-Token": token(identity)} if auth else {},
        respond=AsyncMock(),
        _msg=SimpleNamespace(_client=msg_client),
    )
    asyncio.run(primary._handle(request, operation=operation))
    payload = request.respond.call_args.args[0]
    return RESPONSES[operation].FromString(payload), payload


def ids(response):
    return [match.tool.definition.id for match in response.matches]


class TestAuthentication:
    def test_a_call_without_a_valid_token_is_refused(self, primary):
        response, _ = call(
            primary, "search_tools", pb.SearchToolsRequest(query="x"), auth=False
        )
        assert response.error.code == "UNAUTHENTICATED"

    def test_a_module_cannot_assert_the_engines_identity(self, primary):
        forged = issue_module_token("engine", module_key(SECRET, "someone"))
        request = SimpleNamespace(
            data=pb.GetToolRequest(ref="acme.github/create_issue").SerializeToString(),
            headers={"Nats-Auth-Token": forged},
            respond=AsyncMock(),
        )
        asyncio.run(primary._handle(request, operation="get_tool"))
        response = pb.GetToolResponse.FromString(request.respond.call_args.args[0])
        assert response.error.code == "UNAUTHENTICATED"


class TestValidation:
    @pytest.mark.parametrize(
        "operation, message",
        [
            ("search_tools", pb.SearchToolsRequest(query="")),
            ("search_tools", pb.SearchToolsRequest(query="   ")),
            ("search_tools", pb.SearchToolsRequest(query="x" * 2001)),
            ("search_tools", pb.SearchToolsRequest(query="x", limit=51)),
            (
                "search_tools",
                pb.SearchToolsRequest(query="x", min_score=math.nan),
            ),
            (
                "search_tools",
                pb.SearchToolsRequest(
                    query="x", filter=pb.ToolFilter(modules=["m"] * 33)
                ),
            ),
            (
                "search_tools",
                pb.SearchToolsRequest(query="x", filter=pb.ToolFilter(tags=["t" * 65])),
            ),
            ("get_tool", pb.GetToolRequest(ref="")),
            ("get_tool", pb.GetToolRequest(ref="no-namespace")),
            ("get_tool", pb.GetToolRequest(ref="a/" + "b" * 600)),
            ("list_tools", pb.ListToolsRequest(limit=201)),
            ("list_tools", pb.ListToolsRequest(after="a" * 513)),
            ("list_tools", pb.ListToolsRequest(filter=pb.ToolFilter(tags=["t"] * 17))),
        ],
    )
    def test_requests_outside_the_contract_are_invalid(
        self, primary, operation, message
    ):
        response, _ = call(primary, operation, message)
        assert response.error.code == "INVALID_ARGUMENT"

    def test_garbage_is_invalid(self, primary):
        response, _ = call(primary, "search_tools", b"\xff\xff\xff")
        assert response.error.code == "INVALID_ARGUMENT"

    def test_defaults_apply_to_a_zero_limit(self, primary):
        found, _ = call(primary, "search_tools", pb.SearchToolsRequest(query="issue"))
        assert not found.error.code
        assert 1 <= len(found.matches) <= 5
        listed, _ = call(primary, "list_tools", pb.ListToolsRequest())
        assert len(listed.tools) == 3

    def test_a_failing_backend_is_reported_without_its_details(self, primary, registry):
        def explode(*args, **kwargs):
            raise RuntimeError(f"provider said {CREDENTIAL}")

        registry.search_local = explode
        response, payload = call(
            primary, "search_tools", pb.SearchToolsRequest(query="issue")
        )
        assert response.error.code == "INTERNAL"
        assert CREDENTIAL.encode() not in payload

    def test_search_without_an_embedder_is_reported_as_unavailable(self, primary):
        primary._registry = ToolRegistryService()
        response, _ = call(primary, "search_tools", pb.SearchToolsRequest(query="x"))
        assert response.error.code == "SEARCH_UNAVAILABLE"


class TestAccessFollowsTheIdentity:
    def test_the_engines_own_processes_see_every_tool(self, primary):
        for identity in ("engine", "api", "dagster"):
            response, _ = call(primary, "list_tools", pb.ListToolsRequest(), identity)
            assert [t.definition.id for t in response.tools] == [
                "acme.billing/refund@1",
                "acme.github/create_issue@1",
                "acme.weather/get_forecast@1",
            ]

    def test_a_module_sees_only_what_needs_no_scope_by_default(self, primary):
        response, _ = call(primary, "list_tools", pb.ListToolsRequest(), "some_module")
        assert [t.definition.id for t in response.tools] == [
            "acme.github/create_issue@1",
            "acme.weather/get_forecast@1",
        ]
        found, _ = call(
            primary,
            "search_tools",
            pb.SearchToolsRequest(query="refund a payment", limit=10),
            "some_module",
        )
        assert "acme.billing/refund@1" not in ids(found)

    def test_a_module_sees_the_scopes_configured_for_its_identity(self, primary):
        found, _ = call(
            primary,
            "search_tools",
            pb.SearchToolsRequest(query="refund a payment", limit=10),
            "billing_module",
        )
        assert ids(found)[0] == "acme.billing/refund@1"

    def test_a_tool_the_caller_cannot_discover_is_not_found_not_forbidden(
        self, primary
    ):
        hidden, _ = call(
            primary,
            "get_tool",
            pb.GetToolRequest(ref="acme.billing/refund"),
            "some_module",
        )
        missing, _ = call(
            primary,
            "get_tool",
            pb.GetToolRequest(ref="acme.billing/nothing"),
            "some_module",
        )
        assert hidden.error.code == missing.error.code == "TOOL_NOT_FOUND"
        assert hidden.error.message == missing.error.message
        shown, _ = call(
            primary,
            "get_tool",
            pb.GetToolRequest(ref="acme.billing/refund@1"),
            "billing_module",
        )
        assert shown.tool.definition.name == "refund"

    def test_the_request_cannot_widen_the_callers_scopes(self, primary):
        """Nothing in a request grants a scope: not the context, not a filter, not
        a field a newer client might know (kept as an unknown field)."""
        search = pb.SearchToolsRequest(
            query="refund a payment",
            limit=10,
            context=common_pb2.CallContext(
                principal_id="admin",
                workspace_id="billing:write",
                tenant_id="*",
                trace_id="billing:write",
            ),
            filter=pb.ToolFilter(modules=["acme.billing"], tags=["billing:write"]),
        )
        crafted = search.SerializeToString() + (
            # field 99 (string) = "billing:write"; field 98 (varint) = 1
            b"\x9a\x06\rbilling:write" + b"\x90\x06\x01"
        )
        found, _ = call(primary, "search_tools", crafted, "some_module")
        assert not found.error.code
        assert "acme.billing/refund@1" not in ids(found)
        listed, _ = call(
            primary,
            "list_tools",
            pb.ListToolsRequest(
                context=common_pb2.CallContext(principal_id="billing:write"),
                filter=pb.ToolFilter(modules=["acme.billing"]),
            ),
            "some_module",
        )
        assert list(listed.tools) == []

    def test_a_modules_scopes_cannot_come_from_another_modules_entry(self, primary):
        assert primary.caller_context("billing_module").scopes == {"billing:write"}
        assert primary.caller_context("billing_module_2").scopes == frozenset()
        assert primary.caller_context("").scopes == frozenset()


class TestNothingIsRunOrLeaked:
    def test_a_read_never_builds_a_tool(self, primary, bindings):
        call(primary, "search_tools", pb.SearchToolsRequest(query="refund", limit=10))
        call(primary, "list_tools", pb.ListToolsRequest())
        call(primary, "get_tool", pb.GetToolRequest(ref="acme.billing/refund"))
        assert bindings["billing"].built == 0

    def test_no_reply_carries_a_binding_value(self, primary):
        payloads = [
            call(primary, "list_tools", pb.ListToolsRequest())[1],
            call(primary, "get_tool", pb.GetToolRequest(ref="acme.billing/refund"))[1],
            call(
                primary,
                "search_tools",
                pb.SearchToolsRequest(query="refund a payment", limit=10),
            )[1],
        ]
        assert all(CREDENTIAL.encode() not in payload for payload in payloads)

    def test_a_requirement_names_a_secret_and_availability_says_what_is_missing(
        self, primary, registry
    ):
        entry = call(primary, "get_tool", pb.GetToolRequest(ref="acme.billing/refund"))[
            0
        ].tool
        (requirement,) = entry.definition.requirements.config
        assert (requirement.key, requirement.secret) == ("api_key", True)
        # The module's own value satisfies it, so the tool is available...
        assert entry.availability.available
        # ...and without one, the key is reported missing, never a value.
        registry._tools["acme.billing/refund@1"].binding.default_config = {}
        entry = call(primary, "get_tool", pb.GetToolRequest(ref="acme.billing/refund"))[
            0
        ].tool
        assert not entry.availability.available
        assert list(entry.availability.missing_config) == ["api_key"]


class TestTheServingEngineNeverReadsACatalog:
    def test_a_registry_that_has_just_stopped_reading_one_answers_alone(
        self, primary, registry
    ):
        """A standby that took over served its catalog before it switched its
        registry's catalog off: a call that reached the primary then must not go
        out to NATS, into the queue group it is now part of."""
        from naas_abi_core.services.tool_registry.ToolRegistryPort import (
            IToolCatalogPort,
        )

        class Loops(IToolCatalogPort):
            def list_tools(self, filter=None):
                raise AssertionError("the primary asked a catalog")

            get_tool = list_tools

            def search_tools(self, *args, **kwargs):
                raise AssertionError("the primary asked a catalog")

        registry.configure_catalog(Loops())
        listed, _ = call(primary, "list_tools", pb.ListToolsRequest())
        got, _ = call(
            primary, "get_tool", pb.GetToolRequest(ref="acme.github/create_issue")
        )
        found, _ = call(
            primary,
            "search_tools",
            pb.SearchToolsRequest(query="report a bug", limit=2),
        )
        assert len(listed.tools) == 3 and got.tool.definition.name == "create_issue"
        assert ids(found)[0] == "acme.github/create_issue@1"


class TestResults:
    def test_a_definition_round_trips(self, primary, registry):
        entry = call(primary, "get_tool", pb.GetToolRequest(ref="acme.billing/refund"))[
            0
        ].tool
        assert definition_from_pb(entry.definition) == registry.get_definition(
            "acme.billing/refund"
        )
        assert entry.definition.id == "acme.billing/refund@1"
        assert list(entry.definition.required_scopes) == ["billing:write"]

    def test_search_ranks_like_the_registry_and_limit_holds(self, primary, registry):
        for query in ("report a bug", "weather outside", "send a receipt"):
            expected = [
                r.tool_id
                for r in registry.search_local(
                    query, primary.caller_context("engine"), limit=2
                )
            ]
            found, _ = call(
                primary, "search_tools", pb.SearchToolsRequest(query=query, limit=2)
            )
            assert ids(found) == expected
            assert len(found.matches) <= 2

    def test_filters_and_min_score_narrow_a_search(self, primary):
        found, _ = call(
            primary,
            "search_tools",
            pb.SearchToolsRequest(
                query="create something",
                limit=10,
                filter=pb.ToolFilter(modules=["acme.weather"]),
            ),
        )
        assert ids(found) == ["acme.weather/get_forecast@1"]
        none, _ = call(
            primary,
            "search_tools",
            pb.SearchToolsRequest(query="report a bug", limit=10, min_score=2.0),
        )
        assert list(none.matches) == []

    def test_listing_pages_by_id_and_filters(self, primary):
        first, _ = call(primary, "list_tools", pb.ListToolsRequest(limit=2))
        assert [t.definition.id for t in first.tools] == [
            "acme.billing/refund@1",
            "acme.github/create_issue@1",
        ]
        assert first.next_after == "acme.github/create_issue@1"
        last, _ = call(
            primary, "list_tools", pb.ListToolsRequest(limit=2, after=first.next_after)
        )
        assert [t.definition.id for t in last.tools] == ["acme.weather/get_forecast@1"]
        assert last.next_after == ""
        exact, _ = call(primary, "list_tools", pb.ListToolsRequest(limit=3))
        assert exact.next_after == ""

    def test_available_only_leaves_out_what_is_not_configured(self, primary, registry):
        registry._tools["acme.billing/refund@1"].binding.default_config = {}
        listed, _ = call(
            primary,
            "list_tools",
            pb.ListToolsRequest(filter=pb.ToolFilter(available_only=True)),
        )
        assert "acme.billing/refund@1" not in [t.definition.id for t in listed.tools]


class TestReplySize:
    def test_a_page_stops_before_it_passes_half_the_brokers_limit(self, registry):
        for n in range(20):
            publish(
                registry,
                "acme.bulk",
                f"tool_{n:02d}",
                "A tool. " * 50,
                input_schema={"type": "object", "x": "y" * 400},
            )
        primary = ToolRegistryPrimaryAdapterNATS(registry, SECRET)
        try:
            limit = 8 * 1024
            page, payload = call(
                primary, "list_tools", pb.ListToolsRequest(limit=200), limit=limit
            )
            assert 0 < len(page.tools) < 20 and page.next_after
            assert len(payload) <= limit // 2 + 1024
            # The next page continues where this one ended, to the last tool.
            seen = [t.definition.id for t in page.tools]
            after = page.next_after
            while after:
                page, _ = call(
                    primary,
                    "list_tools",
                    pb.ListToolsRequest(limit=200, after=after),
                    limit=limit,
                )
                seen += [t.definition.id for t in page.tools]
                after = page.next_after
            assert seen == sorted(seen) and len(seen) == 23
        finally:
            primary._dispatch.close()

    def test_an_oversized_best_match_does_not_cost_the_matches_after_it(self, registry):
        publish(
            registry,
            "acme.huge",
            "enormous",
            "Get the weather forecast for a city and report a bug.",
            input_schema={"type": "object", "x": "y" * 20000},
        )
        primary = ToolRegistryPrimaryAdapterNATS(registry, SECRET)
        try:
            found, _ = call(
                primary,
                "search_tools",
                pb.SearchToolsRequest(query="weather forecast city", limit=10),
                limit=8192,
            )
            assert "acme.huge/enormous@1" not in ids(found)
            assert "acme.weather/get_forecast@1" in ids(found)
            assert len(found.matches) == 3  # the three small ones
            assert found.truncated
            # Fully served: nothing to flag.
            whole, _ = call(
                primary, "search_tools", pb.SearchToolsRequest(query="x", limit=10)
            )
            assert not whole.truncated
        finally:
            primary._dispatch.close()

    def test_a_search_cut_at_the_budget_says_so(self, registry):
        for n in range(20):
            publish(
                registry,
                "acme.bulk",
                f"tool_{n:02d}",
                "Get the weather forecast. " * 20,
                input_schema={"type": "object", "x": "y" * 400},
            )
        primary = ToolRegistryPrimaryAdapterNATS(registry, SECRET)
        try:
            found, payload = call(
                primary,
                "search_tools",
                pb.SearchToolsRequest(query="weather forecast", limit=30),
                limit=8 * 1024,
            )
            assert 0 < len(found.matches) < 23 and found.truncated
            assert len(payload) <= 4 * 1024 + 1024
        finally:
            primary._dispatch.close()

    def test_one_definition_above_the_limit_is_neither_listed_nor_returned(
        self, registry
    ):
        publish(
            registry,
            "acme.huge",
            "enormous",
            "Far too large.",
            input_schema={"type": "object", "x": "y" * 20000},
        )
        primary = ToolRegistryPrimaryAdapterNATS(registry, SECRET)
        try:
            listed, _ = call(primary, "list_tools", pb.ListToolsRequest(), limit=8192)
            assert "acme.huge/enormous@1" not in [t.definition.id for t in listed.tools]
            assert len(listed.tools) == 3
            got, _ = call(
                primary,
                "get_tool",
                pb.GetToolRequest(ref="acme.huge/enormous"),
                limit=8192,
            )
            assert got.error.code == "INVALID_ARGUMENT"
        finally:
            primary._dispatch.close()

    def test_a_definition_json_cannot_carry_is_left_out(self, registry):
        publish(
            registry,
            "acme.odd",
            "not_json",
            "Has a NaN in its schema.",
            input_schema={"type": "object", "default": math.nan},
        )
        primary = ToolRegistryPrimaryAdapterNATS(registry, SECRET)
        try:
            listed, _ = call(primary, "list_tools", pb.ListToolsRequest())
            assert "acme.odd/not_json@1" not in [t.definition.id for t in listed.tools]
            assert len(listed.tools) == 3
        finally:
            primary._dispatch.close()
