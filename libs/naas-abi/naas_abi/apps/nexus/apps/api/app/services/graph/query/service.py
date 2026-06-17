"""GraphQueryService — orchestrates a backend-driven Explore query (AUDIT §7b.6, §7b.9).

run_query() = validate ownership (workspace ↔ named-graph) → guard the spec → compile to one
SPARQL query → run the page + (cached) count concurrently → assemble columns/rows/page/count.
The compiler is pure; this layer owns I/O, the cursor round-trip, and the count cache.
"""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
    GraphQuerySpecError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query import guards
from naas_abi.apps.nexus.apps.api.app.services.graph.query.column_discovery import (
    discover_columns as _discover_columns,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.compiler import (
    compile_facet,
    compile_query,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.count_key import count_cache_key
from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import IGraphQueryStore
from naas_abi.apps.nexus.apps.api.app.services.graph.query.search import (
    search_entities as _search_entities,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import (
    AggregateSpec,
    CellData,
    CompileContext,
    CompiledQuery,
    CountInfoData,
    FacetBucketData,
    FacetResultData,
    ListSpec,
    Page,
    PageInfoData,
    QueryResultData,
)

# ── Count cache (injectable; FS-backed impl is wired in the adapter DI) ─────────


class CountCache:
    """Minimal interface: ``fetch`` returns a cached count dict or ``None``; ``store`` saves one."""

    def fetch(self, key: str) -> dict | None:  # pragma: no cover - interface
        raise NotImplementedError

    def store(self, key: str, value: dict) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class NoCountCache(CountCache):
    """Always recompute (v1 default). The 10-min FS cache is a follow-up optimization."""

    def fetch(self, key: str) -> dict | None:
        return None

    def store(self, key: str, value: dict) -> None:
        return None


# ── Cursor codec ────────────────────────────────────────────────────────────────


def _encode_cursor(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> dict:
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
    except Exception as exc:
        raise GraphQuerySpecError("invalid cursor") from exc


def _coerce(value: str, datatype: str) -> Any:
    if datatype == "number":
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value
    if datatype == "boolean":
        return value.strip().lower() in ("true", "1")
    return value


class GraphQueryService:
    def __init__(
        self,
        store: IGraphQueryStore,
        *,
        owned_graphs: Callable[[str], Any],  # workspace_id → set[str] (sync or awaitable)
        system_graphs: set[str],  # global read-only graphs (schema/nexus) any workspace may query
        count_cache: CountCache | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._owned_graphs = owned_graphs
        self._system = system_graphs
        self._cache = count_cache or NoCountCache()
        self._now = now or (lambda: datetime.now(UTC).isoformat())

    # ── Public ──────────────────────────────────────────────────────────────────

    async def run_query(
        self,
        *,
        spec: ListSpec | AggregateSpec,
        workspace_id: str,
        cursor: str | None = None,
        limit: int | None = None,
        force_count_refresh: bool = False,
        include_sparql: bool = True,
    ) -> QueryResultData:
        owned = self._owned_graphs(workspace_id)
        if inspect.isawaitable(owned):
            owned = await owned
        self._check_ownership(spec.graph_uris, owned)
        guards.validate_spec(spec)
        page_limit = guards.clamp_limit(limit)

        page = self._page_from_cursor(spec, cursor, page_limit)
        ctx = CompileContext(
            fts_backend="jena_text" if self._store.supports_fulltext() else "none",
            # Functional-predicate hints come from /columns later; empty is correct (just
            # less optimised: positive filters stay OPTIONAL+FILTER, sorted pages use OFFSET).
            single_valued_predicates=frozenset(),
        )
        compiled = compile_query(spec, ctx, page)
        ckey = count_cache_key(spec, workspace_id=workspace_id)

        rows, count = await asyncio.gather(
            asyncio.to_thread(self._store.select, compiled.sparql),
            self._count(ckey, compiled.count_sparql, force_count_refresh),
        )
        return self._assemble(spec, compiled, rows, count, ckey, page, page_limit, include_sparql)

    async def facets(
        self, *, spec: ListSpec, workspace_id: str, target_column_id: str, search: str = "", limit: int = 50
    ) -> FacetResultData:
        """Distinct values + counts for one column under the other columns' filters."""
        owned = self._owned_graphs(workspace_id)
        if inspect.isawaitable(owned):
            owned = await owned
        self._check_ownership(spec.graph_uris, owned)
        guards.validate_spec(spec)
        capped = max(1, min(int(limit), guards.QueryGuards.MAX_FACET_CARDINALITY))
        ctx = CompileContext(fts_backend="jena_text" if self._store.supports_fulltext() else "none")
        try:
            sparql = compile_facet(spec, ctx, target_column_id=target_column_id, search=search, limit=capped)
        except GraphQuerySpecError as exc:
            # Unfacetable (e.g. a measure) → graceful refusal, not an error.
            return FacetResultData(column_id=target_column_id, faceted=False, reason=str(exc))
        rows = await asyncio.to_thread(self._store.select, sparql)
        truncated = len(rows) > capped
        buckets = tuple(
            FacetBucketData(value=r["v"].value, count=int(r["cnt"].value))
            for r in rows[:capped]
            if "v" in r
        )
        return FacetResultData(
            column_id=target_column_id, faceted=True, buckets=buckets,
            distinct_count=len(buckets), truncated=truncated,
        )

    async def discover_columns(
        self, *, workspace_id: str, graph_uris: list[str], class_uris: list[str]
    ) -> tuple:
        """Ontology ∪ data column discovery for an anchored class (ownership-guarded)."""
        owned = self._owned_graphs(workspace_id)
        if inspect.isawaitable(owned):
            owned = await owned
        self._check_ownership(tuple(graph_uris), owned)
        if not class_uris:
            raise GraphQuerySpecError("at least one class_uri is required")
        return await asyncio.to_thread(
            _discover_columns, self._store, graph_uris=graph_uris, class_uris=class_uris
        )

    async def search_entities(
        self, *, workspace_id: str, graph_uris: list[str], query: str, limit: int = 20
    ) -> tuple:
        """Free-text search for classes ∪ individuals across the given (or all owned) graphs."""
        owned = self._owned_graphs(workspace_id)
        if inspect.isawaitable(owned):
            owned = await owned
        # default: all owned graphs (system graphs are not data graphs, so excluded).
        targets = list(graph_uris) if graph_uris else sorted(owned)
        if not targets:  # a workspace with no graphs → empty result, not an error.
            return ()
        self._check_ownership(tuple(targets), owned)
        q = (query or "").strip()
        if not q:
            raise GraphQuerySpecError("query must be non-empty")
        return await asyncio.to_thread(
            _search_entities, self._store, graph_uris=targets, query=q, limit=limit
        )

    # ── Internals ─────────────────────────────────────────────────────────────────

    def _check_ownership(self, requested: tuple[str, ...], owned: set[str]) -> None:
        if not requested:
            raise GraphQuerySpecError("spec.graph_uris must be non-empty")
        # A graph is queryable if the workspace owns it OR it's a global system graph
        # (schema/nexus) that every workspace may read.
        requested_set = set(requested)
        illegal = requested_set - (owned | self._system)
        if illegal:
            raise GraphAccessError(f"workspace does not own graph(s): {sorted(illegal)}")

    def _page_from_cursor(self, spec: ListSpec | AggregateSpec, cursor: str | None, limit: int) -> Page:
        # Fetch one extra row to detect "has_more" without a second request.
        probe = limit + 1
        if cursor is None:
            return Page(limit=probe)
        payload = _decode_cursor(cursor)
        if payload.get("k") == "keyset":
            after = (*payload.get("v", []), payload.get("r"))
            return Page(limit=probe, after=after)
        if payload.get("k") == "offset":
            return Page(limit=probe, offset=int(payload.get("o", 0)))
        raise GraphQuerySpecError("invalid cursor kind")

    async def _count(self, key: str, count_sparql: str, force_refresh: bool) -> dict:
        if not force_refresh:
            cached = self._cache.fetch(key)
            if cached is not None:
                return {**cached, "status": "cached"}
        total = await asyncio.to_thread(self._store.count, count_sparql)
        value = {"total": total, "computed_at": self._now()}
        self._cache.store(key, value)
        return {**value, "status": "exact"}

    def _assemble(
        self,
        spec: ListSpec | AggregateSpec,
        compiled: CompiledQuery,
        raw_rows: list[dict],
        count: dict,
        ckey: str,
        page: Page,
        limit: int,
        include_sparql: bool,
    ) -> QueryResultData:
        has_more = len(raw_rows) > limit
        kept = raw_rows[:limit]

        cell_rows: list[dict[str, CellData]] = []
        for raw in kept:
            cells: dict[str, CellData] = {}
            for col in compiled.columns:
                var = compiled.var_for_column[col.id].lstrip("?")  # "col_<id>" / "dim_<id>" / "m_<id>"
                binding = raw.get(var)
                if binding is None:  # OPTIONAL miss → cell absent (sparse row)
                    continue
                cells[col.id] = CellData(
                    value=_coerce(binding.value, col.datatype),
                    uri=binding.value if binding.is_uri else None,
                )
            cell_rows.append(cells)

        next_cursor = self._next_cursor(compiled, kept, page, limit) if has_more else None
        page_info = PageInfoData(
            limit=limit,
            has_more=has_more,
            next_cursor=next_cursor,
            offset_fallback=compiled.uses_offset_fallback,
        )
        count_info = CountInfoData(
            total=int(count["total"]),
            computed_at=str(count["computed_at"]),
            status=str(count["status"]),
            cache_key=ckey,
        )
        return QueryResultData(
            mode="list" if isinstance(spec, ListSpec) else "aggregate",
            columns=compiled.columns,
            rows=tuple(cell_rows),
            page=page_info,
            count=count_info,
            resolved_sparql=compiled.sparql if include_sparql else None,
        )

    def _next_cursor(self, compiled: CompiledQuery, kept: list[dict], page: Page, limit: int) -> str | None:
        if not kept:
            return None
        if compiled.uses_offset_fallback:
            return _encode_cursor({"k": "offset", "o": (page.offset or 0) + limit})
        last = kept[-1]
        vals = []
        for col_id in compiled.order_columns:
            var = compiled.var_for_column[col_id].lstrip("?")
            binding = last.get(var)
            vals.append(binding.value if binding is not None else None)
        root = last.get("root")
        if root is None:  # aggregate mode has no ?root; should not reach here (offset fallback)
            return None
        return _encode_cursor({"k": "keyset", "v": vals, "r": root.value})
