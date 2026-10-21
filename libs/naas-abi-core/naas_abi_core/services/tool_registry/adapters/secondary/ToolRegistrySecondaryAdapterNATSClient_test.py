import json
from unittest.mock import AsyncMock

import pytest
from naas_abi_core.services.tool_registry.adapters.secondary.ToolRegistrySecondaryAdapterNATSClient import (
    MAX_LIST_PAGES,
    ToolRegistrySecondaryAdapterNATSClient,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ToolCatalogError,
    ToolCatalogRequestError,
    ToolFilter,
    ToolNotFoundError,
    ToolRegistryError,
    ToolSearchUnavailableError,
)
from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb
from naas_abi_sdk.transport import RPCError


def entry(name, *, missing=()):
    return pb.ToolEntry(
        definition=pb.ToolDefinition(
            id=f"acme.crm/{name}@1",
            namespace="acme.crm",
            name=name,
            version="1",
            module="acme.crm",
            description=f"Does {name}.",
            input_schema_json=json.dumps({"type": "object"}).encode(),
        ),
        availability=pb.ToolAvailability(
            available=not missing, missing_config=list(missing)
        ),
    )


@pytest.fixture
def client():
    client = ToolRegistrySecondaryAdapterNATSClient(
        "nats://127.0.0.1:1", "s" * 32, timeout_seconds=5
    )
    client.remote = AsyncMock()
    yield client


def test_a_tool_the_catalog_does_not_show_is_not_found(client):
    client.remote.get_tool.side_effect = RPCError("TOOL_NOT_FOUND", "no")
    with pytest.raises(ToolNotFoundError, match="acme.crm/nothing"):
        client.get_tool("acme.crm/nothing")


def test_search_that_the_serving_engine_cannot_rank_is_unavailable(client):
    client.remote.search_tools.side_effect = RPCError("SEARCH_UNAVAILABLE", "no")
    with pytest.raises(ToolSearchUnavailableError):
        client.search_tools("x", 3)


def test_other_failures_are_not_hidden(client):
    client.remote.search_tools.side_effect = RPCError("INTERNAL", "boom")
    with pytest.raises(ToolCatalogError, match="INTERNAL: boom"):
        client.search_tools("x", 3)
    client.remote.search_tools.side_effect = TimeoutError()
    with pytest.raises(ToolCatalogError, match="did not answer"):
        client.search_tools("x", 3)
    client.remote.get_tool.side_effect = RPCError("INVALID_ARGUMENT", "bad ref")
    with pytest.raises(ToolCatalogRequestError, match="bad ref"):
        client.get_tool("bad")


def test_a_search_sends_the_limit_the_contract_allows_and_the_filter(client):
    client.remote.search_tools.return_value = pb.SearchToolsResponse(
        matches=[pb.ToolMatch(tool=entry("sync", missing=("api_key",)), score=0.8)]
    )

    answer = client.search_tools(
        "sync", 500, 0.2, ToolFilter(modules=("acme.crm",), available_only=True)
    )
    (result,) = answer.results
    assert not answer.truncated

    request = client.remote.search_tools.call_args.args[0]
    assert request.limit == 50 and request.min_score == pytest.approx(0.2)
    assert (
        list(request.filter.modules) == ["acme.crm"] and request.filter.available_only
    )
    assert result.tool_id == "acme.crm/sync@1" and result.score == 0.8
    assert result.availability.missing_config == ("api_key",)
    assert result.definition.name == "sync"


def test_a_search_without_a_min_score_sends_none(client):
    client.remote.search_tools.return_value = pb.SearchToolsResponse()
    client.search_tools("x", 3)
    assert not client.remote.search_tools.call_args.args[0].HasField("min_score")


def test_listing_reads_every_page(client):
    client.remote.list_tools.side_effect = [
        pb.ListToolsResponse(tools=[entry("a")], next_after="acme.crm/a@1"),
        pb.ListToolsResponse(tools=[entry("b")]),
    ]
    assert [l.definition.name for l in client.list_tools()] == ["a", "b"]
    assert client.remote.list_tools.call_args_list[1].args[0].after == "acme.crm/a@1"


def test_a_catalog_that_never_ends_is_refused(client):
    client.remote.list_tools.return_value = pb.ListToolsResponse(
        tools=[entry("a")], next_after="acme.crm/a@1"
    )
    with pytest.raises(ToolCatalogError, match="more than"):
        client.list_tools()
    assert client.remote.list_tools.await_count == MAX_LIST_PAGES


def test_a_definition_that_does_not_match_its_id_is_refused(client):
    bad = entry("a")
    bad.definition.id = "acme.crm/other@1"
    client.remote.get_tool.return_value = pb.GetToolResponse(tool=bad)
    with pytest.raises(ToolRegistryError, match="does not match"):
        client.get_tool("acme.crm/a")


def test_the_truncation_the_catalog_reports_is_passed_on(client):
    client.remote.search_tools.return_value = pb.SearchToolsResponse(
        matches=[pb.ToolMatch(tool=entry("a"), score=0.5)], truncated=True
    )
    assert client.search_tools("x", 3).truncated


def test_a_query_the_catalog_would_refuse_is_made_acceptable_not_an_error(client):
    client.remote.search_tools.return_value = pb.SearchToolsResponse()
    for blank in ("", "   ", "\n\t"):
        assert client.search_tools(blank, 3).results == ()
    client.remote.search_tools.assert_not_called()

    client.search_tools("  " + "x" * 5000 + "  ", 3)
    sent = client.remote.search_tools.call_args.args[0].query
    assert sent == "x" * 2000


def test_a_request_the_catalog_still_refuses_is_a_catalog_error(client):
    client.remote.search_tools.side_effect = RPCError("INVALID_ARGUMENT", "min_score")
    with pytest.raises(ToolRegistryError) as raised:
        client.search_tools("x", 3, float("nan"))
    assert not isinstance(raised.value, ValueError)


def test_one_bad_definition_does_not_hide_the_catalog(client):
    bad = entry("bad")
    bad.definition.id = "acme.crm/other@1"
    client.remote.list_tools.return_value = pb.ListToolsResponse(
        tools=[entry("a"), bad, entry("b")]
    )
    assert [l.definition.name for l in client.list_tools()] == ["a", "b"]
    client.remote.search_tools.return_value = pb.SearchToolsResponse(
        matches=[
            pb.ToolMatch(tool=bad, score=0.9),
            pb.ToolMatch(tool=entry("a"), score=0.5),
        ]
    )
    assert [r.tool_id for r in client.search_tools("x", 3).results] == ["acme.crm/a@1"]


def test_no_transport_exists_until_the_catalog_is_read():
    client = ToolRegistrySecondaryAdapterNATSClient("nats://127.0.0.1:1", "s" * 32)
    assert client._transport is None
    client.close()  # nothing to close
    assert client.remote is not None and client._transport is not None
    client.close()
    assert client._transport is None
