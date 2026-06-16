"""Column discovery: ontology ∪ data (AUDIT §7b.7.2).

For an anchored class, return the columns a user can select — the **union** of
(a) properties/relations the ontology declares for the class (incl. inherited, so a
valid-but-empty relation still appears) and (b) predicates that actually occur on
instances (with counts + sampled datatypes). Each is tagged ``source: ontology|data|both``.

Pure-ish: takes an ``IGraphQueryStore`` and emits SPARQL; no FastAPI/ABIModule coupling,
so it is unit-testable over a fake store and runnable against the live triple store.
"""

from __future__ import annotations

import re

from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import IGraphQueryStore
from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import (
    DiscoveredColumn,
    TargetClassData,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import sparql_iri

SCHEMA_GRAPH = "http://ontology.naas.ai/graph/schema"
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_OWL_NAMED_INDIVIDUAL = "http://www.w3.org/2002/07/owl#NamedIndividual"
_XSD = "http://www.w3.org/2001/XMLSchema#"

# distinct-objects / subjects above this ⇒ a free-text-ish column → faceting refused.
_HIGH_CARDINALITY_RATIO = 0.8


def _fragment(uri: str) -> str:
    for sep in ("#", "/"):
        if sep in uri:
            tail = uri.rsplit(sep, 1)[-1]
            if tail:
                return tail
    return uri


def _slug(uri: str, direction: str = "out") -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", _fragment(uri)) or "col"
    return base if direction == "out" else f"{base}__in"


def _xsd_to_datatype(range_uri: str | None) -> str | None:
    if not range_uri:
        return None
    frag = _fragment(range_uri)
    if frag in ("integer", "int", "long", "short", "decimal", "float", "double",
                "nonNegativeInteger", "positiveInteger", "byte"):
        return "number"
    if frag in ("date", "dateTime", "time", "gYear", "gYearMonth"):
        return "date"
    if frag == "boolean":
        return "boolean"
    if frag in ("string", "langString", "normalizedString", "token", "anyURI"):
        return "string"
    return None


def _int(row: dict, key: str) -> int:
    b = row.get(key)
    try:
        return int(b.value) if b is not None else 0
    except (ValueError, AttributeError):
        return 0


def discover_columns(
    store: IGraphQueryStore,
    *,
    graph_uris: list[str],
    class_uris: list[str],
    schema_graph: str = SCHEMA_GRAPH,
) -> tuple[DiscoveredColumn, ...]:
    graphs = " ".join(sparql_iri(g) for g in graph_uris)
    classes = " ".join(sparql_iri(c) for c in class_uris)

    # ── (A) data side — datatype properties (literal objects) ─────────────────
    dt_rows = store.select(
        f"""
        SELECT ?p (COUNT(DISTINCT ?s) AS ?subjects) (COUNT(?o) AS ?objs)
               (COUNT(DISTINCT ?o) AS ?distinct_objs) (SAMPLE(DATATYPE(?o)) AS ?dt)
        WHERE {{ VALUES ?g {{ {graphs} }} VALUES ?cls {{ {classes} }} GRAPH ?g {{
            ?s a ?cls . ?s ?p ?o . FILTER(isLiteral(?o)) FILTER(?p != {sparql_iri(_RDF_TYPE)})
        }} }} GROUP BY ?p
        """
    )
    # ── (B) data side — relations (IRI objects) ───────────────────────────────
    rel_rows = store.select(
        f"""
        SELECT ?p (COUNT(DISTINCT ?s) AS ?subjects) (COUNT(?o) AS ?objs)
        WHERE {{ VALUES ?g {{ {graphs} }} VALUES ?cls {{ {classes} }} GRAPH ?g {{
            ?s a ?cls . ?s ?p ?o . FILTER(isIRI(?o)) FILTER(?p != {sparql_iri(_RDF_TYPE)})
        }} }} GROUP BY ?p
        """
    )
    # ── (B-tc) relation target classes ────────────────────────────────────────
    tc_rows = store.select(
        f"""
        SELECT ?p ?tc (COUNT(DISTINCT ?s) AS ?subjects)
        WHERE {{ VALUES ?g {{ {graphs} }} VALUES ?cls {{ {classes} }} GRAPH ?g {{
            ?s a ?cls . ?s ?p ?o . FILTER(isIRI(?o)) FILTER(?p != {sparql_iri(_RDF_TYPE)})
            ?o a ?tc . FILTER(isIRI(?tc)) FILTER(?tc != {sparql_iri(_OWL_NAMED_INDIVIDUAL)})
        }} }} GROUP BY ?p ?tc
        """
    )
    # ── (B-in) data side — INCOMING relations (grain is the object: ?s ?p ?grain) ──
    in_rel_rows = store.select(
        f"""
        SELECT ?p (COUNT(DISTINCT ?o) AS ?objects)
        WHERE {{ VALUES ?g {{ {graphs} }} VALUES ?cls {{ {classes} }} GRAPH ?g {{
            ?o a ?cls . ?s ?p ?o . FILTER(isIRI(?s)) FILTER(?p != {sparql_iri(_RDF_TYPE)})
        }} }} GROUP BY ?p
        """
    )
    # ── (B-in-tc) incoming relation source classes (the entity on the other end) ──
    in_tc_rows = store.select(
        f"""
        SELECT ?p ?sc (COUNT(DISTINCT ?o) AS ?objects)
        WHERE {{ VALUES ?g {{ {graphs} }} VALUES ?cls {{ {classes} }} GRAPH ?g {{
            ?o a ?cls . ?s ?p ?o . FILTER(isIRI(?s)) FILTER(?p != {sparql_iri(_RDF_TYPE)})
            ?s a ?sc . FILTER(isIRI(?sc)) FILTER(?sc != {sparql_iri(_OWL_NAMED_INDIVIDUAL)})
        }} }} GROUP BY ?p ?sc
        """
    )
    # ── (C) ontology side — declared props for the class (incl. inherited) ────
    ont_rows = store.select(
        f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?prop ?ptype ?range
        WHERE {{ GRAPH {sparql_iri(schema_graph)} {{
            VALUES ?cls {{ {classes} }}
            ?prop a ?ptype .
            FILTER(?ptype IN (owl:DatatypeProperty, owl:ObjectProperty, owl:AnnotationProperty))
            ?prop rdfs:domain ?dom . ?cls rdfs:subClassOf* ?dom .
            OPTIONAL {{ ?prop rdfs:range ?range . FILTER(isIRI(?range)) }}
        }} }}
        """
    )

    # target classes per predicate (out direction)
    targets: dict[str, list[TargetClassData]] = {}
    for r in tc_rows:
        p = r["p"].value
        tc = r.get("tc")
        if tc is None:
            continue
        targets.setdefault(p, []).append(
            TargetClassData(uri=tc.value, label=_fragment(tc.value), instance_count=_int(r, "subjects"))
        )

    # source classes per INCOMING predicate (the class reached by going "in")
    in_targets: dict[str, list[TargetClassData]] = {}
    for r in in_tc_rows:
        p = r["p"].value
        sc = r.get("sc")
        if sc is None:
            continue
        in_targets.setdefault(p, []).append(
            TargetClassData(uri=sc.value, label=_fragment(sc.value), instance_count=_int(r, "objects"))
        )

    # ontology declarations keyed by predicate
    ont: dict[str, dict] = {}
    for r in ont_rows:
        p = r["prop"].value
        ptype = _fragment(r["ptype"].value) if r.get("ptype") else ""
        range_uri = r["range"].value if r.get("range") else None
        ont.setdefault(p, {"is_object": False, "range": None})
        if ptype == "ObjectProperty":
            ont[p]["is_object"] = True
        if range_uri and not ont[p]["range"]:
            ont[p]["range"] = range_uri

    columns: list[DiscoveredColumn] = []

    # data-side datatype properties
    seen: set[str] = set()
    for r in dt_rows:
        p = r["p"].value
        seen.add(p)
        subjects, objs, distinct_objs = _int(r, "subjects"), _int(r, "objs"), _int(r, "distinct_objs")
        dt_uri = r["dt"].value if r.get("dt") else None
        datatype = _xsd_to_datatype(dt_uri) or "string"
        ont_range_dt = _xsd_to_datatype(ont.get(p, {}).get("range")) if p in ont else None
        if ont_range_dt:
            datatype, dt_source = ont_range_dt, "ontology-range"
        else:
            dt_source = "sampled"
        high_card = datatype == "string" and subjects > 0 and (distinct_objs / subjects) > _HIGH_CARDINALITY_RATIO
        columns.append(DiscoveredColumn(
            id=_slug(p), predicate_uri=p, label=_fragment(p), kind="property", direction="out",
            datatype=datatype, datatype_source=dt_source,
            source="both" if p in ont else "data", instance_count=subjects,
            is_functional=(objs == subjects and subjects > 0), facetable=not high_card,
        ))

    # data-side relations
    for r in rel_rows:
        p = r["p"].value
        seen.add(p)
        subjects, objs = _int(r, "subjects"), _int(r, "objs")
        columns.append(DiscoveredColumn(
            id=_slug(p), predicate_uri=p, label=_fragment(p), kind="relation", direction="out",
            datatype="iri", datatype_source="ontology-range" if p in ont else "default",
            source="both" if p in ont else "data", instance_count=subjects,
            is_functional=(objs == subjects and subjects > 0), facetable=True,
            target_classes=tuple(targets.get(p, ())),
        ))

    # data-side INCOMING relations (grain is the OBJECT: ?s ?p ?grain) — direction "in".
    # Slugged "<frag>__in" so they never collide with an outgoing relation of the same
    # predicate; label is arrow-prefixed so it's clear the relation points AT the grain.
    for r in in_rel_rows:
        p = r["p"].value
        columns.append(DiscoveredColumn(
            id=_slug(p, "in"), predicate_uri=p, label=f"← {_fragment(p)}", kind="relation", direction="in",
            datatype="iri", datatype_source="default",
            source="data", instance_count=_int(r, "objects"),
            is_functional=False, facetable=True,
            target_classes=tuple(in_targets.get(p, ())),
        ))

    # ontology-only declarations (valid-but-empty → instance_count 0, source "ontology")
    for p, info in ont.items():
        if p in seen:
            continue
        is_relation = info["is_object"]
        datatype = "iri" if is_relation else (_xsd_to_datatype(info["range"]) or "string")
        columns.append(DiscoveredColumn(
            id=_slug(p), predicate_uri=p, label=_fragment(p),
            kind="relation" if is_relation else "property", direction="out",
            datatype=datatype,
            datatype_source="ontology-range" if (is_relation or _xsd_to_datatype(info["range"])) else "default",
            source="ontology", instance_count=0, is_functional=False, facetable=True,
        ))

    columns.sort(key=lambda c: (c.kind != "property", -c.instance_count, c.label.lower()))
    return tuple(columns)
