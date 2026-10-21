"""In-memory tool registry with lazy semantic indexing.

Publication is cheap and synchronous: modules replace their tool set at boot.
Semantic indexing is deferred to the first search (or an explicit
``sync_index``) so booting never depends on an embedding provider.

Index invalidation is fingerprint based. A definition's fingerprint hashes its
``embedding_text()`` together with the embedder's ``model_key``, so:

* a new or changed definition gets (re-)embedded,
* an unchanged one is skipped, even across restarts with a persistent index,
* a removed one is deleted from the index,
* an embedding model change re-embeds everything (the index switches to the
  new model's entries in ``prepare``).

Several processes may share one persistent index (an engine without NATS, next
to a CLI process with a narrower module set). Nothing here deletes what another
process may have written: a search skips a hit this registry does not know, and
a sync removes only what this registry indexed itself. Cleaning leftovers out
(``collect_garbage``) is opt-in, for a registry that is the index's only
writer: the serving engine, or any registry whose index is private.

**Catalog.** A process that does not serve the shared catalog (a client engine,
a standby one) may read it through an ``IToolCatalogPort``
(``configure_catalog``). Reads (``get_definition``, ``list_definitions``,
``availability``, ``check_access``, ``search_tools``) then cover the tools this
process holds and the ones the catalog shows; ``publish``, ``unpublish`` and
``resolve`` never leave the process, because bindings are live objects. A tool
this process holds always shadows the catalog's of the same id, and a reference
resolves here first: what ``resolve`` can build is what a read reports. A tool
only the catalog shows cannot be built here (``resolve`` says so). The serving
side answers from ``get_local``, ``list_local`` and ``search_local``, which
never read a catalog, so two registries cannot answer each other's calls.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from naas_abi_core.services.tool_registry.ToolAccessPolicy import (
    ScopeToolAccessPolicy,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    MAX_CATALOG_SEARCH_LIMIT,
    IToolAccessPolicy,
    IToolCatalogPort,
    IToolEmbedderPort,
    IToolIndexPort,
    IToolRegistry,
    PublishedTool,
    ResolvedEmbedder,
    ToolAccessDeniedError,
    ToolAction,
    ToolAlreadyPublishedError,
    ToolAvailability,
    ToolCatalogError,
    ToolConfigurationError,
    ToolContext,
    ToolDefinition,
    ToolFilter,
    ToolId,
    ToolIndexEntry,
    ToolListing,
    ToolNotFoundError,
    ToolRef,
    ToolRegistryError,
    ToolResolutionError,
    ToolSearchResult,
    ToolSearchUnavailableError,
)
from naas_abi_core.utils.Logger import logger


class ToolRegistryService(IToolRegistry):
    def __init__(
        self,
        embedder: IToolEmbedderPort | None = None,
        index: IToolIndexPort | None = None,
        access_policy: IToolAccessPolicy | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._tools: dict[str, PublishedTool] = {}
        self._modules: dict[str, set[str]] = {}
        self._embedder = embedder
        self._index = index
        self._catalog: IToolCatalogPort | None = None
        self._collect_leftovers = False
        self._access_policy = access_policy or ScopeToolAccessPolicy()
        # Ids the index holds for this registry, and the model they were
        # embedded with. ``None`` means "never synced in this process".
        self._indexed: dict[str, str] | None = None
        self._indexed_model_key: str | None = None
        # Whether leftovers were collected for the current search backend.
        self._collected = False
        # Set by every publication change; lets searches skip fingerprinting
        # the whole catalog when nothing changed.
        self._dirty = True

    # ----------------------------------------------------------------- wiring
    def configure_search(
        self,
        embedder: IToolEmbedderPort | None,
        index: IToolIndexPort | None,
        collect_leftovers: bool = False,
    ) -> None:
        """Install (or replace) the search backend. Forces a full re-sync.

        ``collect_leftovers`` lets the first sync delete what the index holds
        for tools this registry does not publish, and for other embedding
        models. Set it only when this registry is the only writer of the
        index's storage; the default leaves foreign entries alone.
        """
        with self._lock:
            self._embedder = embedder
            self._index = index
            self._collect_leftovers = collect_leftovers
            self._indexed = None
            self._indexed_model_key = None
            self._collected = False
            self._dirty = True

    @property
    def search_available(self) -> bool:
        return self._embedder is not None and self._index is not None

    def configure_catalog(self, catalog: IToolCatalogPort | None) -> None:
        """Read the tools another process serves too (``None``: this process only)."""
        with self._lock:
            self._catalog = catalog

    @property
    def catalog_available(self) -> bool:
        return self._catalog is not None

    # ------------------------------------------------------------ publication
    def publish(self, module: str, tools: Sequence[PublishedTool]) -> None:
        incoming: dict[str, PublishedTool] = {}
        for tool in tools:
            definition = tool.definition
            tool_id = str(definition.id)
            if definition.module != module:
                raise ToolRegistryError(
                    f"Tool '{tool_id}' belongs to module '{definition.module}', "
                    f"it cannot be published by module '{module}'."
                )
            if tool_id in incoming:
                raise ToolRegistryError(
                    f"Module '{module}' publishes tool '{tool_id}' more than once."
                )
            incoming[tool_id] = tool

        with self._lock:
            for tool_id in incoming:
                owner = self._tools.get(tool_id)
                if owner is not None and owner.definition.module != module:
                    raise ToolAlreadyPublishedError(
                        f"Tool '{tool_id}' is already published by module "
                        f"'{owner.definition.module}'."
                    )
            for tool_id in self._modules.get(module, set()):
                self._tools.pop(tool_id, None)
            self._tools.update(incoming)
            self._modules[module] = set(incoming)
            self._dirty = True
        logger.debug(
            f"Tool registry: module '{module}' published {len(incoming)} tool(s)"
        )

    def unpublish(self, module: str) -> None:
        with self._lock:
            for tool_id in self._modules.pop(module, set()):
                self._tools.pop(tool_id, None)
            self._dirty = True

    # ---------------------------------------------------------------- lookup
    def _lookup(
        self,
        ref: str | ToolRef | ToolId,
        visible: Callable[[ToolDefinition], bool] | None = None,
    ) -> PublishedTool:
        if isinstance(ref, ToolId):
            ref = ToolRef(namespace=ref.namespace, name=ref.name, version=ref.version)
        elif isinstance(ref, str):
            ref = ToolRef.parse(ref)
        with self._lock:
            if ref.version is not None:
                tool = self._tools.get(f"{ref.namespace}/{ref.name}@{ref.version}")
                candidates = [tool] if tool is not None else []
            else:
                candidates = [
                    t for t in self._tools.values() if ref.matches(t.definition.id)
                ]
        if visible is not None:
            candidates = [t for t in candidates if visible(t.definition)]
        if not candidates:
            raise ToolNotFoundError(
                f"No published tool matches '{ref}'. Check the module publishing "
                "it is enabled, and the reference's namespace, name and version."
            )
        return max(candidates, key=lambda t: t.definition.id.version_key)

    def _remote(self, ref: str | ToolRef | ToolId) -> ToolListing:
        """The catalog's tool for ``ref`` (the caller found no local one)."""
        assert self._catalog is not None
        return self._catalog.get_tool(str(ref))

    def get_definition(self, ref: str | ToolRef | ToolId) -> ToolDefinition:
        try:
            return self._lookup(ref).definition
        except ToolNotFoundError:
            if self._catalog is None:
                raise
            return self._remote(ref).definition

    def _can(
        self, definition: ToolDefinition, context: ToolContext, action: ToolAction
    ) -> bool:
        try:
            self._access_policy.check(definition, context, action)
        except ToolAccessDeniedError:
            return False
        return True

    def list_definitions(
        self, context: ToolContext | None = None
    ) -> list[ToolDefinition]:
        definitions = {
            str(listing.definition.id): listing.definition
            for listing in self.list_local(context)
        }
        for listing in self._catalog_listings(self._holds_tools()):
            definition = listing.definition
            if str(definition.id) in definitions:
                continue
            if context is None or self._can(definition, context, ToolAction.DISCOVER):
                definitions[str(definition.id)] = definition
        return [definitions[tool_id] for tool_id in sorted(definitions)]

    def _holds_tools(self) -> bool:
        with self._lock:
            return bool(self._tools)

    def _catalog_listings(self, have_local: bool) -> list[ToolListing]:
        """The catalog's tools. When it cannot answer, a process that holds tools
        of its own goes on with them (a warning says so); one that holds none has
        nothing to go on with, and raises."""
        catalog = self._catalog
        if catalog is None:
            return []
        try:
            return catalog.list_tools()
        except ToolCatalogError as exc:
            if not have_local:
                raise
            logger.warning(f"Tool registry: listing this process's tools only: {exc}")
            return []

    @staticmethod
    def _missing_config(
        tool: PublishedTool, config: Mapping[str, Any] | None
    ) -> tuple[str, ...]:
        provided = {**tool.binding.default_config, **(config or {})}
        return tuple(
            key
            for key in tool.definition.required_config_keys()
            if provided.get(key) in (None, "")
        )

    def availability(
        self, ref: str | ToolRef | ToolId, config: Mapping[str, Any] | None = None
    ) -> ToolAvailability:
        try:
            tool = self._lookup(ref)
        except ToolNotFoundError:
            if self._catalog is None:
                raise
            # The owner's own values are never sent: keys it lacks, less the ones
            # this caller provides.
            missing = tuple(
                key
                for key in self._remote(ref).availability.missing_config
                if (config or {}).get(key) in (None, "")
            )
            return ToolAvailability(available=not missing, missing_config=missing)
        missing = self._missing_config(tool, config)
        return ToolAvailability(available=not missing, missing_config=missing)

    # --------------------------------------------------- what this process holds
    def get_local(
        self, ref: str | ToolRef | ToolId, context: ToolContext | None = None
    ) -> ToolListing:
        """A tool this process holds, with its availability. Never reads the catalog.

        With a ``context``, only a tool it may discover counts (the highest
        version of those, for a reference without one); one it may not is
        reported as not found, so a caller cannot tell it exists.
        """
        tool = self._lookup(
            ref,
            None
            if context is None
            else lambda definition: self._can(definition, context, ToolAction.DISCOVER),
        )
        missing = self._missing_config(tool, None)
        return ToolListing(
            definition=tool.definition,
            availability=ToolAvailability(
                available=not missing, missing_config=missing
            ),
        )

    def known_scopes(self) -> set[str]:
        """Every scope the tools this process holds require."""
        with self._lock:
            return {
                scope
                for tool in self._tools.values()
                for scope in tool.definition.required_scopes
            }

    def list_local(
        self,
        context: ToolContext | None = None,
        filter: ToolFilter | None = None,
    ) -> list[ToolListing]:
        """The tools this process holds that ``context`` may discover (``None``:
        all), sorted by id. Never reads the catalog."""
        with self._lock:
            tools = list(self._tools.values())
        listings = []
        for tool in tools:
            if context is not None and not self._can(
                tool.definition, context, ToolAction.DISCOVER
            ):
                continue
            if filter is not None and not filter.matches(tool.definition):
                continue
            missing = self._missing_config(tool, None)
            if filter is not None and filter.available_only and missing:
                continue
            listings.append(
                ToolListing(
                    definition=tool.definition,
                    availability=ToolAvailability(
                        available=not missing, missing_config=missing
                    ),
                )
            )
        return sorted(listings, key=lambda listing: str(listing.definition.id))

    # ------------------------------------------------------------ resolution
    def check_access(
        self,
        ref: str | ToolRef | ToolId,
        context: ToolContext,
        action: ToolAction,
    ) -> ToolDefinition:
        try:
            definition = self._lookup(ref).definition
        except ToolNotFoundError:
            if self._catalog is None:
                raise
            definition = self._remote(ref).definition
        self._access_policy.check(definition, context, action)
        return definition

    def resolve(
        self,
        ref: str | ToolRef | ToolId,
        context: ToolContext,
        config: Mapping[str, Any] | None = None,
        action: ToolAction = ToolAction.EXECUTE,
    ) -> object:
        try:
            tool = self._lookup(ref)
        except ToolNotFoundError:
            if self._catalog is None:
                raise
            listing = self._remote(ref)
            raise ToolResolutionError(
                f"Tool '{listing.definition.id}' is published by another engine "
                "process: this one can find it but cannot build or run it."
            ) from None
        definition = tool.definition
        self._access_policy.check(definition, context, action)
        missing = self._missing_config(tool, config)
        if missing:
            raise ToolConfigurationError(str(definition.id), missing)
        merged = {**tool.binding.default_config, **(config or {})}
        try:
            return tool.binding.create(context, merged)
        except ToolRegistryError:
            raise
        except Exception as exc:
            raise ToolResolutionError(
                f"Tool '{definition.id}' could not be built: {exc}"
            ) from exc

    # ---------------------------------------------------------------- search
    def _require_search(self) -> tuple[IToolEmbedderPort, IToolIndexPort]:
        if self._embedder is None or self._index is None:
            raise ToolSearchUnavailableError(
                "Tool search needs an embedding model and an index. Configure a "
                "default embedding model in the model registry "
                "(services.model_registry.default_embedding_model) or pass an "
                "embedder and an index to ToolRegistryService."
            )
        return self._embedder, self._index

    @staticmethod
    def _fingerprint(definition: ToolDefinition, model_key: str) -> str:
        payload = f"{model_key}\n{definition.embedding_text()}".encode()
        return hashlib.sha256(payload).hexdigest()

    def sync_index(self) -> int:
        embedder, index = self._require_search()
        return self._sync(embedder.resolve(), index)

    def _sync(self, embedder: ResolvedEmbedder, index: IToolIndexPort) -> int:
        with self._lock:
            model_key = embedder.model_key
            if not self._dirty and self._indexed_model_key == model_key:
                return 0
            definitions = {tool_id: t.definition for tool_id, t in self._tools.items()}
            desired = {
                tool_id: self._fingerprint(d, model_key)
                for tool_id, d in definitions.items()
            }
            if self._indexed_model_key == model_key and self._indexed == desired:
                self._dirty = False
                return 0

            index.prepare(model_key)
            stored = index.fingerprints(list(desired))
            stale = [
                tool_id for tool_id, fp in desired.items() if stored.get(tool_id) != fp
            ]
            if stale:
                vectors = embedder.embed_documents(
                    [definitions[tool_id].embedding_text() for tool_id in stale]
                )
                if len(vectors) != len(stale):
                    raise ToolRegistryError(
                        f"Embedder returned {len(vectors)} vectors for "
                        f"{len(stale)} tool definitions."
                    )
                index.upsert(
                    [
                        ToolIndexEntry(
                            id=tool_id,
                            fingerprint=desired[tool_id],
                            vector=tuple(float(v) for v in vector),
                            metadata={"module": definitions[tool_id].module},
                        )
                        for tool_id, vector in zip(stale, vectors)
                    ]
                )
            if self._indexed is not None and self._indexed_model_key == model_key:
                removed = [
                    tool_id for tool_id in self._indexed if tool_id not in desired
                ]
                if removed:
                    index.delete(removed)
            if self._collect_leftovers and not self._collected:
                # The previous run's leftovers: tools no longer published, other
                # embedding models. Once per backend.
                index.collect_garbage(list(desired))
                self._collected = True
            self._indexed = desired
            self._indexed_model_key = model_key
            self._dirty = False
            logger.debug(
                f"Tool registry index synced: {len(stale)} embedded, "
                f"{len(desired)} indexed (model {model_key})"
            )
            return len(stale)

    def search_tools(
        self,
        query: str,
        context: ToolContext | None = None,
        limit: int = 5,
        min_score: float | None = None,
        where: Callable[[ToolDefinition], bool] | None = None,
    ) -> list[ToolSearchResult]:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        if self._catalog is None:
            return self.search_local(
                query, context, limit=limit, min_score=min_score, where=where
            )
        context = context or ToolContext()
        local: list[ToolSearchResult] = []
        local_ranked = False
        if self._holds_tools():
            try:
                local = self.search_local(
                    query, context, limit=limit, min_score=min_score, where=where
                )
                local_ranked = True
            except ToolSearchUnavailableError:
                # This process cannot rank its own tools; the catalog's search
                # decides, and raises the same error when it cannot either.
                logger.debug("Tool registry: no local search backend; catalog only")
        try:
            remote = self._search_catalog(query, context, limit, min_score, where)
        except ToolCatalogError as exc:
            # This process ranked its own tools: they stay searchable while the
            # serving engine is away. With nothing ranked, there is no answer.
            if not local_ranked:
                raise
            logger.warning(f"Tool registry: searching this process's tools only: {exc}")
            remote = []
        merged = {result.tool_id: result for result in remote}
        merged.update({result.tool_id: result for result in local})
        ranked = sorted(merged.values(), key=lambda result: -result.score)
        return ranked[:limit]

    def _search_catalog(
        self,
        query: str,
        context: ToolContext,
        limit: int,
        min_score: float | None,
        where: Callable[[ToolDefinition], bool] | None,
    ) -> list[ToolSearchResult]:
        """The catalog's best matches this caller may see, less what this process
        holds (it ranks those itself). The catalog applied its own access rules to
        this process; the caller's are applied here, so ask for more until the
        limit is met or the catalog has no more."""
        assert self._catalog is not None
        fetch = min(max(limit * 2, limit + 5), MAX_CATALOG_SEARCH_LIMIT)
        previous = -1
        while True:
            answer = self._catalog.search_tools(query, fetch, min_score)
            hits = answer.results
            kept: list[ToolSearchResult] = []
            for hit in hits:
                definition = hit.definition
                with self._lock:
                    held = hit.tool_id in self._tools
                if held or not self._can(definition, context, ToolAction.DISCOVER):
                    continue
                if where is not None and not where(definition):
                    continue
                kept.append(hit)
            # A short answer means the catalog has no more, unless it says it left
            # some out; and asking for more is pointless when that returned no more
            # than the last time (the catalog's reply size budget, not the limit,
            # is what cut it).
            exhausted = len(hits) < fetch and not answer.truncated
            if (
                len(kept) >= limit
                or exhausted
                or fetch >= MAX_CATALOG_SEARCH_LIMIT
                or len(hits) <= previous
            ):
                return kept[:limit]
            previous = len(hits)
            fetch = min(fetch * 2, MAX_CATALOG_SEARCH_LIMIT)

    def search_local(
        self,
        query: str,
        context: ToolContext | None = None,
        limit: int = 5,
        min_score: float | None = None,
        where: Callable[[ToolDefinition], bool] | None = None,
        filter: ToolFilter | None = None,
    ) -> list[ToolSearchResult]:
        """Search the tools this process holds. Never reads the catalog."""
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        embedder, index = self._require_search()
        context = context or ToolContext()
        resolved = embedder.resolve()
        self._sync(resolved, index)
        vector = resolved.embed_query(query)

        results: list[ToolSearchResult] = []
        seen: set[str] = set()
        # Over-fetch so hits the caller may not see don't starve the limit;
        # widen until the limit is filled or a short page shows the index is
        # exhausted. ``index.size()`` is not trusted here: some backends
        # under-report it.
        fetch = max(limit * 4, limit + 10)
        while True:
            hits = index.search(vector, limit=fetch)
            for hit in hits:
                if hit.id in seen:
                    continue
                seen.add(hit.id)
                if min_score is not None and hit.score < min_score:
                    continue
                with self._lock:
                    tool = self._tools.get(hit.id)
                if tool is None:
                    # Another process's tool, or a previous run's: not ours to
                    # delete from a store others share.
                    continue
                if not self._can(tool.definition, context, ToolAction.DISCOVER):
                    continue
                if where is not None and not where(tool.definition):
                    continue
                if filter is not None and not filter.matches(tool.definition):
                    continue
                missing = self._missing_config(tool, None)
                if filter is not None and filter.available_only and missing:
                    continue
                results.append(
                    ToolSearchResult(
                        tool_id=hit.id,
                        name=tool.definition.name,
                        description=tool.definition.description,
                        module=tool.definition.module,
                        score=hit.score,
                        availability=ToolAvailability(
                            available=not missing, missing_config=missing
                        ),
                        definition=tool.definition,
                    )
                )
            if len(results) >= limit or len(hits) < fetch:
                break
            fetch *= 2

        return results[:limit]
