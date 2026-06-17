"""Triple-store-backed implementation of ``IGraphQueryStore`` (AUDIT §7b.5).

Wraps the configured ``TripleStoreService`` (or any object with ``query(sparql) -> rdflib
Result``). Transport stays in the underlying triple-store secondary adapter (Fuseki/Oxigraph/
embedded); this adapter only (a) shapes ``Result`` rows into ``Binding`` dicts and (b) reports
the full-text capability so the compiler can pick ``text:query`` vs ``CONTAINS``.
"""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import (
    Binding,
    IGraphQueryStore,
    ResultRow,
)
from rdflib import URIRef


class GraphQueryTripleStoreAdapter(IGraphQueryStore):
    def __init__(self, triple_store: Any, *, fts_backend: str = "none") -> None:
        self._store = triple_store
        self._fts_backend = fts_backend

    def select(self, sparql: str) -> list[ResultRow]:
        # The triple-store adapters yield an iterator of rdflib ResultRow; the variable
        # names live on each row's `.labels` (name → index), not on a Result.vars.
        rows: list[ResultRow] = []
        for row in self._store.query(sparql):
            binding: ResultRow = {}
            for name in getattr(row, "labels", None) or {}:
                term = row[name]
                if term is None:  # OPTIONAL miss → omit (sparse row)
                    continue
                binding[str(name)] = Binding(value=str(term), is_uri=isinstance(term, URIRef))
            rows.append(binding)
        return rows

    def count(self, sparql: str) -> int:
        for row in self._store.query(sparql):
            for name in getattr(row, "labels", None) or {}:
                term = row[name]
                if term is not None:
                    return int(str(term))
        return 0

    def supports_fulltext(self) -> bool:
        return self._fts_backend == "jena_text"


def resolve_fts_backend(triple_store: Any) -> str:
    """Which full-text dialect the configured backend supports.

    v1 returns ``"none"`` (portable ``CONTAINS``): jena-text needs the Fuseki dataset to be
    assembled with a per-predicate Lucene index, which isn't introspectable from here and
    isn't enabled in dev. Flip this to ``"jena_text"`` once that deployment work lands — it's
    the single switch that turns on the compiler's index-accelerated search path.
    """
    return "none"
