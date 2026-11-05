"""The LinkedIn client against a fake Voyager API (``httpx.MockTransport``)."""

from __future__ import annotations

import asyncio
import json
import urllib.parse
from typing import Any

import httpx
from naas_abi_apps.common.testing import FakeCache, MemoryStorage
from naas_abi_apps.linkedin.integrations.LinkedInIntegration import (
    LinkedInIntegration,
    LinkedInIntegrationConfiguration,
    activity_id,
    as_tools,
    organization_public_id,
)

POST = "https://www.linkedin.com/posts/alice_hello-activity-7100000000000000000-abcd"
ME = "https://www.linkedin.com/in/alice"

TOP_CARD = {
    "data": {
        "data": {
            "identityDashProfilesByMemberIdentity": {
                "*elements": ["urn:li:fsd_profile:ACoAAAlice"]
            }
        }
    },
    "included": [
        {
            "entityUrn": "urn:li:fsd_profile:ACoAAAlice",
            "publicIdentifier": "alice",
            "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
            "firstName": "Alice",
        }
    ],
}
ORGANIZATION = {
    "data": {"*elements": ["urn:li:fs_normalized_company:42"]},
    "included": [
        {
            "$type": "com.linkedin.voyager.organization.Company",
            "name": "Demo",
            "trackingId": "x",
            "entityUrn": "urn:li:fs_normalized_company:42",
            "logo": {
                "image": {
                    "rootUrl": "https://media/",
                    "artifacts": [
                        {"fileIdentifyingUrlPathSegment": "small.png"},
                        {"fileIdentifyingUrlPathSegment": "large.png"},
                    ],
                }
            },
        }
    ],
}


def people_page(start: int, total: int) -> dict[str, Any]:
    return {
        "data": {
            "data": {
                "searchDashClustersByAll": {"metadata": {"totalResultCount": total}}
            }
        },
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.search.EntityResultViewModel",
                "navigationUrl": f"https://www.linkedin.com/in/p{start}?miniProfile%3AACoAA{start}",
                "title": {"text": f"Person {start}"},
            }
        ],
    }


class Voyager:
    """Answers by path; records each request."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = urllib.parse.unquote(str(request.url))
        for marker, answer in self.routes.items():
            if marker in url:
                body = answer(url) if callable(answer) else answer
                if isinstance(body, httpx.Response):
                    return body
                return httpx.Response(200, json=body)
        return httpx.Response(404, text="no route")


def integration(voyager: Voyager, **kwargs: Any) -> LinkedInIntegration:
    return LinkedInIntegration(
        LinkedInIntegrationConfiguration(
            li_at="secret-li-at",
            JSESSIONID='"ajax:123"',
            linkedin_url=ME,
            transport=httpx.MockTransport(voyager),
            page_delay=0,
            **kwargs,
        )
    )


def test_urls_are_parsed() -> None:
    assert organization_public_id("https://www.linkedin.com/school/hec/") == {
        "result": "hec"
    }
    assert "error" in organization_public_id("https://www.linkedin.com/in/x")
    assert activity_id(POST) == {"result": "7100000000000000000"}
    assert activity_id("urn:li:activity:12/") == {"result": "12"}


def test_an_error_never_returns_the_session() -> None:
    voyager = Voyager({"/organization/companies": httpx.Response(403, text="nope")})
    result = asyncio.run(
        integration(voyager).get_organization_info(
            "https://www.linkedin.com/company/demo/"
        )
    )
    assert result["error"] == "LinkedIn API request failed: HTTP 403"
    text = json.dumps(result)
    assert "secret-li-at" not in text and "ajax:123" not in text
    sent = voyager.requests[0]
    assert sent.headers["csrf-token"] == "ajax:123"
    assert "li_at=secret-li-at" in sent.headers["cookie"]


def test_responses_are_archived_cleaned_and_cached() -> None:
    voyager = Voyager({"/organization/companies": ORGANIZATION})
    storage, cache = MemoryStorage(), FakeCache()
    client = integration(voyager, storage=storage, cache=cache)
    url = "https://www.linkedin.com/company/demo/"

    cleaned = asyncio.run(client.get_organization_info(url, return_cleaned_json=True))
    again = asyncio.run(client.get_organization_id(url))

    [company] = cleaned["com.linkedin.voyager.organization.Company"]
    assert company["name"] == "Demo" and company["logo"] == "https://media/large.png"
    assert "trackingId" not in company
    assert again == {"result": "42"}
    assert len(voyager.requests) == 1  # the second call came from the cache
    assert all("secret-li-at" not in key for key in cache.values)
    assert {k for _, k in storage.objects} == {"demo.json", "demo_cleaned.json"}


def test_comments_are_paginated() -> None:
    def comments(url: str) -> dict[str, Any]:
        start = int(url.split("'start': ")[1].split(",")[0])
        return {
            "data": {
                "data": {
                    "socialDashCommentsBySocialDetail": {
                        "*elements": [f"c{start}"],
                        "paging": {"total": 2},
                    }
                }
            },
            "included": [{"$type": "Comment", "text": f"comment {start}"}],
        }

    voyager = Voyager({"voyagerSocialDashComments": comments})
    result = asyncio.run(integration(voyager).get_post_comments(POST, count=1))

    elements = result["data"]["data"]["socialDashCommentsBySocialDetail"]["*elements"]
    assert elements == ["c0", "c1"]
    assert len(result["included"]) == 2
    assert len(voyager.requests) == 2


def test_search_people_without_an_organization_exports_the_people() -> None:
    def search(url: str) -> dict[str, Any]:
        start = int(url.split("variables=(start:")[1].split(",")[0])
        return people_page(start, total=2)

    voyager = Voyager(
        {"voyagerIdentityDashProfiles": TOP_CARD, "voyagerSearchDashClusters": search}
    )
    storage = MemoryStorage()
    result = asyncio.run(
        integration(voyager, storage=storage).search_people(count=1, location="France")
    )

    assert result["total_connections"] == 2
    assert [p["name"] for p in result["connections"]] == ["Person 0", "Person 1"]
    assert result["connections"][0]["profile_url"] == "https://www.linkedin.com/in/p0"
    assert result["excel_url"].endswith("alice_search_people_F_105015875.xlsx")
    assert (
        "linkedin/search_people/alice/F/_all/105015875",
        "alice_search_people_F_105015875.xlsx",
    ) in storage.objects


def test_an_empty_feed_is_an_error() -> None:
    voyager = Voyager(
        {
            "voyagerIdentityDashProfiles": TOP_CARD,
            "voyagerFeedDashProfileUpdates": {
                "data": {"data": {"feedDashProfileUpdatesByMemberShareFeed": {}}}
            },
        }
    )
    result = asyncio.run(integration(voyager).get_profile_posts_feed(ME))
    assert result == {"error": f"No post found for LinkedIn profile '{ME}'"}


def test_tools_take_their_optional_arguments_by_name() -> None:
    voyager = Voyager(
        {
            "voyagerIdentityDashProfiles": TOP_CARD,
            "voyagerSearchDashClusters": people_page(0, 1),
        }
    )
    tools = {
        t.name: t
        for t in as_tools(
            LinkedInIntegrationConfiguration(
                li_at="a",
                JSESSIONID="b",
                linkedin_url=ME,
                transport=httpx.MockTransport(voyager),
                page_delay=0,
            )
        )
    }
    assert len(tools) == 12
    result = asyncio.run(tools["linkedin_search_people"].coroutine(limit=5))
    assert result["connections_returned"] == 1
    top_card = asyncio.run(tools["linkedin_get_profile_top_card"].coroutine(url=ME))
    assert (
        top_card["com.linkedin.voyager.dash.identity.profile.Profile"][0]["firstName"]
        == "Alice"
    )
