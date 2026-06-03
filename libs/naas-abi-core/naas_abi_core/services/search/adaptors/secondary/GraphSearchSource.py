"""GraphSearchSource — search over the triple store.

This is a SCAFFOLD. The default `search` is a SPARQL `CONTAINS` over common
label predicates — works against every triple_store backend (Oxigraph, Jena,
Neptune, Filesystem) with no extra infra, but performs a full literal scan.
Swap in Jena's `text:query` / Neptune's OpenSearch / a sidecar vector index
later by overriding `_run_lexical_search` or registering a second source
(e.g. `GraphVectorSearchSource`) and letting `SearchService` federate them.

Indexing path (currently TODO):
- Subscribe to `TripleStoreService.subscribe((None, None, None), cb, "*")`
  to receive per-triple `bytes` payloads. Parse with rdflib, group changes
  by subject, debounce, and re-project the subject's outgoing literals into
  a `Document`. Then push to a vector store / FTS index.
- Subscribe to `EventService` for `TriplesInserted` / `GraphDropped` /
  `GraphCleared` to drive graph-scope ops (drop a whole partition when a
  graph is dropped) and to power monitoring cross-checks ("event log says
  N inserts, index has N-5 → trigger reindex").
- On failure inside any of the above, publish `SearchIndexFailed` via
  `EventService.publish` and continue. Do NOT retry inline — retry is a
  separate consumer's concern.
"""

from __future__ import annotations

from typing import Any, Iterator

import rdflib

from naas_abi_core.services.search.SearchPorts import (
    Document,
    ISearchSource,
    SearchHit,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


# Predicates we treat as "label-ish" when scanning literals. Order matters
# for snippet pick: prefer prefLabel over altLabel over plain label, etc.
LABEL_PREDICATES = [
    "http://www.w3.org/2004/02/skos/core#prefLabel",
    "http://www.w3.org/2000/01/rdf-schema#label",
    "http://www.w3.org/2004/02/skos/core#altLabel",
    "http://www.w3.org/2000/01/rdf-schema#comment",
]


class GraphSearchSource(ISearchSource):
    def __init__(self, triple_store: TripleStoreService, name: str = "graph"):
        self._triple_store = triple_store
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> Iterator[SearchHit]:
        if not query.strip():
            return

        # Escape the user-supplied string. SPARQL string literals use the same
        # escapes as Turtle: backslash and quote. Replace in this order so
        # we don't double-escape backslashes we just inserted.
        escaped = query.replace("\\", "\\\\").replace('"', '\\"')

        label_filter = " || ".join(
            f"?p = <{p}>" for p in LABEL_PREDICATES
        )

        sparql = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT ?s ?p ?lit ?type ?g WHERE {{
                GRAPH ?g {{
                    ?s ?p ?lit .
                    OPTIONAL {{ ?s a ?type . }}
                    FILTER(isLiteral(?lit))
                    FILTER({label_filter})
                    FILTER(CONTAINS(LCASE(STR(?lit)), LCASE("{escaped}")))
                }}
            }}
            LIMIT {int(limit)}
        """

        results = self._triple_store.query(sparql)
        for row in results:
            assert isinstance(row, rdflib.query.ResultRow)
            s, p, lit, type_, g = row
            yield SearchHit(
                id=str(s),
                source=self._name,
                kind="entity",
                title=str(lit),
                snippet=str(lit),
                score=1.0,  # lexical CONTAINS has no meaningful score
                url=str(s),
                highlights=[str(lit)],
                metadata={
                    "graph": str(g) if g else None,
                    "matched_predicate": str(p),
                    "type": str(type_) if type_ else None,
                },
            )

    # ------------------------------------------------------------------
    # indexing (TODO)
    # ------------------------------------------------------------------

    def supports_indexing(self) -> bool:
        # Flip to True once the vector / FTS sidecar is wired in. The lexical
        # SPARQL path above queries the triple store live and needs no index.
        return False

    def index(self, document: Document) -> None:  # noqa: D401
        raise NotImplementedError("GraphSearchSource: vector index path not implemented yet")

    def remove(self, document_id: str) -> None:  # noqa: D401
        raise NotImplementedError("GraphSearchSource: vector index path not implemented yet")

    def reindex(self) -> int:  # noqa: D401
        raise NotImplementedError("GraphSearchSource: vector index path not implemented yet")
