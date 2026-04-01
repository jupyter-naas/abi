from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from typing import Any

import httpx
from naas_abi.apps.nexus.apps.api.app.services.search.search__schema import (
    PrivateSearchRequestData,
    PrivateSearchResponseData,
    SearchRequestData,
    SearchResponseData,
    WebSearchRequestData,
    WebSearchResponseData,
    WebSearchResultData,
)

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": "NEXUS/1.0 (https://github.com/jravenel/nexus; search service)",
}


class SearchService:
    def __init__(
        self,
        triple_store_getter: Callable[[], Any] | None = None,
    ) -> None:
        self._triple_store_getter = triple_store_getter

    async def search(self, request: SearchRequestData) -> SearchResponseData:
        return SearchResponseData(
            query=request.query,
            total=0,
            results=[],
            facets={},
        )

    async def web_search(self, request: WebSearchRequestData) -> WebSearchResponseData:
        if request.engine == "wikipedia":
            results = await self._search_wikipedia(query=request.query, limit=request.limit)
        elif request.engine == "duckduckgo":
            results = await self._search_duckduckgo(query=request.query, limit=request.limit)
        else:
            raise ValueError(f"Unknown engine: {request.engine}")

        return WebSearchResponseData(
            query=request.query,
            engine=request.engine,
            results=results,
        )

    async def private_search(self, request: PrivateSearchRequestData) -> PrivateSearchResponseData:
        if request.source != "ontology":
            return PrivateSearchResponseData(query=request.query, source=request.source, results=[])

        results = self._search_ontology(query=request.query)
        return PrivateSearchResponseData(
            query=request.query,
            source=request.source,
            results=results,
        )

    async def get_suggestions(self, query: str, limit: int) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "opensearch",
                        "search": query,
                        "limit": limit,
                        "namespace": "0",
                        "format": "json",
                    },
                    headers=_DEFAULT_HEADERS,
                )
                response.raise_for_status()
                data = response.json()
                if len(data) >= 2 and isinstance(data[1], list):
                    return [str(item) for item in data[1][:limit]]
        except Exception:
            logger.warning("Wikipedia suggestions failed", exc_info=True)
        return []

    async def _search_wikipedia(self, query: str, limit: int) -> list[WebSearchResultData]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "generator": "search",
                        "gsrsearch": query,
                        "gsrlimit": limit,
                        "prop": "extracts|pageimages|info",
                        "exintro": "1",
                        "explaintext": "1",
                        "exsentences": "3",
                        "piprop": "thumbnail",
                        "pithumbsize": "200",
                        "inprop": "url",
                        "format": "json",
                    },
                    headers=_DEFAULT_HEADERS,
                )
                response.raise_for_status()
                data = response.json()
                pages = data.get("query", {}).get("pages", {})
                return self._build_wikipedia_results(pages=pages)
        except Exception:
            logger.warning("Wikipedia search failed", exc_info=True)
            return []

    async def _search_duckduckgo(self, query: str, limit: int) -> list[WebSearchResultData]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": "1",
                        "skip_disambig": "1",
                    },
                    headers=_DEFAULT_HEADERS,
                )
                response.raise_for_status()
                data = response.json()
                return self._build_duckduckgo_results(data=data, query=query, limit=limit)
        except Exception:
            logger.warning("DuckDuckGo search failed", exc_info=True)
            return []

    @staticmethod
    def _build_wikipedia_results(pages: dict[str, Any]) -> list[WebSearchResultData]:
        results: list[WebSearchResultData] = []
        sorted_pages = sorted(pages.values(), key=lambda page: page.get("index", 999))

        for index, page in enumerate(sorted_pages):
            page_id = str(page.get("pageid", index))
            result_id = hashlib.md5(f"wikipedia:{page_id}".encode()).hexdigest()[:12]
            title = str(page.get("title", ""))

            results.append(
                WebSearchResultData(
                    id=result_id,
                    title=title,
                    snippet=str(page.get("extract", ""))[:500],
                    url=page.get("fullurl")
                    or f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    relevance=1.0 - (index * 0.05),
                    metadata={
                        "source": "wikipedia",
                        "language": "en",
                        "image": page.get("thumbnail", {}).get("source"),
                        "pageid": page.get("pageid"),
                    },
                )
            )

        return results

    @staticmethod
    def _build_duckduckgo_results(
        data: dict[str, Any],
        query: str,
        limit: int,
    ) -> list[WebSearchResultData]:
        results: list[WebSearchResultData] = []

        main_image = data.get("Image")
        if isinstance(main_image, str) and main_image and not main_image.startswith("http"):
            main_image = f"https://duckduckgo.com{main_image}"

        abstract = data.get("Abstract")
        if isinstance(abstract, str) and abstract:
            result_id = hashlib.md5(f"ddg:abstract:{query}".encode()).hexdigest()[:12]
            results.append(
                WebSearchResultData(
                    id=result_id,
                    title=str(data.get("Heading") or query),
                    snippet=abstract,
                    url=data.get("AbstractURL"),
                    relevance=1.0,
                    metadata={
                        "source": "duckduckgo",
                        "type": "abstract",
                        "source_name": data.get("AbstractSource", ""),
                        "image": main_image,
                    },
                )
            )

        for index, topic in enumerate(data.get("RelatedTopics", [])[: max(limit - 1, 0)]):
            if not isinstance(topic, dict) or not topic.get("Text"):
                continue

            topic_icon = topic.get("Icon", {}).get("URL")
            if isinstance(topic_icon, str) and topic_icon and not topic_icon.startswith("http"):
                topic_icon = f"https://duckduckgo.com{topic_icon}"

            topic_text = str(topic.get("Text", ""))
            result_id = hashlib.md5(
                f"ddg:topic:{topic.get('FirstURL', str(index))}".encode()
            ).hexdigest()[:12]
            results.append(
                WebSearchResultData(
                    id=result_id,
                    title=topic_text[:100] + ("..." if len(topic_text) > 100 else ""),
                    snippet=topic_text,
                    url=topic.get("FirstURL"),
                    relevance=0.9 - (index * 0.05),
                    metadata={
                        "source": "duckduckgo",
                        "type": "related",
                        "image": topic_icon,
                    },
                )
            )

        for topic in data.get("RelatedTopics", []):
            if len(results) >= limit:
                break
            if not isinstance(topic, dict) or "Topics" not in topic:
                continue

            for subtopic in topic.get("Topics", [])[:3]:
                if len(results) >= limit:
                    break
                if not isinstance(subtopic, dict):
                    continue

                result_id = hashlib.md5(
                    f"ddg:subtopic:{subtopic.get('FirstURL', '')}".encode()
                ).hexdigest()[:12]
                results.append(
                    WebSearchResultData(
                        id=result_id,
                        title=str(subtopic.get("Text", ""))[:100],
                        snippet=str(subtopic.get("Text", "")),
                        url=subtopic.get("FirstURL"),
                        relevance=0.7,
                        metadata={
                            "source": "duckduckgo",
                            "type": "category",
                            "category": topic.get("Name", ""),
                        },
                    )
                )

        return results[:limit]

    def _search_ontology(self, query: str) -> list[WebSearchResultData]:
        triple_store_service = self._get_triple_store_service()
        if triple_store_service is None:
            return []

        escaped_query = self._escape_sparql_literal(query)
        sparql_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?uri ?label ?definition WHERE {{
            ?uri a ?type .
            OPTIONAL {{ ?uri rdfs:label ?label . }}
            OPTIONAL {{ ?uri skos:definition ?definition . }}
            FILTER (
                (BOUND(?label) && CONTAINS(LCASE(STR(?label)), LCASE("{escaped_query}")))
             || (BOUND(?definition) && CONTAINS(LCASE(STR(?definition)), LCASE("{escaped_query}")))
            )
        }}
        LIMIT 100
        """

        try:
            sparql_results = triple_store_service.query(sparql_query)
        except Exception:
            logger.warning("Ontology search failed", exc_info=True)
            return []

        results: list[WebSearchResultData] = []
        normalized_query = (query or "").strip().lower()

        for row in sparql_results:
            uri = str(row.get("uri")) if hasattr(row, "get") else ""
            if not uri:
                continue

            label = str(row.get("label") or uri.split("/")[-1])
            definition = str(row.get("definition") or "")

            normalized_label = label.strip().lower()
            normalized_definition = definition.strip().lower()

            if normalized_query == normalized_label:
                score = 1.0
            elif normalized_query in normalized_label:
                score = 0.8
            elif normalized_query in normalized_definition:
                score = 0.6
            else:
                score = 0.0

            results.append(
                WebSearchResultData(
                    id=uri,
                    title=label,
                    snippet=definition,
                    url=None,
                    relevance=score,
                    metadata={},
                )
            )

        return results

    def _get_triple_store_service(self) -> Any | None:
        if self._triple_store_getter is not None:
            return self._triple_store_getter()
        try:
            from naas_abi import ABIModule

            return ABIModule.get_instance().engine.services.triple_store
        except Exception:
            logger.warning("Unable to resolve triple store service", exc_info=True)
            return None

    @staticmethod
    def _escape_sparql_literal(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
