"""Read-only projections for the Explorer. Composer query execution stays separate."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
    GraphPackData,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import (
    sparql_iri,
    sparql_string_literal,
)

PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
"""
NAMED = "http://www.w3.org/2002/07/owl#NamedIndividual"
# A typed IRI is an instance, except resources declaring schema constructs.
INSTANCE = """
?s a ?instanceType . FILTER(isIRI(?s) && isIRI(?instanceType))
FILTER(?instanceType NOT IN (owl:Class, rdfs:Class, owl:Ontology,
 owl:ObjectProperty, owl:DatatypeProperty, owl:AnnotationProperty,
 rdf:Property, rdfs:Datatype, owl:Restriction, owl:Axiom))
FILTER NOT EXISTS { ?s a ?schemaType .
 VALUES ?schemaType { owl:Class rdfs:Class owl:Ontology owl:ObjectProperty
 owl:DatatypeProperty owl:AnnotationProperty rdf:Property rdfs:Datatype owl:Restriction owl:Axiom } }
"""


class QueryStore(Protocol):
    def query(self, query: str, /) -> Iterable[Any]: ...


def rows(store: QueryStore, query: str) -> list[dict[str, Any]]:
    # Propagate failures: a failed query must not masquerade as an empty graph.
    return [row.asdict() for row in store.query(PREFIXES + query)]


def resolve_graphs(packs: list[GraphPackData], requested: list[str]) -> list[str]:
    allowed = {g.uri for pack in packs for g in pack.graphs}
    for uri in requested:
        sparql_iri(uri)
    if set(requested) - allowed:
        raise GraphAccessError("One or more selected graphs are unavailable.")
    return sorted(set(requested) if requested else allowed)


def values(graphs: list[str]) -> str:
    return "VALUES ?g { " + " ".join(map(sparql_iri, graphs)) + " }"


def local_name(uri: str) -> str:
    return uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1] or uri


def catalog(
    store: QueryStore, packs: list[GraphPackData], graphs: list[str], schema_uri: str
) -> dict[str, Any]:
    """Sidebar metadata only; opening an instance view must not require dashboard totals."""
    graph_catalog = {
        g.uri: {
            "uri": g.uri,
            "id": g.id,
            "label": g.label,
            "role_label": pack.role_label,
            "can_write": g.can_write,
        }
        for pack in packs
        for g in pack.graphs
    }
    if not graphs:
        return {
            "graphs": list(graph_catalog.values()),
            "selected_graphs": [],
            "classes": [],
        }
    scope = values(graphs)
    classes: dict[str, dict[str, Any]] = {
        str(row["cls"]): {
            "uri": str(row["cls"]),
            "label": local_name(str(row["cls"])),
            "count": int(row["total"]),
            "parents": [],
        }
        for row in rows(
            store,
            f"""
          SELECT ?cls (COUNT(DISTINCT ?s) AS ?total) WHERE {{
            {scope} GRAPH ?g {{ {INSTANCE} BIND(?instanceType AS ?cls)
              FILTER(?cls != owl:NamedIndividual) }}
          }} GROUP BY ?cls
        """,
        )
    }
    # Only ancestors of classes in this scope. No full schema download or N+1 label lookups.
    if classes:
        class_values = " ".join(map(sparql_iri, classes))
        metadata_scope = values(sorted(set(graphs + [schema_uri])))
        hierarchy = rows(
            store,
            f"""
          SELECT DISTINCT ?child ?parent WHERE {{
            VALUES ?cls {{ {class_values} }} {metadata_scope}
            GRAPH ?g {{ ?cls rdfs:subClassOf* ?child .
              ?child rdfs:subClassOf ?parent .
              FILTER(isIRI(?child) && isIRI(?parent)) }}
          }}
        """,
        )
        for row in hierarchy:
            child, parent = str(row["child"]), str(row["parent"])
            for uri in (child, parent):
                classes.setdefault(
                    uri,
                    {"uri": uri, "label": local_name(uri), "count": 0, "parents": []},
                )
            if parent not in classes[child]["parents"]:
                classes[child]["parents"].append(parent)
        label_values = " ".join(map(sparql_iri, classes))
        for row in rows(
            store,
            f"""
          SELECT ?cls (MIN(STR(?rawLabel)) AS ?label) WHERE {{
            VALUES ?cls {{ {label_values} }} {metadata_scope}
            GRAPH ?g {{ ?cls rdfs:label ?rawLabel . FILTER(isLiteral(?rawLabel)) }}
          }} GROUP BY ?cls
        """,
        ):
            classes[str(row["cls"])]["label"] = str(row["label"])
    return {
        "graphs": list(graph_catalog.values()),
        "selected_graphs": graphs,
        "classes": sorted(
            classes.values(), key=lambda c: (c["label"].lower(), c["uri"])
        ),
    }


def overview(
    store: QueryStore, packs: list[GraphPackData], graphs: list[str], schema_uri: str
) -> dict[str, Any]:
    graph_catalog = {
        g.uri: {
            "uri": g.uri,
            "id": g.id,
            "label": g.label,
            "role_label": pack.role_label,
        }
        for pack in packs
        for g in pack.graphs
    }
    zero = {
        "triples": 0,
        "instances": 0,
        "named_individuals": 0,
        "labeled_instances": 0,
        "classes": 0,
        "predicates": 0,
        "relations": 0,
        "literal_values": 0,
    }
    if not graphs:
        return {
            "graphs": list(graph_catalog.values()),
            "selected_graphs": [],
            "kpis": zero,
            "classes": [],
            "graph_metrics": [],
        }
    scope = values(graphs)
    triple_rows = rows(
        store,
        f"""
      SELECT ?g (COUNT(*) AS ?triples) (COUNT(DISTINCT ?p) AS ?predicates)
        (SUM(IF(isIRI(?o) && ?p != rdf:type, 1, 0)) AS ?relations)
        (SUM(IF(isLiteral(?o), 1, 0)) AS ?literal_values)
      WHERE {{ {scope} GRAPH ?g {{ ?s ?p ?o }} }} GROUP BY ?g
    """,
    )
    per_graph: dict[str, dict[str, Any]] = {
        uri: {**graph_catalog[uri], **zero} for uri in graphs
    }
    for row in triple_rows:
        per_graph[str(row["g"])].update(
            {
                k: int(row[k])
                for k in ("triples", "predicates", "relations", "literal_values")
            }
        )
    for row in rows(
        store,
        f"""
      SELECT ?g (COUNT(DISTINCT ?s) AS ?instances)
      WHERE {{ {scope} GRAPH ?g {{ {INSTANCE} }} }} GROUP BY ?g
    """,
    ):
        per_graph[str(row["g"])]["instances"] = int(row["instances"])
    aggregate = rows(
        store,
        f"""
      SELECT ?instances ?named_individuals ?labeled_instances WHERE {{
        {{ SELECT (COUNT(DISTINCT ?s) AS ?instances) WHERE {{
          {scope} GRAPH ?g {{ {INSTANCE} }}
        }} }}
        {{ SELECT (COUNT(DISTINCT ?s) AS ?named_individuals) WHERE {{
          {scope} GRAPH ?g {{ {INSTANCE}
            FILTER EXISTS {{ ?s a owl:NamedIndividual }} }}
        }} }}
        {{ SELECT (COUNT(DISTINCT ?s) AS ?labeled_instances) WHERE {{
          {scope} GRAPH ?g {{ {INSTANCE}
            FILTER EXISTS {{ ?s rdfs:label ?label .
              FILTER(isLiteral(?label) && STRLEN(STR(?label)) > 0) }} }}
        }} }}
      }}
    """,
    )[0]
    kpis = {
        **zero,
        **{
            k: int(aggregate[k])
            for k in ("instances", "named_individuals", "labeled_instances")
        },
    }
    for key in ("triples", "relations", "literal_values"):
        kpis[key] = sum(int(g[key]) for g in per_graph.values())
    kpis["predicates"] = int(
        rows(
            store,
            f"""
      SELECT (COUNT(DISTINCT ?p) AS ?n)
      WHERE {{ {scope} GRAPH ?g {{ ?s ?p ?o }} }}
    """,
        )[0]["n"]
    )
    metadata = catalog(store, packs, graphs, schema_uri)
    kpis["classes"] = sum(c["count"] > 0 for c in metadata["classes"])
    return {
        "graphs": list(graph_catalog.values()),
        "selected_graphs": graphs,
        "kpis": kpis,
        "classes": metadata["classes"],
        "graph_metrics": list(per_graph.values()),
    }


def instances(
    store: QueryStore,
    graphs: list[str],
    class_uris: list[str],
    search: str,
    offset: int,
    limit: int,
    schema_uri: str,
    *,
    include_counts: bool = True,
) -> dict[str, Any]:
    if not graphs:
        return {"items": [], "has_more": False}
    class_filter = (
        ("VALUES ?instanceType { " + " ".join(map(sparql_iri, class_uris)) + " }")
        if class_uris
        else ""
    )
    search_filter = ""
    if search.strip():
        needle = sparql_string_literal(search.strip().lower())
        search_filter = f"""FILTER(CONTAINS(LCASE(STR(?s)), {needle}) ||
          EXISTS {{ ?s rdfs:label ?searchLabel .
                    FILTER(CONTAINS(LCASE(STR(?searchLabel)), {needle})) }})"""
    # Paginate graph/subject pairs before joining labels, properties or multiple rdf:types.
    page = rows(
        store,
        f"""
      SELECT DISTINCT ?g ?s WHERE {{ {values(graphs)} GRAPH ?g {{
        {INSTANCE} {class_filter} {search_filter}
      }} }} ORDER BY ?s ?g LIMIT {limit + 1} OFFSET {offset}
    """,
    )
    has_more = len(page) > limit
    page = page[:limit]
    if not page:
        return {"items": [], "has_more": has_more}
    pairs = (
        "VALUES (?g ?s) { "
        + " ".join(
            f"({sparql_iri(str(r['g']))} {sparql_iri(str(r['s']))})" for r in page
        )
        + " }"
    )
    items: dict[tuple[str, str], dict[str, Any]] = {
        (str(r["g"]), str(r["s"])): {
            "uri": str(r["s"]),
            "graph_uri": str(r["g"]),
            "label": "",
            "class_uri": "",
            "class_label": "",
            "properties": {},
            "domain_relations_count": 0,
            "range_relations_count": 0,
            "properties_count": 0,
        }
        for r in page
    }
    types: dict[tuple[str, str], set[str]] = {}
    # Seeds already passed the instance predicate. Separate types and labels so
    # OPTIONAL joins cannot multiply every type/label row before VALUES is applied.
    for row in rows(
        store,
        f"""
      SELECT ?g ?s ?type ?label WHERE {{
        {pairs} GRAPH ?g {{
          {{ ?s a ?type . FILTER(isIRI(?type)) }}
          UNION {{ ?s rdfs:label ?label . FILTER(isLiteral(?label)) }}
        }}
      }}
    """,
    ):
        key = str(row["g"]), str(row["s"])
        if row.get("type"):
            types.setdefault(key, set()).add(str(row["type"]))
        if row.get("label"):
            label = str(row["label"])
            if not items[key]["label"] or label < items[key]["label"]:
                items[key]["label"] = label
    for key, item in items.items():
        candidates = types.get(key, set()) - {NAMED}
        preferred = candidates & set(class_uris)
        item["class_uri"] = min(preferred or candidates or {NAMED})
        item["class_label"] = local_name(item["class_uri"])
    class_values = " ".join(
        map(sparql_iri, sorted({i["class_uri"] for i in items.values()}))
    )
    for row in rows(
        store,
        f"""
      SELECT ?cls (MIN(STR(?rawLabel)) AS ?label) WHERE {{
        VALUES ?cls {{ {class_values} }} {values(sorted(set(graphs + [schema_uri])))}
        GRAPH ?g {{ ?cls rdfs:label ?rawLabel }}
      }} GROUP BY ?cls
    """,
    ):
        for item in items.values():
            if item["class_uri"] == str(row["cls"]):
                item["class_label"] = str(row["label"])
    if include_counts:
        for row in rows(
            store,
            f"""
          SELECT ?g ?s (SUM(IF(isIRI(?o) && ?p != rdf:type, 1, 0)) AS ?outgoing)
          WHERE {{ {pairs} GRAPH ?g {{ ?s ?p ?o }} }} GROUP BY ?g ?s
        """,
        ):
            item = items[str(row["g"]), str(row["s"])]
            item["domain_relations_count"] = int(row["outgoing"])
        for row in rows(
            store,
            f"""
          SELECT ?g ?s (COUNT(DISTINCT ?p) AS ?properties)
          WHERE {{ {pairs} GRAPH ?g {{ ?s ?p ?o . FILTER(isLiteral(?o)) }} }} GROUP BY ?g ?s
        """,
        ):
            items[str(row["g"]), str(row["s"])]["properties_count"] = int(
                row["properties"]
            )
        for row in rows(
            store,
            f"""
          SELECT ?g ?s (COUNT(*) AS ?incoming)
          WHERE {{ {pairs} GRAPH ?g {{ ?other ?p ?s . FILTER(?p != rdf:type) }} }} GROUP BY ?g ?s
        """,
        ):
            items[str(row["g"]), str(row["s"])]["range_relations_count"] = int(
                row["incoming"]
            )
    return {"items": list(items.values()), "has_more": has_more}


def network(
    store: QueryStore,
    graphs: list[str],
    class_uris: list[str],
    search: str,
    offset: int,
    limit: int,
    schema_uri: str,
    relation_limit: int = 200,
) -> dict[str, Any]:
    """One page of instances and their immediate relationships, retaining graph provenance."""
    page = instances(
        store,
        graphs,
        class_uris,
        search,
        offset,
        limit,
        schema_uri,
        include_counts=False,
    )
    result = {**page, "neighbors": [], "relations": [], "relations_truncated": False}
    if not page["items"]:
        return result
    seeds = (
        "VALUES (?g ?seed) { "
        + " ".join(
            f"({sparql_iri(item['graph_uri'])} {sparql_iri(item['uri'])})"
            for item in page["items"]
        )
        + " }"
    )
    relations = rows(
        store,
        f"""
        SELECT DISTINCT ?g ?s ?p ?o WHERE {{
            {seeds}
            GRAPH ?g {{
                {{ ?seed ?p ?o . BIND(?seed AS ?s) }}
                UNION {{ ?s ?p ?seed . BIND(?seed AS ?o) }}
                FILTER(isIRI(?s) && isIRI(?o) && ?p != rdf:type)
            }}
        }} ORDER BY ?g ?s ?p ?o LIMIT {relation_limit + 1}
    """,
    )
    result["relations_truncated"] = len(relations) > relation_limit
    relations = relations[:relation_limit]
    seed_keys = {(item["graph_uri"], item["uri"]) for item in page["items"]}
    neighbors = {
        (str(row["g"]), str(row[side])) for row in relations for side in ("s", "o")
    } - seed_keys
    resources: dict[tuple[str, str], dict[str, str]] = {
        (graph, uri): {
            "graph_uri": graph,
            "uri": uri,
            "label": local_name(uri),
            "class_uri": "",
            "class_label": "",
        }
        for graph, uri in sorted(neighbors)
    }
    if resources:
        pairs = (
            "VALUES (?g ?s) { "
            + " ".join(f"({sparql_iri(g)} {sparql_iri(s)})" for g, s in resources)
            + " }"
        )
        neighbor_labels: dict[tuple[str, str], str] = {}
        for row in rows(
            store,
            f"""
            SELECT ?g ?s ?label ?type WHERE {{ {pairs} GRAPH ?g {{
                {{ ?s rdfs:label ?label . FILTER(isLiteral(?label) && STRLEN(STR(?label)) > 0) }}
                UNION {{ ?s a ?type . FILTER(isIRI(?type) && ?type != owl:NamedIndividual) }}
            }} }}
        """,
        ):
            key = str(row["g"]), str(row["s"])
            item = resources[key]
            if row.get("label"):
                label = str(row["label"])
                neighbor_labels[key] = min(neighbor_labels.get(key, label), label)
                item["label"] = neighbor_labels[key]
            if row.get("type"):
                kind = str(row["type"])
                item["class_uri"] = min(item["class_uri"] or kind, kind)
                item["class_label"] = local_name(item["class_uri"])
    predicates = {str(row["p"]) for row in relations}
    names: dict[str, str] = {}
    if predicates:
        for row in rows(
            store,
            f"""
            SELECT ?p (MIN(STR(?rawLabel)) AS ?label) WHERE {{
                VALUES ?p {{ {" ".join(map(sparql_iri, sorted(predicates)))} }}
                {values(sorted(set(graphs + [schema_uri])))}
                GRAPH ?g {{ ?p rdfs:label ?rawLabel }}
            }} GROUP BY ?p
        """,
        ):
            names[str(row["p"])] = str(row["label"])
    result["neighbors"] = list(resources.values())
    result["relations"] = [
        {
            "graph_uri": str(row["g"]),
            "source": str(row["s"]),
            "target": str(row["o"]),
            "predicate": str(row["p"]),
            "label": names.get(str(row["p"]), local_name(str(row["p"]))),
        }
        for row in relations
    ]
    return result
