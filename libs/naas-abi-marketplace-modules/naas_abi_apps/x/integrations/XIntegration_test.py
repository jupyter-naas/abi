"""Offline tests of the X integration (``httpx.MockTransport``)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from naas_abi_apps.common.testing import FakeCache, MemoryStorage
from naas_abi_apps.x.integrations.XIntegration import (
    DEFAULT_TWEET_FIELDS,
    XIntegration,
    XIntegrationConfiguration,
    _clamp_end_time,
    as_tools,
    slugify_query,
)
from naas_abi_sdk.integration import IntegrationConnectionError

NASA_USER_ID = "11348282"
TOOL_NAMES = [
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
]


class Api:
    """A scripted X API: ``routes[path]`` is a list of (status, body) answers,
    served in order (the last one repeats). Records every request."""

    def __init__(self, routes: dict[str, list[tuple[int, object]]]):
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answers = self.routes[request.url.path]
        status, body = answers.pop(0) if len(answers) > 1 else answers[0]
        return httpx.Response(status, json=body)

    def params(self, index: int = -1) -> dict[str, str]:
        return dict(self.requests[index].url.params)


def integration(
    api: Api,
    storage: MemoryStorage | None = None,
    cache: FakeCache | None = None,
    token: str = "token",
) -> XIntegration:
    return XIntegration(
        XIntegrationConfiguration(
            bearer_token=token,
            storage=storage,
            cache=cache,
            backoff=(0, 0),
            transport=httpx.MockTransport(api),
        )
    )


def stored(storage: MemoryStorage, prefix: str) -> dict[str, object]:
    return {
        key: json.loads(value)
        for (p, key), value in storage.objects.items()
        if p == prefix
    }


# ----------------------------------------------------------------- lookups


def test_lookup_sends_the_token_and_archives_with_a_copy() -> None:
    user = {"data": {"id": NASA_USER_ID, "username": "NASA"}}
    api = Api({f"/2/users/{NASA_USER_ID}": [(200, user)]})
    storage = MemoryStorage()

    result = asyncio.run(integration(api, storage).get_user_by_id(NASA_USER_ID))

    assert result == user
    assert api.requests[0].headers["Authorization"] == "Bearer token"
    files = stored(storage, "x/get_user_by_id")
    # The file and StorageUtils' timestamped copy, with the same content.
    assert files[f"{NASA_USER_ID}.json"] == user
    copies = [k for k in files if k.endswith(f"_{NASA_USER_ID}.json")]
    assert len(copies) == 1 and files[copies[0]] == user
    raw = storage.objects[("x/get_user_by_id", f"{NASA_USER_ID}.json")]
    assert raw == json.dumps(user, indent=4, ensure_ascii=False).encode()


def test_lookups_are_cached_for_a_day() -> None:
    api = Api({"/2/users/by/username/NASA": [(200, {"data": {"id": "1"}})]})
    cache = FakeCache()
    x = integration(api, cache=cache)

    first = asyncio.run(x.get_user_by_username("NASA"))
    second = asyncio.run(x.get_user_by_username("NASA"))

    assert first == second == {"data": {"id": "1"}}
    assert len(api.requests) == 1
    assert "x:get_user_by_username_NASA" in cache.values


def test_bulk_lookups_join_ids_and_hash_the_file_name() -> None:
    api = Api({"/2/tweets": [(200, {"data": [{"id": "20"}, {"id": "21"}]})]})
    storage = MemoryStorage()

    asyncio.run(integration(api, storage).get_tweets_by_ids(["21", "20"]))

    assert api.params()["ids"] == "21,20"
    (name,) = [k for k in stored(storage, "x/get_tweets_by_ids") if "_" not in k]
    assert len(name) == len("12345678.json")


def test_ids_and_handles_cannot_change_the_path() -> None:
    api = Api({})
    x = integration(api)
    for call in (
        x.get_user_by_id("../tweets"),
        x.get_user_by_username("a/b"),
        x.get_tweet_by_id("1?x=2"),
        x.get_user_tweets("1/../2"),
    ):
        with pytest.raises(ValueError):
            asyncio.run(call)
    assert api.requests == []


def test_timelines_paginate_and_merge_includes() -> None:
    page1 = {
        "data": [{"id": "3"}, {"id": "2"}],
        "includes": {"users": [{"id": "u1"}], "media": [{"media_key": "m1"}]},
        "meta": {
            "newest_id": "3",
            "oldest_id": "2",
            "result_count": 2,
            "next_token": "t",
        },
    }
    page2 = {
        "data": [{"id": "1"}],
        "includes": {"users": [{"id": "u1"}, {"id": "u2"}]},
        "meta": {"oldest_id": "1", "result_count": 1},
    }
    api = Api({f"/2/users/{NASA_USER_ID}/tweets": [(200, page1), (200, page2)]})
    storage = MemoryStorage()

    result = asyncio.run(
        integration(api, storage).get_user_tweets(NASA_USER_ID, max_pages=None)
    )

    assert [t["id"] for t in result["data"]] == ["3", "2", "1"]
    assert result["includes"]["users"] == [{"id": "u1"}, {"id": "u2"}]
    assert result["meta"] == {
        "newest_id": "3",
        "oldest_id": "1",
        "result_count": 3,
        "next_token": "t",
    }
    assert api.params(1)["pagination_token"] == "t"
    assert len(result["sources"]) == 2
    assert all(s.startswith("x/get_all_items/") for s in result["sources"])
    assert stored(storage, "x/get_user_tweets")[f"{NASA_USER_ID}.json"] == result


# ----------------------------------------------------------------- search


def search_page(ids: list[str], next_token: str | None = None) -> dict:
    meta: dict = {"newest_id": ids[0], "oldest_id": ids[-1], "result_count": len(ids)}
    if next_token:
        meta["next_token"] = next_token
    return {"data": [{"id": i, "text": f"tweet {i}"} for i in ids], "meta": meta}


def test_search_saves_the_envelope_where_in_engine_did() -> None:
    api = Api({"/2/tweets/search/recent": [(200, search_page(["9", "8"], "next"))]})
    storage = MemoryStorage()
    query = "(OpenAI OR Anthropic) lang:en"

    envelope = asyncio.run(integration(api, storage).search_recent_tweets(query))

    slug = slugify_query(query)
    assert slug == "(openai_or_anthropic)_lang:en"
    prefix = f"x/search_recent_tweets/{slug}"
    assert envelope["file_path"].startswith(f"{prefix}/")
    assert envelope["file_path"].endswith(f"_{slug}.json")
    files = stored(storage, prefix)
    assert list(files.values()) == [envelope]
    assert set(envelope) == {
        "query",
        "options",
        "results",
        "started_at",
        "ended_at",
        "file_path",
    }
    # max_pages=1 stopped a walk that had more: has_more for the workflow.
    assert envelope["results"]["meta"]["has_more"] is True
    assert envelope["options"]["tweet_fields"] == DEFAULT_TWEET_FIELDS
    params = api.params()
    assert params["query"] == query
    assert params["sort_order"] == "recency"
    assert params["tweet.fields"] == ",".join(DEFAULT_TWEET_FIELDS)


def test_search_without_persist_saves_only_the_pages() -> None:
    api = Api({"/2/tweets/search/recent": [(200, search_page(["9"]))]})
    storage = MemoryStorage()

    envelope = asyncio.run(
        integration(api, storage).search_recent_tweets(
            "q", since_id="5", persist_envelope=False
        )
    )

    assert envelope["file_path"] is None
    assert api.params()["since_id"] == "5"
    assert {p for p, _ in storage.objects} == {"x/get_all_items"}


def test_search_is_never_cached() -> None:
    """A cached search would hand back tweets the spend ledger never saw."""
    api = Api({"/2/tweets/search/recent": [(200, search_page(["9"]))]})
    cache = FakeCache()
    x = integration(api, cache=cache)

    asyncio.run(x.search_recent_tweets("q"))
    asyncio.run(x.search_recent_tweets("q"))

    assert len(api.requests) == 2
    assert cache.values == {}


def test_end_time_is_clamped_before_now() -> None:
    future = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    clamped = _clamp_end_time(future)
    assert datetime.fromisoformat(clamped) < datetime.now(UTC) - timedelta(seconds=10)
    assert _clamp_end_time("2020-01-01T00:00:00Z") == "2020-01-01T00:00:00Z"
    assert _clamp_end_time("not a date") == "not a date"


# --------------------------------------------------------------- failures


def test_transient_errors_are_retried() -> None:
    api = Api(
        {
            "/2/tweets/20": [
                (503, {"title": "Service Unavailable"}),
                (429, {"title": "Too Many Requests"}),
                (200, {"data": {"id": "20"}}),
            ]
        }
    )

    assert asyncio.run(integration(api).get_tweet_by_id("20")) == {"data": {"id": "20"}}
    assert len(api.requests) == 3


def test_retries_are_bounded_and_the_last_error_raised() -> None:
    api = Api({"/2/tweets/20": [(503, {"title": "Service Unavailable"})]})

    with pytest.raises(IntegrationConnectionError, match="X API 503"):
        asyncio.run(integration(api).get_tweet_by_id("20"))
    assert len(api.requests) == 3  # one attempt, then one per backoff sleep


def test_client_errors_fail_fast_with_the_body() -> None:
    api = Api({"/2/tweets/20": [(400, {"title": "Invalid Request"})]})

    with pytest.raises(IntegrationConnectionError, match="Invalid Request"):
        asyncio.run(integration(api).get_tweet_by_id("20"))
    assert len(api.requests) == 1


def test_no_token_fails_without_a_request() -> None:
    api = Api({})
    with pytest.raises(IntegrationConnectionError, match="X_BEARER_TOKEN"):
        asyncio.run(integration(api, token="").get_tweet_by_id("20"))
    assert api.requests == []


# ------------------------------------------------------------------ counts


def test_counts_sum_the_pages_and_save_the_envelope() -> None:
    bucket = {"start": "2026-07-07T12:00:00.000Z", "end": "2026-07-07T13:00:00.000Z"}
    api = Api(
        {
            "/2/tweets/counts/recent": [
                (
                    200,
                    {
                        "data": [{**bucket, "tweet_count": 10}],
                        "meta": {"total_tweet_count": 10, "next_token": "t"},
                    },
                ),
                (
                    200,
                    {
                        "data": [{**bucket, "tweet_count": 5}],
                        "meta": {"total_tweet_count": 5},
                    },
                ),
            ]
        }
    )
    storage = MemoryStorage()

    envelope = asyncio.run(
        integration(api, storage).count_recent_tweets(
            "q", start_time="2026-07-07T12:00:00Z", end_time="2026-07-07T14:00:00Z"
        )
    )

    assert envelope["total_tweet_count"] == 15
    assert envelope["results"]["meta"]["total_tweet_count"] == 15
    assert len(envelope["results"]["data"]) == 2
    assert envelope["options"]["granularity"] == "hour"
    assert api.params(1)["pagination_token"] == "t"
    assert envelope["file_path"].startswith("x/count_recent_tweets/q/")
    assert list(stored(storage, "x/count_recent_tweets/q").values()) == [envelope]


# ------------------------------------------------------------------- tools


def test_the_thirteen_tools_keep_their_names() -> None:
    tools = as_tools(XIntegrationConfiguration(bearer_token="token"))
    assert [t.name for t in tools] == TOOL_NAMES
    assert all(t.coroutine is not None for t in tools)


def test_a_tool_fills_the_defaults_the_model_left_out() -> None:
    api = Api({f"/2/users/{NASA_USER_ID}/mentions": [(200, search_page(["1"]))]})
    tools = {
        t.name: t
        for t in as_tools(
            XIntegrationConfiguration(
                bearer_token="token", transport=httpx.MockTransport(api)
            )
        )
    }

    result = asyncio.run(
        tools["x_get_user_mentions"].ainvoke({"user_id": NASA_USER_ID})
    )

    assert [t["id"] for t in result["data"]] == ["1"]
    assert api.params()["max_results"] == "100"


def test_the_search_tool_can_be_routed_elsewhere() -> None:
    calls: list[dict] = []

    async def search(query: str, **options: object) -> dict:
        calls.append({"query": query, **options})
        return {"routed": True}

    tools = {
        t.name: t
        for t in as_tools(
            XIntegrationConfiguration(bearer_token="token"),
            search_recent_tweets=search,
        )
    }

    result = asyncio.run(tools["x_search_recent_tweets"].ainvoke({"query": "q"}))

    assert result == {"routed": True}
    assert calls[0]["query"] == "q" and calls[0]["max_pages"] == 1
