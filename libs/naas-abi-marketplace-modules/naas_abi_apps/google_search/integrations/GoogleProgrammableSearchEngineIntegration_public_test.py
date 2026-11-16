"""googlesearch_extract_content_from_url reads public pages only, and keeps none.

The listener of ``common/public_fetch_test`` stands for a service on the
module's own network; "public.example.com" resolves to a public address routed
to it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from naas_abi_apps.common.public_fetch_test import (  # noqa: F401 - fixture
    LOOPBACK,
    PUBLIC_NAME,
    TOKEN,
    Listener,
    listener,
)
from naas_abi_apps.common.testing import MemoryStorage
from naas_abi_apps.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegrationConfiguration,
    as_tools,
)


@pytest.fixture
def extract() -> tuple[Any, MemoryStorage]:
    """The tool as the agent builds it, with object storage recorded."""
    storage = MemoryStorage()
    tools = as_tools(
        GoogleProgrammableSearchEngineIntegrationConfiguration(
            api_key="k", search_engine_id="cx", storage=storage
        )
    )
    tool = next(t for t in tools if t.name == "googlesearch_extract_content_from_url")
    return tool, storage


def _invoke(tool: Any, url: str) -> str:
    try:
        return str(asyncio.run(tool.ainvoke({"url": url})))
    except Exception as exc:  # noqa: BLE001 - a refusal surfaces as an exception
        return f"refused: {exc}"


@pytest.mark.parametrize("host", ["127.0.0.1", "127.1", "localhost", "fuseki"])
def test_googlesearch_extract_content_keeps_to_public_addresses(
    listener: Listener,  # noqa: F811
    extract: tuple[Any, MemoryStorage],
    host: str,
) -> None:
    tool, storage = extract
    out = _invoke(tool, f"http://{host}:{listener.port}/admin")
    assert TOKEN not in out
    assert listener.hits == []
    assert storage.objects == {}


def test_googlesearch_extract_content_keeps_redirects_to_public_addresses(
    listener: Listener,  # noqa: F811
    extract: tuple[Any, MemoryStorage],
) -> None:
    tool, _ = extract
    listener.redirect_to = f"http://{LOOPBACK}:{listener.port}/admin"
    out = _invoke(tool, f"http://{PUBLIC_NAME}:{listener.port}/redirect")
    assert TOKEN not in out
    assert listener.hits == ["/redirect"]


def test_googlesearch_extract_content_keeps_no_copy_of_public_pages(
    listener: Listener,  # noqa: F811
    extract: tuple[Any, MemoryStorage],
) -> None:
    tool, storage = extract
    out = _invoke(tool, f"http://{PUBLIC_NAME}:{listener.port}/page")
    assert TOKEN in out
    assert storage.objects == {}
