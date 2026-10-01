"""Search topics: list a workspace's topics and run them against its graphs."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import (
    IGraphQueryStore,
    ResultRow,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics.builtin import BUILTIN_TOPICS
from naas_abi.apps.nexus.apps.api.app.services.search.topics.port import SearchTopicStorePort
from naas_abi.apps.nexus.apps.api.app.services.search.topics.templating import (
    render,
    validate_query,
    validate_topic,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics.topics__schema import (
    DEFAULT_DISABLED_SCOPE_IDS,
    ROLE_CONTRACTS,
    SWITCHABLE_SCOPE_IDS,
    SearchTopic,
    SearchTopicNotFoundError,
    SearchTopicValidationError,
    TopicDetail,
    TopicFact,
    TopicResultItem,
    TopicResults,
    TopicSectionItem,
    TopicSectionResult,
)

MAX_RESULTS = 100
SECTION_LIMIT = 100
PREVIEW_LIMIT = 20


def _value(row: ResultRow, name: str) -> str | None:
    binding = row.get(name)
    if binding is None:
        return None
    return binding.value if binding.value.strip() else None


def _humanize(name: str) -> str:
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " ").strip()
    return words[:1].upper() + words[1:].lower()


def _score(raw: str | None) -> float | None:
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None


class SearchTopicService:
    def __init__(self, store: SearchTopicStorePort) -> None:
        self._store = store

    # -- definitions -------------------------------------------------------

    async def list_topics(
        self, workspace_id: str, *, include_disabled: bool = True
    ) -> list[SearchTopic]:
        topics: dict[str, SearchTopic] = dict(BUILTIN_TOPICS)
        for stored in await self._store.list(workspace_id):
            topics[stored.id] = stored.with_source(
                "override" if stored.id in BUILTIN_TOPICS else "custom"
            )
        ordered = sorted(topics.values(), key=lambda t: (t.order, t.label.lower()))
        return [t for t in ordered if include_disabled or t.enabled]

    async def get_topic(self, workspace_id: str, topic_id: str) -> SearchTopic:
        for topic in await self.list_topics(workspace_id):
            if topic.id == topic_id:
                return topic
        raise SearchTopicNotFoundError(f"Unknown search topic: {topic_id}")

    async def save_topic(
        self, workspace_id: str, topic: SearchTopic, *, user_id: str | None
    ) -> SearchTopic:
        validate_topic(topic)
        source = "override" if topic.id in BUILTIN_TOPICS else "custom"
        stored = topic.with_source(source)
        await self._store.save(workspace_id, stored, user_id=user_id)
        return stored

    async def reset_topic(self, workspace_id: str, topic_id: str) -> SearchTopic | None:
        """Drop the stored definition: a built-in comes back, a custom topic is gone."""
        removed = await self._store.delete(workspace_id, topic_id)
        if topic_id in BUILTIN_TOPICS:
            return BUILTIN_TOPICS[topic_id]
        if not removed:
            raise SearchTopicNotFoundError(f"Unknown search topic: {topic_id}")
        return None

    # -- feature and web-engine scopes ---------------------------------------

    async def disabled_scopes(self, workspace_id: str) -> set[str]:
        stored = await self._store.get_disabled_scopes(workspace_id)
        if stored is None:
            return set(DEFAULT_DISABLED_SCOPE_IDS)
        return stored & SWITCHABLE_SCOPE_IDS

    async def set_scope_enabled(
        self, workspace_id: str, scope_id: str, enabled: bool, *, user_id: str | None
    ) -> set[str]:
        """Switch a feature or web engine on or off for the whole workspace."""
        if scope_id not in SWITCHABLE_SCOPE_IDS:
            raise SearchTopicNotFoundError(f"Unknown search scope: {scope_id}")
        disabled = await self.disabled_scopes(workspace_id)
        disabled = disabled - {scope_id} if enabled else disabled | {scope_id}
        await self._store.set_disabled_scopes(workspace_id, disabled, user_id=user_id)
        return disabled

    # -- execution ---------------------------------------------------------

    async def search(
        self,
        workspace_id: str,
        topic_id: str,
        query: str,
        store: IGraphQueryStore,
        *,
        limit: int = 30,
        offset: int = 0,
    ) -> TopicResults:
        topic = await self.get_topic(workspace_id, topic_id)
        limit = max(1, min(limit, MAX_RESULTS))
        sparql = render(
            topic.results_query,
            "results",
            {"q": query.strip(), "limit": limit + 1, "offset": max(0, offset)},
        )
        rows = await asyncio.to_thread(store.select, sparql)
        items: list[TopicResultItem] = []
        seen: set[str] = set()
        for row in rows:
            uri, title = _value(row, "uri"), _value(row, "title")
            if not uri or not title or uri in seen:
                continue
            seen.add(uri)
            items.append(
                TopicResultItem(
                    uri=uri,
                    title=title,
                    subtitle=_value(row, "subtitle"),
                    snippet=_value(row, "snippet"),
                    image=_value(row, "image"),
                    score=_score(_value(row, "score")),
                )
            )
        return TopicResults(
            topic_id=topic.id,
            query=query,
            items=items[:limit],
            has_more=len(items) > limit,
            sparql=sparql,
        )

    async def detail(
        self,
        workspace_id: str,
        topic_id: str,
        uri: str,
        store: IGraphQueryStore,
    ) -> TopicDetail:
        topic = await self.get_topic(workspace_id, topic_id)
        header_sparql = render(topic.header_query, "header", {"uri": uri})

        async def run_section(section: Any) -> TopicSectionResult:
            sparql = render(section.query, "section", {"uri": uri, "limit": SECTION_LIMIT})
            try:
                rows = await asyncio.to_thread(store.select, sparql)
            except Exception as exc:  # one broken section must not hide the others
                return TopicSectionResult(
                    id=section.id,
                    label=section.label,
                    empty_text=section.empty_text,
                    link_topic=section.link_topic,
                    items=[],
                    sparql=sparql,
                    error=str(exc) or type(exc).__name__,
                )
            items = [
                TopicSectionItem(
                    title=title,
                    item=_value(row, "item"),
                    subtitle=_value(row, "subtitle"),
                    snippet=_value(row, "snippet"),
                    image=_value(row, "image"),
                    start=_value(row, "start"),
                    end=_value(row, "end"),
                    url=_value(row, "url"),
                )
                for row in rows
                if (title := _value(row, "title"))
            ]
            return TopicSectionResult(
                id=section.id,
                label=section.label,
                empty_text=section.empty_text,
                link_topic=section.link_topic,
                items=items,
                sparql=sparql,
            )

        header_rows, *sections = await asyncio.gather(
            asyncio.to_thread(store.select, header_sparql),
            *(run_section(s) for s in topic.sections),
        )
        if not header_rows:
            raise SearchTopicNotFoundError(f"{topic.label} not found in the workspace graphs")
        header = header_rows[0]
        slots = ROLE_CONTRACTS["header"].required | ROLE_CONTRACTS["header"].optional
        facts = [
            TopicFact(key=name, label=_humanize(name), value=binding.value, is_uri=binding.is_uri)
            for name, binding in header.items()
            if name not in slots and binding.value.strip()
        ]
        return TopicDetail(
            topic_id=topic.id,
            uri=uri,
            title=_value(header, "title") or uri,
            subtitle=_value(header, "subtitle"),
            snippet=_value(header, "snippet"),
            image=_value(header, "image"),
            url=_value(header, "url"),
            facts=facts,
            sections=list(sections),
            header_sparql=header_sparql,
        )

    async def preview(
        self,
        template: str,
        role: str,
        params: dict[str, Any],
        store: IGraphQueryStore,
    ) -> tuple[str, list[ResultRow]]:
        """Run one template from the settings editor and return its first rows."""
        errors = validate_query(template, role)
        if errors:
            raise SearchTopicValidationError(errors)
        defaults: dict[str, Any] = {"q": "", "limit": PREVIEW_LIMIT, "offset": 0}
        allowed = ROLE_CONTRACTS[role].placeholders
        values = {k: v for k, v in {**defaults, **params}.items() if k in allowed}
        if "uri" in allowed and not values.get("uri"):
            raise SearchTopicValidationError(["pick an individual (uri) to preview this query"])
        values["limit"] = min(int(values.get("limit") or PREVIEW_LIMIT), PREVIEW_LIMIT)
        sparql = render(template, role, values)
        rows = await asyncio.to_thread(store.select, sparql)
        return sparql, rows[:PREVIEW_LIMIT]
