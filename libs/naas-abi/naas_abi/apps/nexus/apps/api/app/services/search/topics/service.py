"""Search topics: list a workspace's topics and run them against its graphs."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import replace
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
    TopicResultRow,
    TopicResultRowDef,
    TopicResults,
    TopicSectionItem,
    TopicSectionResult,
)

MAX_RESULTS = 100
SECTION_LIMIT = 100
PREVIEW_LIMIT = 20
# A result row lists at most this many values ("A, B, C +2").
ROW_VALUES = 3

logger = logging.getLogger(__name__)


def _value(row: ResultRow, name: str) -> str | None:
    binding = row.get(name)
    if binding is None:
        return None
    return binding.value if binding.value.strip() else None


def _tags(value: str | None) -> list[str]:
    """Split a section's newline-separated ``tags`` into distinct labels, in order."""
    if not value:
        return []
    return list(dict.fromkeys(tag.strip() for tag in value.split("\n") if tag.strip()))


def _projection(sparql: str) -> dict[str, int]:
    """Position of each variable in a query's SELECT clause: header facts keep that order."""
    match = re.search(r"\bSELECT\b(.*?)\bWHERE\b", sparql, re.IGNORECASE | re.DOTALL)
    names = re.findall(r"\?(\w+)", match.group(1)) if match else []
    return {name: i for i, name in reversed(list(enumerate(names)))}


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
        page = await self._decorate(topic, items[:limit], store)
        return TopicResults(
            topic_id=topic.id,
            query=query,
            items=page,
            has_more=len(items) > limit,
            sparql=sparql,
        )

    async def _decorate(
        self, topic: SearchTopic, items: list[TopicResultItem], store: IGraphQueryStore
    ) -> list[TopicResultItem]:
        """Give a page of results its pictures and metadata rows, one query each.

        A broken image or row query leaves its slot empty; the results still show.
        """
        if not items or (not topic.image_query.strip() and not topic.result_rows):
            return items
        uris = [item.uri for item in items]

        async def collect(template: str, role: str, slot: str) -> dict[str, list[str]]:
            try:
                rows = await asyncio.to_thread(store.select, render(template, role, {"uris": uris}))
            except Exception as exc:  # noqa: BLE001
                logger.warning("search topic %s %s query failed: %s", topic.id, role, exc)
                return {}
            values: dict[str, list[str]] = {}
            for row in rows:
                uri, value = _value(row, "uri"), _value(row, slot)
                if uri and value and value not in values.setdefault(uri, []):
                    values[uri].append(value)
            return values

        image_job = (
            collect(topic.image_query, "image", "image")
            if topic.image_query.strip()
            else asyncio.sleep(0, result={})
        )
        images, *row_values = await asyncio.gather(
            image_job, *(collect(r.query, "row", "value") for r in topic.result_rows)
        )
        decorated = []
        for item in items:
            rows = []
            for definition, values in zip(topic.result_rows, row_values, strict=True):
                found = values.get(item.uri) or []
                if not found:
                    continue
                shown = ", ".join(found[:ROW_VALUES])
                if len(found) > ROW_VALUES:
                    shown += f" +{len(found) - ROW_VALUES}"
                rows.append(TopicResultRow(id=definition.id, label=definition.label, value=shown))
            image = (images.get(item.uri) or [item.image])[0]
            decorated.append(replace(item, image=image, rows=rows))
        return decorated

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
                    tags=_tags(_value(row, "tags")),
                    group=_value(row, "group"),
                    group_item=_value(row, "group_item"),
                    group_image=_value(row, "group_image"),
                    client=_value(row, "client"),
                    client_item=_value(row, "client_item"),
                    client_image=_value(row, "client_image"),
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

        async def run_fact(definition: TopicResultRowDef) -> TopicFact | None:
            try:
                rows = await asyncio.to_thread(
                    store.select, render(definition.query, "row", {"uris": [uri]})
                )
            except Exception as exc:  # noqa: BLE001 - a broken fact leaves its slot empty
                logger.warning("search topic %s fact %s failed: %s", topic.id, definition.id, exc)
                return None
            values = list(dict.fromkeys(v for row in rows if (v := _value(row, "value"))))
            if not values:
                return None
            return TopicFact(key=definition.id, label=definition.label, value=", ".join(values))

        header_rows, extra_facts, *sections = await asyncio.gather(
            asyncio.to_thread(store.select, header_sparql),
            asyncio.gather(*(run_fact(f) for f in topic.detail_facts)),
            *(run_section(s) for s in topic.sections),
        )
        if not header_rows:
            raise SearchTopicNotFoundError(f"{topic.label} not found in the workspace graphs")
        header = header_rows[0]
        slots = ROLE_CONTRACTS["header"].required | ROLE_CONTRACTS["header"].optional
        projection = _projection(header_sparql)
        facts = sorted(
            (
                TopicFact(
                    key=name, label=_humanize(name), value=binding.value, is_uri=binding.is_uri
                )
                for name, binding in header.items()
                if name not in slots and binding.value.strip()
            ),
            key=lambda fact: projection.get(fact.key, len(projection)),
        )
        facts += [fact for fact in extra_facts if fact is not None]
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
        if "uris" in allowed:
            # Image and row queries run on a page of results: preview them on one individual.
            if not params.get("uri"):
                raise SearchTopicValidationError(["pick an individual (uri) to preview this query"])
            values["uris"] = [str(params["uri"])]
        if "uri" in allowed and not values.get("uri"):
            raise SearchTopicValidationError(["pick an individual (uri) to preview this query"])
        if "limit" in allowed:
            values["limit"] = min(int(values.get("limit") or PREVIEW_LIMIT), PREVIEW_LIMIT)
        sparql = render(template, role, values)
        rows = await asyncio.to_thread(store.select, sparql)
        return sparql, rows[:PREVIEW_LIMIT]
