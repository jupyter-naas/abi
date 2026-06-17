"""Google-like entity search across data graphs (Composer grain picker).

For a free-text string, return a mix of CLASSES and INDIVIDUALS across the given (or all
owned) named graphs, each tagged with its ``kind`` so the frontend can configure the
Composer grain from a click. A class hit carries an instance count; an individual hit
carries its ``rdf:type`` domain class.

Pure-ish: takes an ``IGraphQueryStore`` and emits SPARQL; no FastAPI/ABIModule coupling,
so it is unit-testable over a fake store and runnable against the live triple store.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import IGraphQueryStore
from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import (
    SearchHitData,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import (
    sparql_iri,
    sparql_string_literal,
)

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"

# Meta-classes that are never a meaningful "domain class" for a hit — excluded from both
# the class scan and the individual's rdf:type.
_EXCLUDED_TYPES = (
    "http://www.w3.org/2002/07/owl#NamedIndividual",
    "http://www.w3.org/2002/07/owl#Class",
    "http://www.w3.org/2000/01/rdf-schema#Class",
    "http://www.w3.org/2002/07/owl#Ontology",
    "http://www.w3.org/2002/07/owl#ObjectProperty",
    "http://www.w3.org/2002/07/owl#DatatypeProperty",
    "http://www.w3.org/2002/07/owl#AnnotationProperty",
)


def _fragment(uri: str) -> str:
    for sep in ("#", "/"):
        if sep in uri:
            tail = uri.rsplit(sep, 1)[-1]
            if tail:
                return tail
    return uri


def _int(row: dict, key: str) -> int:
    b = row.get(key)
    try:
        return int(b.value) if b is not None else 0
    except (ValueError, AttributeError):
        return 0


def _excluded_filter(var: str) -> str:
    excl = ", ".join(sparql_iri(t) for t in _EXCLUDED_TYPES)
    return f"FILTER({var} NOT IN ({excl}))"


def search_entities(
    store: IGraphQueryStore,
    *,
    graph_uris: list[str],
    query: str,
    limit: int = 20,
) -> tuple[SearchHitData, ...]:
    graphs = " ".join(sparql_iri(g) for g in graph_uris)
    lit = sparql_string_literal(query)
    rdf_type = sparql_iri(_RDF_TYPE)
    rdfs_label = sparql_iri(_RDFS_LABEL)

    # ── (A) CLASSES — any ?cls used as `?s a ?cls` (minus meta-classes), counted ──
    # MATCH when the class fragment OR the class IRI contains the query (case-insensitive).
    # Counting is done in SPARQL against the data, so the fragment match is applied in Python.
    class_rows = store.select(
        f"""
        SELECT ?cls ?g (COUNT(DISTINCT ?s) AS ?cnt)
        WHERE {{ VALUES ?g {{ {graphs} }} GRAPH ?g {{
            ?s {rdf_type} ?cls . FILTER(isIRI(?cls)) {_excluded_filter("?cls")}
            FILTER(CONTAINS(LCASE(STR(?cls)), LCASE({lit})))
        }} }} GROUP BY ?cls ?g
        ORDER BY DESC(?cnt)
        LIMIT {int(limit)}
        """
    )

    # ── (B) INDIVIDUALS — `?uri a ?cls` (minus meta-classes), label-or-uri match ──
    ind_rows = store.select(
        f"""
        SELECT ?uri ?cls ?g (COALESCE(?lbl, STR(?uri)) AS ?label)
        WHERE {{ VALUES ?g {{ {graphs} }} GRAPH ?g {{
            ?uri {rdf_type} ?cls . FILTER(isIRI(?cls)) {_excluded_filter("?cls")}
            OPTIONAL {{ ?uri {rdfs_label} ?lbl }}
            BIND(COALESCE(?lbl, STR(?uri)) AS ?l)
            FILTER(CONTAINS(LCASE(STR(?l)), LCASE({lit})) || CONTAINS(LCASE(STR(?uri)), LCASE({lit})))
        }} }}
        LIMIT {int(limit)}
        """
    )

    needle = query.strip().lower()

    # ── classes — apply the fragment/IRI match in Python (the SPARQL only matched the IRI) ──
    class_hits: list[SearchHitData] = []
    for r in class_rows:
        cls = r.get("cls")
        if cls is None:
            continue
        cls_uri = cls.value
        label = _fragment(cls_uri)
        if needle and needle not in label.lower() and needle not in cls_uri.lower():
            continue
        g = r.get("g")
        class_hits.append(
            SearchHitData(
                uri=cls_uri,
                label=label,
                kind="class",
                class_uri=cls_uri,
                class_label=label,
                graph_uri=g.value if g is not None else "",
                instance_count=_int(r, "cnt"),
            )
        )
    class_hits.sort(key=lambda h: (-h.instance_count, h.label.lower()))

    # ── individuals ──
    ind_hits: list[SearchHitData] = []
    for r in ind_rows:
        uri = r.get("uri")
        cls = r.get("cls")
        if uri is None or cls is None:
            continue
        lbl = r.get("label")
        label = lbl.value if lbl is not None else uri.value
        g = r.get("g")
        ind_hits.append(
            SearchHitData(
                uri=uri.value,
                label=label,
                kind="individual",
                class_uri=cls.value,
                class_label=_fragment(cls.value),
                graph_uri=g.value if g is not None else "",
                instance_count=0,
            )
        )
    ind_hits.sort(key=lambda h: h.label.lower())

    # classes first, then individuals — each kind capped at `limit`.
    return tuple(class_hits[:limit] + ind_hits[:limit])
