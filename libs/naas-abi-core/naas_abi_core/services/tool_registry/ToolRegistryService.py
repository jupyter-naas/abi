"""In-memory tool registry with lazy semantic indexing.

Publication is cheap and synchronous: modules replace their tool set at boot.
Semantic indexing is deferred to the first search (or an explicit
``sync_index``) so booting never depends on an embedding provider.

Index invalidation is fingerprint based. A definition's fingerprint hashes its
``embedding_text()`` together with the embedder's ``model_key``, so:

* a new or changed definition gets (re-)embedded,
* an unchanged one is skipped, even across restarts with a persistent index,
* a removed one is deleted from the index,
* an embedding model change re-embeds everything (the index discards the
  previous model's vectors in ``prepare``).
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
    IToolAccessPolicy,
    IToolEmbedderPort,
    IToolIndexPort,
    IToolRegistry,
    PublishedTool,
    ToolAccessDeniedError,
    ToolAction,
    ToolAlreadyPublishedError,
    ToolAvailability,
    ToolConfigurationError,
    ToolContext,
    ToolDefinition,
    ToolId,
    ToolIndexEntry,
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
        self._access_policy = access_policy or ScopeToolAccessPolicy()
        # Ids the index holds for this registry, and the model they were
        # embedded with. ``None`` means "never synced in this process".
        self._indexed: dict[str, str] | None = None
        self._indexed_model_key: str | None = None
        # Set by every publication change; lets searches skip fingerprinting
        # the whole catalog when nothing changed.
        self._dirty = True

    # ----------------------------------------------------------------- wiring
    def configure_search(
        self, embedder: IToolEmbedderPort | None, index: IToolIndexPort | None
    ) -> None:
        """Install (or replace) the search backend. Forces a full re-sync."""
        with self._lock:
            self._embedder = embedder
            self._index = index
            self._indexed = None
            self._indexed_model_key = None
            self._dirty = True

    @property
    def search_available(self) -> bool:
        return self._embedder is not None and self._index is not None

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
    def _lookup(self, ref: str | ToolRef | ToolId) -> PublishedTool:
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
        if not candidates:
            raise ToolNotFoundError(
                f"No published tool matches '{ref}'. Check the module publishing "
                "it is enabled, and the reference's namespace, name and version."
            )
        return max(candidates, key=lambda t: t.definition.id.version_key)

    def get_definition(self, ref: str | ToolRef | ToolId) -> ToolDefinition:
        return self._lookup(ref).definition

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
        with self._lock:
            definitions = [t.definition for t in self._tools.values()]
        if context is not None:
            definitions = [
                d for d in definitions if self._can(d, context, ToolAction.DISCOVER)
            ]
        return sorted(definitions, key=lambda d: str(d.id))

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
        missing = self._missing_config(self._lookup(ref), config)
        return ToolAvailability(available=not missing, missing_config=missing)

    # ------------------------------------------------------------ resolution
    def check_access(
        self,
        ref: str | ToolRef | ToolId,
        context: ToolContext,
        action: ToolAction,
    ) -> ToolDefinition:
        definition = self._lookup(ref).definition
        self._access_policy.check(definition, context, action)
        return definition

    def resolve(
        self,
        ref: str | ToolRef | ToolId,
        context: ToolContext,
        config: Mapping[str, Any] | None = None,
        action: ToolAction = ToolAction.EXECUTE,
    ) -> object:
        tool = self._lookup(ref)
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
        embedder, index = self._require_search()
        context = context or ToolContext()
        self.sync_index()
        vector = embedder.embed_query(query)

        results: list[ToolSearchResult] = []
        seen: set[str] = set()
        stale: list[str] = []
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
                    stale.append(hit.id)
                    continue
                if not self._can(tool.definition, context, ToolAction.DISCOVER):
                    continue
                if where is not None and not where(tool.definition):
                    continue
                missing = self._missing_config(tool, None)
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

        if stale:
            # Leftovers of a previous process sharing a persistent index.
            index.delete(stale)
        return results[:limit]
