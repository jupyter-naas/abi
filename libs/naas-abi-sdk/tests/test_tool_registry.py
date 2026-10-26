import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb

from naas_abi_sdk.catalog import OPERATIONS
from naas_abi_sdk.module import EngineProxy, ModuleDependencies
from naas_abi_sdk.services import FACTORIES, service_proxy
from naas_abi_sdk.services.errors import ToolNotFound, ToolSearchUnavailable
from naas_abi_sdk.services.tool_registry import ToolRegistryService
from naas_abi_sdk.transport import RPCError


def entry(name, *, secret=False, missing=(), scopes=()):
    return pb.ToolEntry(
        definition=pb.ToolDefinition(
            id=f"acme.crm/{name}@1",
            namespace="acme.crm",
            name=name,
            version="1",
            module="acme.crm",
            description=f"Does {name}.",
            input_schema_json=json.dumps({"type": "object"}).encode(),
            tags=["crm"],
            requirements=pb.ToolRequirements(
                config=[
                    pb.ConfigRequirement(key="api_key", secret=secret, required=True)
                ]
            ),
            required_scopes=list(scopes),
        ),
        availability=pb.ToolAvailability(
            available=not missing, missing_config=list(missing)
        ),
    )


def test_the_catalog_lists_the_service_and_a_module_may_depend_on_it():
    assert OPERATIONS["tool_registry"] == [
        "list_tools",
        "get_tool",
        "search_tools",
        "invoke_tool",
        "cancel_tool",
    ]
    assert FACTORIES["tool_registry"] is ToolRegistryService
    client = SimpleNamespace(tool_registry=AsyncMock(), bus=object())
    engine = EngineProxy(client, ModuleDependencies(services=("tool_registry",)))
    assert engine.services.tool_registry_available()
    assert isinstance(engine.services.tool_registry, ToolRegistryService)
    assert isinstance(
        service_proxy("tool_registry", AsyncMock(), None), ToolRegistryService
    )


def test_a_definition_is_data_with_requirements_that_name_but_never_hold_secrets():
    client = AsyncMock()
    client.get_tool.return_value = pb.GetToolResponse(
        tool=entry("sync", secret=True, missing=("api_key",), scopes=("crm:read",))
    )

    result = asyncio.run(ToolRegistryService(client).get_tool("acme.crm/sync"))

    assert client.get_tool.call_args.args[0].ref == "acme.crm/sync"
    definition = result.definition
    assert definition.id == "acme.crm/sync@1"
    assert definition.input_schema == {"type": "object"}
    assert definition.output_schema is None
    assert definition.tags == ("crm",) and definition.required_scopes == ("crm:read",)
    assert definition.remote is False
    (requirement,) = definition.config
    assert (requirement.key, requirement.secret, requirement.required) == (
        "api_key",
        True,
        True,
    )
    assert not result.availability.available
    assert result.availability.missing_config == ("api_key",)


def test_search_sends_limit_filter_and_min_score_and_ranks_as_answered():
    client = AsyncMock()
    client.search_tools.return_value = pb.SearchToolsResponse(
        matches=[
            pb.ToolMatch(tool=entry("sync"), score=0.9),
            pb.ToolMatch(tool=entry("export"), score=0.4),
        ]
    )

    matches = asyncio.run(
        ToolRegistryService(client).search_tools(
            "sync contacts",
            limit=2,
            min_score=0.3,
            modules=["acme.crm"],
            tags=["crm"],
            available_only=True,
        )
    )

    request = client.search_tools.call_args.args[0]
    assert request.query == "sync contacts" and request.limit == 2
    assert request.min_score == pytest.approx(0.3)
    assert list(request.filter.modules) == ["acme.crm"]
    assert list(request.filter.tags) == ["crm"] and request.filter.available_only
    assert [(m.tool_id, m.score) for m in matches] == [
        ("acme.crm/sync@1", 0.9),
        ("acme.crm/export@1", 0.4),
    ]
    assert matches[0].definition.name == "sync" and matches[0].availability.available


def test_search_without_a_min_score_sends_none():
    client = AsyncMock()
    client.search_tools.return_value = pb.SearchToolsResponse()

    asyncio.run(ToolRegistryService(client).search_tools("x"))

    assert not client.search_tools.call_args.args[0].HasField("min_score")


@pytest.mark.parametrize(
    "arguments",
    [
        {"limit": 0},
        {"limit": 51},
        {"min_score": float("nan")},
        {"min_score": float("inf")},
    ],
)
def test_search_refuses_what_the_contract_refuses_before_sending(arguments):
    client = AsyncMock()
    with pytest.raises(ValueError):
        asyncio.run(ToolRegistryService(client).search_tools("x", **arguments))
    client.search_tools.assert_not_called()


def test_a_bare_string_is_not_a_list_of_modules():
    with pytest.raises(TypeError):
        asyncio.run(ToolRegistryService(AsyncMock()).list_tools(modules="acme.crm"))


def test_listing_follows_pages_until_the_last():
    client = AsyncMock()
    client.list_tools.side_effect = [
        pb.ListToolsResponse(tools=[entry("a"), entry("b")], next_after="acme.crm/b@1"),
        pb.ListToolsResponse(tools=[entry("c")]),
    ]

    listed = asyncio.run(ToolRegistryService(client).list_tools(tags=["crm"]))

    assert [e.definition.name for e in listed] == ["a", "b", "c"]
    first, second = (call.args[0] for call in client.list_tools.call_args_list)
    assert first.after == "" and second.after == "acme.crm/b@1"
    assert first.limit == 200 and list(first.filter.tags) == ["crm"]


def test_listing_gives_up_on_a_catalog_that_never_ends():
    client = AsyncMock()
    client.list_tools.return_value = pb.ListToolsResponse(
        tools=[entry("a")], next_after="acme.crm/a@1"
    )

    with pytest.raises(RuntimeError, match="too large"):
        asyncio.run(ToolRegistryService(client).list_tools())


@pytest.mark.parametrize(
    "code, error",
    [("TOOL_NOT_FOUND", ToolNotFound), ("SEARCH_UNAVAILABLE", ToolSearchUnavailable)],
)
def test_engine_errors_become_portable_domain_errors(code, error):
    client = AsyncMock()
    client.get_tool.side_effect = RPCError(code, "no")
    client.search_tools.side_effect = RPCError(code, "no")
    service = ToolRegistryService(client)

    with pytest.raises(error):
        asyncio.run(service.get_tool("acme.crm/sync"))
    with pytest.raises(error):
        asyncio.run(service.search_tools("sync"))
