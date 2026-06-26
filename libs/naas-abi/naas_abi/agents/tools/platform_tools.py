"""Tools exposing the ABI platform data services to an agent.

Each tool resolves its service lazily at call time via
``ABIModule.get_instance().engine.services.<svc>`` (the same pattern AbiAgent.New
uses), so importing this module is cheap and the services are guaranteed
initialised by the time an agent actually runs. Every tool catches service
errors and returns ``{"error": ...}`` so a failure is reported to the model
instead of crashing the agent turn.

Scope: read-heavy + safe writes across the knowledge graph (triple store),
object storage, vector store, cache and key-value store. Sensitive/side-effecting
services (secrets, message bus, email) are intentionally excluded for now.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool


def _services() -> Any:
    from naas_abi import ABIModule  # noqa: PLC0415 - lazy, services init by call time

    return ABIModule.get_instance().engine.services


def platform_service_tools() -> list[BaseTool]:
    # --- Knowledge graph (triple store / SPARQL) ---
    @tool
    def kg_sparql_query(query: str) -> Any:
        """Run a SPARQL query against the knowledge graph (triple store) and
        return the result rows. Use this to answer questions about entities and
        relationships in the graph."""
        try:
            from naas_abi_core.utils.SPARQL import SPARQLUtils  # noqa: PLC0415

            ts = _services().triple_store
            return SPARQLUtils(ts).results_to_list(ts.query(query))
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def kg_list_graphs() -> Any:
        """List the named graphs in the knowledge graph (triple store)."""
        try:
            return [str(g) for g in _services().triple_store.list_graphs()]
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    # --- Object storage ---
    @tool
    def storage_list_objects(prefix: str = "") -> Any:
        """List object keys in the object storage under a prefix (folder)."""
        try:
            return [str(o) for o in _services().object_storage.list_objects(prefix)]
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def storage_get_object(prefix: str, key: str) -> Any:
        """Read an object from object storage. Returns its text when decodable,
        otherwise its size in bytes."""
        try:
            data = _services().object_storage.get_object(prefix, key)
            try:
                return {"text": data.decode("utf-8")}
            except UnicodeDecodeError:
                return {"binary": True, "bytes": len(data)}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    # --- Vector store ---
    @tool
    def vector_list_collections() -> Any:
        """List the collections in the vector store (semantic search index)."""
        try:
            return _services().vector_store.list_collections()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def vector_collection_size(collection_name: str) -> Any:
        """Return the number of documents in a vector store collection."""
        try:
            size = _services().vector_store.get_collection_size(collection_name)
            return {"collection": collection_name, "size": size}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    # --- Cache ---
    @tool
    def cache_get(key: str) -> Any:
        """Get a value from the cache by key (returns None if absent)."""
        try:
            return {"key": key, "value": str(_services().cache.get(key))}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def cache_set(key: str, value: str) -> Any:
        """Set a text value in the cache by key."""
        try:
            _services().cache.set_text(key, value)
            return {"ok": True, "key": key}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    # --- Key-value store ---
    @tool
    def kv_get(key: str) -> Any:
        """Get a value from the key-value store by key."""
        try:
            value = _services().kv.get(key)
            text = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
            return {"key": key, "value": text}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def kv_set(key: str, value: str) -> Any:
        """Set a value in the key-value store by key."""
        try:
            _services().kv.set(key, value.encode("utf-8"))
            return {"ok": True, "key": key}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    return [
        kg_sparql_query,
        kg_list_graphs,
        storage_list_objects,
        storage_get_object,
        vector_list_collections,
        vector_collection_size,
        cache_get,
        cache_set,
        kv_get,
        kv_set,
    ]
