"""Nexus's own application graph, read and written as Nexus.

``http://ontology.naas.ai/graph/nexus`` holds the metadata Nexus keeps about
knowledge graphs (labels, roles) and views' filters. It is the platform's: IAM
placed it in no workspace, so no member's role reaches it. Nexus reads and
writes it as ``api`` for no user, after the request has been authorized for the
data it is about (the graph's own placement decides that, through the kernel).
"""

from __future__ import annotations

from typing import Any

from naas_abi_core.engine.call_context import as_service_account


class NexusCatalogStore:
    """The triple store, used as ``api`` for no user (the catalog graph only)."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def query(self, query: str) -> Any:
        with as_service_account("api"):
            return self._store.query(query)

    def insert(self, triples: Any, graph_name: Any) -> Any:
        with as_service_account("api"):
            return self._store.insert(triples, graph_name=graph_name)

    def remove(self, triples: Any, graph_name: Any) -> Any:
        with as_service_account("api"):
            return self._store.remove(triples, graph_name=graph_name)

    def list_graphs(self) -> Any:
        with as_service_account("api"):
            return self._store.list_graphs()

    def create_graph(self, graph_name: Any) -> Any:
        with as_service_account("api"):
            return self._store.create_graph(graph_name)
