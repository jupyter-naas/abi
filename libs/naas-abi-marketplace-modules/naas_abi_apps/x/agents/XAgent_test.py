"""Offline tests of the X agent: its tools, the spend ledger of its search tool,
and its SPARQL templates on what the search pipeline writes."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from naas_abi_apps.common.testing import (
    FakeTripleStore,
    MemoryStorage,
    bound_tool_names,
    fake_engine,
)
from naas_abi_apps.x.agents import XAgent
from naas_abi_apps.x.configuration import XConfiguration
from naas_abi_apps.x.integrations import XIntegration
from naas_abi_apps.x.pipelines.XSearchRecentTweetsPipeline import (
    XSearchRecentTweetsPipeline,
    XSearchRecentTweetsPipelineConfiguration,
    XSearchRecentTweetsPipelineParameters,
)
from naas_abi_apps.x.services import SyncModule, SyncService

# Tool names the agent exposes. API tools come from the XIntegration `as_tools`
# factory; SPARQL tools come from XSparqlQueries.ttl.
EXPECTED_API_TOOL_NAMES = {
    "x_get_user_by_id",
    "x_get_user_by_username",
    "x_get_users_by_ids",
    "x_get_users_by_usernames",
    "x_get_user_tweets",
    "x_get_user_mentions",
    "x_get_user_liked_tweets",
    "x_get_user_followers",
    "x_get_user_following",
    "x_get_tweet_by_id",
    "x_get_tweets_by_ids",
    "x_search_recent_tweets",
    "x_count_recent_tweets",
}

EXPECTED_SPARQL_TOOL_NAMES = {
    "find_top_liked_tweets",
    "find_top_retweeted_tweets",
    "find_top_impression_tweets",
    "find_top_engaging_tweets",
    "find_tweets_by_author",
    "find_tweets_by_username",
    "find_tweets_containing_keyword",
    "find_tweets_in_language",
    "find_tweets_since",
    "find_tweet_by_id",
    "find_top_authors_by_tweet_count",
    "find_language_distribution",
    "find_tweets_by_search_query",
    "list_ingested_search_queries",
}


# The SDK Agent adds its own tools (the time of day).
SDK_TOOLS = {"get_time_date"}


class FakeModule:
    """What ``create_agent`` reads of the SDK ``ABIModule``."""

    module_id = "applications.x"

    def __init__(self, token: str | None, **settings: Any) -> None:
        self.engine = fake_engine()
        self.engine.services.triple_store = FakeTripleStore()
        self.engine.services.object_storage = MemoryStorage()
        self.configuration = SimpleNamespace(**{**asdict(XConfiguration()), **settings})
        self.bearer_token = token

    def start(self) -> None:
        """As ``ABIModule.on_initialized``, on the running loop."""
        self.sync = SyncModule(self, asyncio.get_running_loop())


def build(module: FakeModule):
    async def main():
        module.start()
        return await XAgent.create_agent(module)

    return asyncio.run(main())


def test_without_a_token_the_agent_has_the_graph_tools_only() -> None:
    module = FakeModule(None)
    build(module)
    assert bound_tool_names(module.engine) - SDK_TOOLS == EXPECTED_SPARQL_TOOL_NAMES


def test_with_a_token_the_agent_has_every_tool() -> None:
    module = FakeModule("token")
    agent = build(module)

    assert agent.name == XAgent.NAME == "X"
    assert bound_tool_names(module.engine) - SDK_TOOLS == (
        EXPECTED_API_TOOL_NAMES | EXPECTED_SPARQL_TOOL_NAMES
    )
    assert module.engine.services.model_registry.asked == [""]


def test_the_chat_model_comes_from_the_configuration() -> None:
    module = FakeModule(None, chat_model="openai/gpt-x")
    build(module)
    assert module.engine.services.model_registry.asked == ["openai/gpt-x"]


def test_the_suggestions_fit_an_agent_descriptor() -> None:
    from naas_abi_sdk import AgentDescriptor

    descriptor = AgentDescriptor(
        XAgent.NAME,
        XAgent.DESCRIPTION,
        avatar_url=XAgent.LOGO_URL,
        suggestions=XAgent.SUGGESTIONS,
    )
    assert len(descriptor.suggestions) == 7


def test_caps_come_from_the_configuration() -> None:
    limits = XAgent.agent_search_limits(
        SimpleNamespace(agent_daily_max_usd=0.5, agent_monthly_max_tweets=10)
    )
    assert limits.cost_per_tweet_usd == 0.005
    assert (limits.daily_tweet_cap, limits.monthly_tweet_cap) == (100, 10)
    unset = XAgent.agent_search_limits(SimpleNamespace())
    assert (unset.daily_tweet_cap, unset.monthly_tweet_cap) == (None, None)


# --------------------------------------------------- the search spends credits


def test_the_search_tool_goes_through_the_agent_ledger(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def api(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [{"id": "9"}, {"id": "8"}],
                "meta": {"newest_id": "9", "oldest_id": "8", "result_count": 2},
            },
        )

    real = XIntegration.x_integration_for
    monkeypatch.setattr(
        XAgent,
        "x_integration_for",
        lambda module: real(module, transport=httpx.MockTransport(api)),
    )
    module = FakeModule("token", agent_daily_max_tweets=2)
    storage = module.engine.services.object_storage

    async def main() -> tuple[dict, dict]:
        module.start()
        tools = {t.name: t for t in XAgent.integration_tools(module)}
        search = tools["x_search_recent_tweets"]
        first = await search.ainvoke({"query": "drones"})
        second = await search.ainvoke({"query": "drones"})
        return first, second

    first, second = asyncio.run(main())

    assert first["budget_blocked"] is False
    assert first["budget"]["tweets_today"] == 2
    assert first["file_path"].startswith("x/search_recent_tweets/drones/")
    ledger = json.loads(storage.objects[("x/_budget", "agent.json")])
    assert list(ledger["daily"].values()) == [2]
    # The cap is spent: no second call to X.
    assert second["budget_blocked"] is True
    assert "daily X budget reached: 2/2 tweets" in second["budget_reason"]
    assert len(requests) == 1


# ----------------------------------------------------- the graph SPARQL tools

ENVELOPE = {
    "query": "drones lang:en",
    "options": {"max_results": 10},
    "results": {
        "data": [
            {
                "id": "101",
                "text": "Drones over the stadium",
                "author_id": "1",
                "lang": "en",
                "public_metrics": {"like_count": 7, "retweet_count": 2},
            },
            {
                "id": "102",
                "text": "Another drone",
                "author_id": "1",
                "lang": "fr",
                "public_metrics": {"like_count": 3, "retweet_count": 0},
            },
        ],
        "includes": {"users": [{"id": "1", "username": "alice", "name": "Alice"}]},
        "meta": {"newest_id": "102", "oldest_id": "101", "result_count": 2},
    },
    "started_at": "2026-07-07T14:00:05+00:00",
    "ended_at": "2026-07-07T14:00:06+00:00",
}


@pytest.fixture
def graph_tools() -> dict[str, Any]:
    store, storage = FakeTripleStore(), MemoryStorage()
    asyncio.run(storage.put_object("x/s", "e.json", json.dumps(ENVELOPE).encode()))
    XSearchRecentTweetsPipeline(
        XSearchRecentTweetsPipelineConfiguration(
            triple_store=SyncService(store, asyncio.run),
            object_storage=SyncService(storage, asyncio.run),
        )
    ).run(XSearchRecentTweetsPipelineParameters(file_path="x/s/e.json"))
    module = FakeModule(None)
    module.engine.services.triple_store = store
    from naas_abi_apps.common.sparql_templates import module_queries, query_tools

    tools = query_tools(
        module_queries(XAgent.PACKAGE_DIR), store, names=XAgent.SPARQL_TOOLS
    )
    return {t.name: t for t in tools}


def test_the_graph_tools_read_what_the_pipeline_wrote(graph_tools) -> None:
    liked = asyncio.run(graph_tools["find_top_liked_tweets"].ainvoke({"limit": "5"}))
    assert [row["tweetId"] for row in liked] == ["101", "102"]
    assert liked[0]["tweetUrl"] == "https://x.com/i/status/101"

    by_user = asyncio.run(
        graph_tools["find_tweets_by_username"].ainvoke(
            {"username": "@Alice", "limit": "5"}
        )
    )
    assert {row["tweetId"] for row in by_user} == {"101", "102"}

    queries = asyncio.run(
        graph_tools["list_ingested_search_queries"].ainvoke({"limit": "5"})
    )
    assert queries[0]["queryString"] == "drones lang:en"


def test_graph_tool_arguments_are_validated(graph_tools) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        asyncio.run(
            graph_tools["find_top_liked_tweets"].ainvoke({"limit": "5 } DROP ALL"})
        )
