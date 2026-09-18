"""SearchAgent tools for Nexus Search.

The Search page (``stores/search.ts``) fans a query out to
``POST /api/search/web`` (Wikipedia or DuckDuckGo), ``POST /api/search/private``
(source ``ontology``: classes and properties from the loaded ontologies), and
any custom sources the tenant configures in the browser. These tools run the
same two server-side searches. ``POST /api/search/`` (workspace search) is a
stub that returns no results today, so there is no tool for it: the agent
explains that from the code instead of returning an empty list as if it
were an answer.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.runtime import clip, guarded, jsonable, run, tool_context

_FEATURE = "Search"
_ENGINES = ("wikipedia", "duckduckgo")


def _service() -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry
    from naas_abi.apps.nexus.apps.api.app.services.search.service import SearchService

    try:
        return ServiceRegistry.instance().search
    except RuntimeError:
        return SearchService()


def _result(result: Any) -> dict[str, Any]:
    out = jsonable(result)
    if isinstance(out, dict) and "snippet" in out:
        out["snippet"] = clip(out["snippet"], 300)
    return out


def search_tools() -> list[BaseTool]:
    @tool
    def search_public_web(query: str, engine: str = "wikipedia", limit: int = 8) -> Any:
        """Search the public web the way the Search page does.

        engine is wikipedia or duckduckgo. Returns title, snippet, url,
        relevance.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        if engine not in _ENGINES:
            return {"error": f"engine must be one of {', '.join(_ENGINES)}."}
        if not (query or "").strip():
            return {"error": "query is required."}

        def _run() -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.search.search__schema import (
                WebSearchRequestData,
            )

            response = run(
                _service().web_search(
                    WebSearchRequestData(
                        query=query.strip(), engine=engine, limit=max(1, min(limit, 20))
                    )
                )
            )
            return {
                "engine": response.engine,
                "results": [_result(r) for r in response.results],
            }

        return guarded(_FEATURE, _run)

    @tool
    def search_ontology_terms(query: str) -> Any:
        """Private search over the loaded ontologies (classes and properties by
        label), the page's "Private" source."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        if not (query or "").strip():
            return {"error": "query is required."}

        def _run() -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.search.search__schema import (
                PrivateSearchRequestData,
            )

            response = run(
                _service().private_search(
                    PrivateSearchRequestData(query=query.strip(), source="ontology")
                )
            )
            return {"results": [_result(r) for r in response.results[:25]]}

        return guarded(_FEATURE, _run)

    return [search_public_web, search_ontology_terms]
