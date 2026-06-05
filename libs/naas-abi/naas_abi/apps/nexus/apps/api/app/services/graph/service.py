from __future__ import annotations

import asyncio
import hashlib
import re
import unicodedata
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    DiscoveryClassData,
    DiscoveryDataProperty,
    DiscoveryInspectorRelation,
    DiscoveryInstanceData,
    DiscoveryInstanceDetailData,
    DiscoveryPropertyData,
    DiscoveryRelationRowData,
    DiscoveryRelationTypeData,
    GraphAnalysisData,
    GraphEdgeData,
    GraphInfoData,
    GraphKpisData,
    GraphNetworkData,
    GraphNodeData,
    GraphOverviewData,
    GraphPackData,
    GraphProtectedError,
    GraphServiceUnavailableError,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import KnowledgeGraph
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.query import ResultRow

_cache = CacheFactory.CacheFS_find_storage(subpath="nexus/graph")

GRAPH_BASE_URI = URIRef(
    ABIModule.get_instance().configuration.nexus_config.ontology_base_uri + "graph/"
)
NEXUS_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus")
SCHEMA_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/schema")

_PROTECTED_URIS = {SCHEMA_GRAPH_URI, NEXUS_GRAPH_URI}

_OWL_TYPE_MAP: dict[str, str] = {
    str(OWL.NamedIndividual): "named_individual",
    str(OWL.Class): "class",
    str(OWL.ObjectProperty): "object_property",
    str(OWL.DatatypeProperty): "datatype_property",
    str(OWL.Restriction): "restriction",
}
_TYPE_PRIORITY: dict[str, int] = {
    "named_individual": 5,
    "class": 4,
    "object_property": 3,
    "datatype_property": 3,
    "restriction": 2,
    "unknown": 0,
}


def _detect_rdf_format(filename: str) -> str:
    fname = filename.lower()
    if fname.endswith(".ttl"):
        return "turtle"
    if fname.endswith(".owl") or fname.endswith(".rdf"):
        return "xml"
    if fname.endswith(".nt"):
        return "nt"
    if fname.endswith(".n3"):
        return "n3"
    if fname.endswith(".jsonld") or fname.endswith(".json"):
        return "json-ld"
    return "turtle"


_BFO_BUCKET_ROOTS_VALUES = " ".join(
    f"<http://purl.obolibrary.org/obo/{bfo_id}>"
    for bfo_id in (
        "BFO_0000040",  # Material Entity (WHO)
        "BFO_0000015",  # Process (WHAT)
        "BFO_0000008",  # Temporal Region (WHEN)
        "BFO_0000029",  # Site (WHERE)
        "BFO_0000031",  # Generically Dependent Continuant (HOW WE KNOW)
        "BFO_0000019",  # Quality (HOW IT IS)
        "BFO_0000017",  # Realizable (WHY)
    )
)


def _escape_sparql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w\s-]", "", ascii_value).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned)


@_cache(
    lambda triple_store, uri: f"ontology_label_{uri}",
    DataType.JSON,
    ttl=timedelta(days=1),
)
def _get_ontology_label(triple_store: TripleStoreService, uri: str) -> str:
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?label
    WHERE {{
        GRAPH <http://ontology.naas.ai/graph/schema> {{
            <{uri}> rdfs:label ?label .
        }}
    }}
    """
    for row in triple_store.query(query):
        assert isinstance(row, ResultRow)
        return str(row.label) if row.label else uri.split("/")[-1].split("#")[-1]
    return uri.split("/")[-1].split("#")[-1]


@_cache(
    lambda triple_store, class_uri: f"bfo_parent_{class_uri}",
    DataType.JSON,
    ttl=timedelta(days=1),
)
def _get_bfo_parent_for_class(triple_store: TripleStoreService, class_uri: str) -> str | None:
    """Walk rdfs:subClassOf+ in the schema graph to find the nearest BFO bucket-root ancestor."""
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?ancestor WHERE {{
        GRAPH <http://ontology.naas.ai/graph/schema> {{
            VALUES ?ancestor {{ {_BFO_BUCKET_ROOTS_VALUES} }}
            <{class_uri}> rdfs:subClassOf+ ?ancestor .
        }}
    }}
    LIMIT 1
    """
    for row in triple_store.query(query):
        assert isinstance(row, ResultRow)
        val = getattr(row, "ancestor", None)
        return str(val) if val else None
    return None


def _uri_fragment(uri: str) -> str:
    if not uri:
        return ""
    return uri.split("/")[-1].split("#")[-1]


@_cache(
    lambda triple_store, uri: f"property_kind_{uri}",
    DataType.JSON,
    ttl=timedelta(days=1),
)
def _classify_property(triple_store: TripleStoreService, uri: str) -> str:
    """Return 'datatype' for owl:DatatypeProperty, 'annotation' for owl:AnnotationProperty.

    Falls back to 'datatype' if the property is not declared in the schema graph.
    """
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?type WHERE {{
        GRAPH <http://ontology.naas.ai/graph/schema> {{
            <{uri}> rdf:type ?type .
            FILTER(?type IN (owl:DatatypeProperty, owl:AnnotationProperty))
        }}
    }}
    LIMIT 1
    """
    for row in triple_store.query(query):
        assert isinstance(row, ResultRow)
        type_str = str(row.type)
        if type_str.endswith("AnnotationProperty"):
            return "annotation"
        return "datatype"
    return "datatype"


def _fetch_property_values(
    triple_store: TripleStoreService,
    graph_uri: str,
    subject_uris: list[str],
    property_uris: list[str],
) -> dict[str, dict[str, str]]:
    """Fetch literal property values for subjects, grouped by subject and property."""
    if not subject_uris or not property_uris:
        return {}
    subj_values = " ".join(f"<{uri}>" for uri in subject_uris)
    pred_values = " ".join(f"<{uri}>" for uri in property_uris)
    query = f"""
    SELECT ?s ?p ?o WHERE {{
        GRAPH <{graph_uri}> {{
            VALUES ?s {{ {subj_values} }}
            VALUES ?p {{ {pred_values} }}
            ?s ?p ?o .
            FILTER(isLiteral(?o))
        }}
    }}
    """
    out: dict[str, dict[str, str]] = {}
    for row in triple_store.query(query):
        assert isinstance(row, ResultRow)
        s_uri = str(row.s)
        p_uri = str(row.p)
        value = str(row.o)
        bucket = out.setdefault(s_uri, {})
        # Keep first-seen value (idempotent) — fine for most labels & identifiers
        bucket.setdefault(p_uri, value)
    return out


def _fetch_relation_counts(
    triple_store: TripleStoreService,
    graph_uri: str,
    subject_uris: list[str],
) -> dict[str, int]:
    """Count object-property edges per subject in *graph_uri*.

    For each subject, returns the number of triples ``?s ?p ?o`` where
    ``?p != rdf:type`` and ``?o`` is an IRI — i.e. the outgoing
    relations count visible in Table 2.
    """
    if not subject_uris:
        return {}
    subj_values = " ".join(f"<{uri}>" for uri in subject_uris)
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT ?s (COUNT(*) AS ?total) WHERE {{
        VALUES ?g {{ <{graph_uri}> }}
        GRAPH ?g {{
            VALUES ?s {{ {subj_values} }}
            ?s ?p ?o .
            FILTER(?p != rdf:type)
            FILTER(isIRI(?o))
        }}
    }}
    GROUP BY ?s
    """
    counts: dict[str, int] = {}
    try:
        for row in triple_store.query(query):
            if not isinstance(row, ResultRow):
                continue
            s_value = getattr(row, "s", None)
            total_value = getattr(row, "total", None)
            if s_value is None or total_value is None:
                continue
            try:
                counts[str(s_value)] = int(total_value)
            except (ValueError, TypeError):
                continue
    except Exception:
        return {}
    return counts


def _fetch_data_property_counts(
    triple_store: TripleStoreService,
    graph_uri: str,
    subject_uris: list[str],
) -> dict[str, int]:
    """Count datatype-property assertions per subject (triples where o is a Literal)."""
    if not subject_uris:
        return {}
    subj_values = " ".join(f"<{uri}>" for uri in subject_uris)
    query = f"""
    SELECT ?s (COUNT(*) AS ?total) WHERE {{
        VALUES ?g {{ <{graph_uri}> }}
        GRAPH ?g {{
            VALUES ?s {{ {subj_values} }}
            ?s ?p ?o .
            FILTER(isLiteral(?o))
        }}
    }}
    GROUP BY ?s
    """
    counts: dict[str, int] = {}
    try:
        for row in triple_store.query(query):
            if not isinstance(row, ResultRow):
                continue
            s_value = getattr(row, "s", None)
            total_value = getattr(row, "total", None)
            if s_value is None or total_value is None:
                continue
            try:
                counts[str(s_value)] = int(total_value)
            except (ValueError, TypeError):
                continue
    except Exception:
        return {}
    return counts


def _fetch_object_property_values(
    triple_store: TripleStoreService,
    graph_uri: str,
    subject_uris: list[str],
) -> dict[str, dict[str, dict[str, str]]]:
    """Fetch IRI-valued property values involving subject_uris as subject or object.

    Covers both outgoing (?s in subject_uris → ?o) and incoming (?s → ?o in subject_uris)
    relations between owl:NamedIndividuals.

    Returns dict[uri][predicate_uri] = {"uri": str, "label": str}
    """
    if not subject_uris:
        return {}
    subj_values = " ".join(f"<{uri}>" for uri in subject_uris)
    out: dict[str, dict[str, dict[str, str]]] = {}

    outgoing_query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?s ?p ?o ?oLabel WHERE {{
        GRAPH <{graph_uri}> {{
            VALUES ?s {{ {subj_values} }}
            ?s ?p ?o .
            ?o a owl:NamedIndividual .
            FILTER(isIRI(?o))
            FILTER(?p != rdf:type)
            OPTIONAL {{ ?o rdfs:label ?oLabel . }}
        }}
    }}
    """
    try:
        for row in triple_store.query(outgoing_query):
            if not isinstance(row, ResultRow):
                continue
            s_uri = str(row.s)
            p_uri = str(row.p)
            o_uri = str(row.o)
            o_label_val = getattr(row, "oLabel", None)
            o_label = str(o_label_val) if o_label_val else _uri_fragment(o_uri)
            out.setdefault(s_uri, {}).setdefault(p_uri, {"uri": o_uri, "label": o_label})
    except Exception:
        return out

    incoming_query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?s ?p ?o ?sLabel WHERE {{
        GRAPH <{graph_uri}> {{
            VALUES ?o {{ {subj_values} }}
            ?s ?p ?o .
            ?s a owl:NamedIndividual .
            FILTER(isIRI(?s))
            FILTER(?p != rdf:type)
            OPTIONAL {{ ?s rdfs:label ?sLabel . }}
        }}
    }}
    """
    try:
        for row in triple_store.query(incoming_query):
            if not isinstance(row, ResultRow):
                continue
            s_uri = str(row.s)
            p_uri = str(row.p)
            o_uri = str(row.o)
            s_label_val = getattr(row, "sLabel", None)
            s_label = str(s_label_val) if s_label_val else _uri_fragment(s_uri)
            out.setdefault(o_uri, {}).setdefault(p_uri, {"uri": s_uri, "label": s_label})
    except Exception:
        pass

    return out


def _fetch_range_relation_counts(
    triple_store: TripleStoreService,
    graph_uri: str,
    object_uris: list[str],
) -> dict[str, int]:
    """Count incoming object-property edges per instance (triples where ?o is the instance)."""
    if not object_uris:
        return {}
    obj_values = " ".join(f"<{uri}>" for uri in object_uris)
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT ?o (COUNT(*) AS ?total) WHERE {{
        VALUES ?g {{ <{graph_uri}> }}
        GRAPH ?g {{
            VALUES ?o {{ {obj_values} }}
            ?s ?p ?o .
            FILTER(?p != rdf:type)
            FILTER(isIRI(?s))
        }}
    }}
    GROUP BY ?o
    """
    counts: dict[str, int] = {}
    try:
        for row in triple_store.query(query):
            if not isinstance(row, ResultRow):
                continue
            o_value = getattr(row, "o", None)
            total_value = getattr(row, "total", None)
            if o_value is None or total_value is None:
                continue
            try:
                counts[str(o_value)] = int(total_value)
            except (ValueError, TypeError):
                continue
    except Exception:
        return {}
    return counts


def _get_subjects_graph_batch(
    triple_store: TripleStoreService,
    subject_uris: list[str],
    graph_names: list[str],
    depth: int = 2,
) -> Graph:
    """Fetch all triples for a batch of subjects in a single CONSTRUCT query.

    Equivalent to calling SPARQLUtils.get_subject_graph once per URI, but in one
    round-trip to the triple store. With depth=2 also follows IRI objects to
    pull their labels/types.
    """
    graph = Graph()
    if not subject_uris or depth <= 0:
        return graph

    values_subjects = " ".join(f"<{u}>" for u in subject_uris)
    values_graphs = " ".join(f"<{g}>" for g in graph_names)

    construct_clauses: list[str] = []
    where_clauses: list[str] = []
    for i in range(depth):
        if i == 0:
            construct_clauses.append("?s ?p0 ?o0 .")
            where_clauses.append("?s ?p0 ?o0 .")
        else:
            construct_clauses.append(f"?o{i - 1} ?p{i} ?o{i} .")
            where_clauses.append(f"OPTIONAL {{ ?o{i - 1} ?p{i} ?o{i} . FILTER(isIRI(?o{i - 1})) }}")

    sparql = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    CONSTRUCT {{ {" ".join(construct_clauses)} }}
    WHERE {{
        VALUES ?s {{ {values_subjects} }}
        VALUES ?g {{ {values_graphs} }}
        GRAPH ?g {{
            {" ".join(where_clauses)}
        }}
    }}
    """
    for triple in triple_store.query(sparql):
        graph.add(triple)  # type: ignore[arg-type]
    return graph


def _build_network_from_subject_graph(
    triple_store: TripleStoreService,
    workspace_id: str,
    subject_graph: Graph,
    limit: int,
) -> GraphNetworkData:
    """Walk a pre-fetched subject graph and build the GraphNetworkData payload.

    Replaces the per-row inner loop that previously triggered N+1 SPARQL
    queries — assumes all triples needed for nodes/edges are already in
    ``subject_graph``.
    """
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    for s, p, o in subject_graph:
        subject_uri = str(s)
        subject_label_value = subject_graph.value(URIRef(subject_uri), RDFS.label)
        subject_label = str(subject_label_value) if subject_label_value else subject_uri
        subject_types = list(subject_graph.objects(URIRef(subject_uri), RDF.type))
        if OWL.NamedIndividual not in subject_types:
            continue
        if o == OWL.NamedIndividual or p == RDFS.label:
            continue
        if subject_uri not in nodes:
            nodes[subject_uri] = {"uri": subject_uri, "label": subject_label}
        if "type" not in nodes[subject_uri]:
            class_type = next(
                (
                    str(subject_type)
                    for subject_type in subject_types
                    if subject_type not in {OWL.NamedIndividual, OWL.Class}
                ),
                None,
            )
            if class_type:
                nodes[subject_uri]["type"] = class_type
                nodes[subject_uri]["type_label"] = _get_ontology_label(triple_store, class_type)
                bfo_parent = _get_bfo_parent_for_class(triple_store, class_type)
                nodes[subject_uri]["bfo_parent_iri"] = bfo_parent or ""
        if isinstance(o, Literal):
            nodes[subject_uri][_get_ontology_label(triple_store, str(p))] = str(o)
        elif isinstance(o, URIRef) and p != RDF.type:
            object_uri = str(o)
            edge_id = hashlib.sha256(f"{subject_uri}|{str(p)}|{object_uri}".encode()).hexdigest()
            if edge_id not in edges:
                object_label_value = subject_graph.value(URIRef(object_uri), RDFS.label)
                object_label = str(object_label_value) if object_label_value else object_uri
                edges[edge_id] = {
                    "id": edge_id,
                    "label": _get_ontology_label(triple_store, str(p)),
                    "source_id": subject_uri,
                    "source_label": subject_label,
                    "target_id": object_uri,
                    "target_label": object_label,
                }

    graph_nodes: list[GraphNodeData] = []
    graph_edges: list[GraphEdgeData] = []

    for node_data in list(nodes.values())[: int(limit)]:
        node_id = str(node_data.get("uri", "") or "").strip()
        if not node_id:
            continue
        _excluded = {"uri", "label", "type", "type_label"}
        graph_nodes.append(
            GraphNodeData(
                id=node_id,
                workspace_id=workspace_id,
                type=str(node_data.get("type_label") or node_data.get("type") or "unknown"),
                label=str(node_data.get("label") or node_id),
                properties={
                    key.split("/")[-1]: value
                    for key, value in node_data.items()
                    if key not in _excluded and (value != "unknown" or key == "bfo_parent_iri")
                },
            )
        )

    for edge_data in list(edges.values())[: int(limit)]:
        source_id = str(edge_data.get("source_id", "") or "").strip()
        target_id = str(edge_data.get("target_id", "") or "").strip()
        if not source_id or not target_id:
            continue
        graph_edges.append(
            GraphEdgeData(
                id=str(
                    edge_data.get("id") or f"{source_id}|{edge_data.get('label', '')}|{target_id}"
                ),
                workspace_id=workspace_id,
                source_id=source_id,
                target_id=target_id,
                source_label=str(edge_data.get("source_label") or source_id),
                target_label=str(edge_data.get("target_label") or target_id),
                type=str(edge_data.get("label") or "related"),
                properties={},
            )
        )

    return GraphNetworkData(nodes=graph_nodes, edges=graph_edges)


# @_cache(
#     lambda triple_store, workspace_id, graph_names, graph_filters: (
#         f"list_individuals_{str(triple_store)}_{workspace_id}_{str(graph_names)}_{str(graph_filters)}"
#     ),
#     DataType.PICKLE,
#     ttl=timedelta(days=1),
# )
def _list_individuals(
    triple_store: TripleStoreService,
    workspace_id: str,
    graph_names: list[str],
    graph_filters: list[dict[str, str | None]],
    limit: int = 200,
    depth: int = 2,
) -> GraphNetworkData:
    values = " ".join(f"<{name}>" for name in graph_names)
    filter_clauses: list[str] = []
    for filter_item in graph_filters:
        parts: list[str] = []
        subject_uri = filter_item.get("subject_uri")
        predicate_uri = filter_item.get("predicate_uri")
        object_uri = filter_item.get("object_uri")
        if subject_uri:
            parts.append(f"?s = <{subject_uri}>")
        if predicate_uri:
            parts.append(f"?p = <{predicate_uri}>")
        if object_uri:
            parts.append(f"?o = <{object_uri}>")
        if parts:
            filter_clauses.append(f"({' && '.join(parts)})")
    triple_filter_clause = f"FILTER({' || '.join(filter_clauses)})" if filter_clauses else ""

    query = f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT DISTINCT ?uri
    WHERE {{
        VALUES ?g {{ {values} }}
        GRAPH ?g {{
            ?s ?p ?o .
            ?s a owl:NamedIndividual ;
            FILTER(?s != owl:NamedIndividual)
            {triple_filter_clause}
            BIND(?s AS ?uri)
        }}
    }}
    LIMIT {int(limit)}
    """
    subject_uris = [str(row.uri) for row in triple_store.query(query) if isinstance(row, ResultRow)]
    subject_graph = _get_subjects_graph_batch(
        triple_store=triple_store,
        subject_uris=subject_uris,
        graph_names=graph_names,
        depth=depth,
    )
    return _build_network_from_subject_graph(
        triple_store=triple_store,
        workspace_id=workspace_id,
        subject_graph=subject_graph,
        limit=limit,
    )


def _search_individuals(
    triple_store: TripleStoreService,
    workspace_id: str,
    graph_names: list[str],
    search_query: str,
    limit: int = 200,
    depth: int = 2,
) -> GraphNetworkData:
    values = " ".join(f"<{name}>" for name in graph_names)
    escaped = _escape_sparql_string(search_query)

    query = f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?uri
    WHERE {{
        VALUES ?g {{ {values} }}
        GRAPH ?g {{
            ?s a owl:NamedIndividual ;
               rdfs:label ?label .
            FILTER(CONTAINS(LCASE(STR(?label)), "{escaped}"))
            BIND(?s AS ?uri)
        }}
    }}
    LIMIT {int(limit)}
    """
    subject_uris = [str(row.uri) for row in triple_store.query(query) if isinstance(row, ResultRow)]
    subject_graph = _get_subjects_graph_batch(
        triple_store=triple_store,
        subject_uris=subject_uris,
        graph_names=graph_names,
        depth=depth,
    )
    return _build_network_from_subject_graph(
        triple_store=triple_store,
        workspace_id=workspace_id,
        subject_graph=subject_graph,
        limit=limit,
    )


def _build_graph_overview(
    triple_store: TripleStoreService, graph_uri: URIRef, limit: int = 500
) -> GraphOverviewData:
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?uri ?label ?type
    WHERE {{
        GRAPH <{str(graph_uri)}> {{
            ?uri a owl:NamedIndividual ;
                 rdfs:label ?label ;
                 rdf:type ?type .
            FILTER(?type != owl:NamedIndividual)
        }}
    }}
    LIMIT {int(limit)}
    """
    rows = triple_store.query(query)
    nodes: list[dict[str, Any]] = []
    class_dict: dict[str, str] = {}
    type_counts: dict[str, int] = {}
    for row in rows:
        assert isinstance(row, ResultRow)
        class_uri = str(row.type)
        class_label = class_dict.get(class_uri)
        if not class_label:
            class_label = _get_ontology_label(triple_store, class_uri)
            class_dict[class_uri] = class_label
        type_counts[class_label] = type_counts.get(class_label, 0) + 1
        nodes.append(
            {
                "uri": str(row.uri),
                "label": str(row.label),
                "type": str(row.type),
                "type_label": class_label,
            }
        )

    node_uris = [node["uri"] for node in nodes]
    edges: list[dict[str, Any]] = []
    if node_uris:
        values_clause = " ".join(f"<{uri}>" for uri in node_uris)
        query_edges = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?s ?p ?o
        WHERE {{
            GRAPH <{str(graph_uri)}> {{
                VALUES ?s {{ {values_clause} }}
                ?s ?p ?o .
                FILTER(?p != rdf:type && isIRI(?o))
            }}
        }}
        """
        for row_edge in triple_store.query(query_edges):
            assert isinstance(row_edge, ResultRow)
            edges.append({"s": str(row_edge.s), "p": str(row_edge.p), "o": str(row_edge.o)})

    count_query = f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT (COUNT(DISTINCT ?uri) AS ?total)
    WHERE {{
        GRAPH <{str(graph_uri)}> {{
            ?uri a owl:NamedIndividual .
        }}
    }}
    """
    count_rows = list(triple_store.query(count_query))
    total_instances = (
        int(count_rows[0].total)
        if count_rows and isinstance(count_rows[0], ResultRow)
        else len(nodes)
    )

    kpis: dict[str, Any] = {
        "total_instances": total_instances,
        "total_relationships": len(edges),
        "average_degree": (2 * len(edges) / len(nodes)) if nodes else 0,
        "density": (len(edges) / (len(nodes) * (len(nodes) - 1))) if len(nodes) > 1 else 0,
    }
    instances_by_class = [
        {"type": node_type, "count": count}
        for node_type, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return GraphOverviewData(kpis=kpis, instances_by_class=instances_by_class)


@_cache(
    lambda triple_store, graph_uri: f"graph_kpis_{graph_uri}",
    DataType.JSON,
    ttl=timedelta(minutes=5),
)
def _get_graph_kpis(triple_store: TripleStoreService, graph_uri: str) -> dict[str, int]:
    def _count(sparql: str) -> int:
        try:
            for row in triple_store.query(sparql):
                if not isinstance(row, ResultRow):
                    continue
                val = getattr(row, "total", None)
                return int(val) if val is not None else 0
        except Exception:
            pass
        return 0

    individuals = _count(f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT (COUNT(DISTINCT ?s) AS ?total)
    WHERE {{
        GRAPH <{graph_uri}> {{
            ?s a owl:NamedIndividual .
        }}
    }}
    """)

    relations = _count(f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT (COUNT(*) AS ?total)
    WHERE {{
        GRAPH <{graph_uri}> {{
            ?s ?p ?o .
            FILTER(?p != rdf:type)
            FILTER(isIRI(?o))
        }}
    }}
    """)

    properties = _count(f"""
    SELECT (COUNT(*) AS ?total)
    WHERE {{
        GRAPH <{graph_uri}> {{
            ?s ?p ?o .
            FILTER(isLiteral(?o))
        }}
    }}
    """)

    return {"individuals": individuals, "relations": relations, "properties": properties}


class GraphService:
    def __init__(
        self,
        triple_store_getter: Callable[[], TripleStoreService] | None = None,
    ) -> None:
        self._triple_store_getter = triple_store_getter

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_triple_store(self) -> TripleStoreService:
        if self._triple_store_getter is not None:
            return self._triple_store_getter()
        try:
            from naas_abi import ABIModule

            return ABIModule.get_instance().engine.services.triple_store
        except Exception as exc:
            raise GraphServiceUnavailableError(
                "Triple store is not initialized. Load API through naas_abi.ABIModule."
            ) from exc

    # ── Public API ────────────────────────────────────────────────────────────

    async def list_graphs(self, workspace_id: str) -> list[GraphPackData]:
        store = self._get_triple_store()
        query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX nexus: <http://ontology.naas.ai/nexus/>
        SELECT DISTINCT ?uri ?label ?role_label
        WHERE {{
            GRAPH <{NEXUS_GRAPH_URI}> {{
                ?uri rdf:type <{KnowledgeGraph._class_uri}> .
                OPTIONAL {{ ?uri rdfs:label ?label . }}
                OPTIONAL {{
                    ?uri nexus:hasKnowledgeGraphRole ?role_uri .
                    ?role_uri rdfs:label ?role_label .
                }}
            }}
        }}
        """
        role_graphs: dict[str, list[GraphInfoData]] = {}
        for row in store.query(query):
            assert isinstance(row, ResultRow)
            graph_uri = str(row.uri)
            graph_id = graph_uri.split("/")[-1]
            graph_label = str(row.label) if row.label else graph_id
            role_label = (
                str(row.role_label).strip().lower() if row.role_label is not None else "unknown"
            ) or "unknown"
            role_graphs.setdefault(role_label, []).append(
                GraphInfoData(
                    id=graph_id,
                    uri=graph_uri,
                    label=graph_label,
                    role_label=role_label,
                )
            )

        packed_graphs: list[GraphPackData] = []
        for role_label in sorted(role_graphs):
            graphs = sorted(role_graphs[role_label], key=lambda graph: graph.label.lower())
            packed_graphs.append(GraphPackData(role_label=role_label, graphs=graphs))
        return packed_graphs

    async def create_graph(
        self,
        workspace_id: str,
        label: str,
        description: str | None,
        user_id: str,
    ) -> GraphInfoData:
        store = self._get_triple_store()
        graph_label = label.strip()
        graph_id = _slugify(graph_label)
        new_graph_uri = GRAPH_BASE_URI + graph_id
        store.create_graph(new_graph_uri)
        new_graph = KnowledgeGraph(_uri=new_graph_uri, label=graph_label, creator=user_id)
        if description:
            new_graph.description = _slugify(description)
        store.insert(new_graph.rdf(), graph_name=NEXUS_GRAPH_URI)
        return GraphInfoData(id=graph_id, uri=str(new_graph_uri), label=graph_label)

    async def clear_graph(self, workspace_id: str, graph_uri: str) -> None:
        uri = URIRef(graph_uri)
        if uri in _PROTECTED_URIS:
            raise GraphProtectedError("Schema or Nexus graph cannot be cleared.")
        self._get_triple_store().clear_graph(uri)

    def _remove_subject_and_object_triples(
        self,
        store: TripleStoreService,
        uri: URIRef,
        named_graph: URIRef,
    ) -> None:
        """Remove every triple in *named_graph* where *uri* appears as subject or object."""
        triples = Graph()
        forward_query = f"""
        SELECT ?p ?o
        WHERE {{
            GRAPH <{named_graph}> {{
                <{uri}> ?p ?o .
            }}
        }}
        """
        for row in store.query(forward_query):
            assert isinstance(row, ResultRow)
            triples.add((uri, row.p, row.o))
        inverse_query = f"""
        SELECT ?s ?p
        WHERE {{
            GRAPH <{named_graph}> {{
                ?s ?p <{uri}> .
            }}
        }}
        """
        for row in store.query(inverse_query):
            assert isinstance(row, ResultRow)
            triples.add((row.s, row.p, uri))
        if len(triples) > 0:
            store.remove(triples, graph_name=named_graph)

    async def delete_graph(self, workspace_id: str, graph_uri: str) -> None:
        uri = URIRef(graph_uri)
        if uri in _PROTECTED_URIS:
            raise GraphProtectedError("Schema or Nexus graph cannot be deleted.")
        store = self._get_triple_store()
        store.drop_graph(uri)
        self._remove_subject_and_object_triples(store, uri, NEXUS_GRAPH_URI)

    async def create_individual(
        self,
        workspace_id: str,
        graph_uri: str,
        label: str,
        class_uri: str | None,
    ) -> GraphNodeData:
        normalized_label = label.strip()
        if not normalized_label:
            raise ValueError("Individual label must not be empty.")
        target_graph = URIRef(graph_uri)
        if target_graph in _PROTECTED_URIS:
            raise GraphProtectedError(
                "Individuals cannot be inserted into the Schema or Nexus graph."
            )
        store = self._get_triple_store()
        slug = _slugify(normalized_label) or "individual"
        suffix = uuid.uuid4().hex[:12]
        individual_uri = URIRef(f"{graph_uri.rstrip('/')}/{slug}-{suffix}")
        triples = Graph()
        triples.add((individual_uri, RDF.type, OWL.NamedIndividual))
        if class_uri:
            triples.add((individual_uri, RDF.type, URIRef(class_uri)))
        triples.add((individual_uri, RDFS.label, Literal(normalized_label)))
        store.insert(triples, graph_name=target_graph)
        type_label = _get_ontology_label(store, class_uri) if class_uri else "owl:NamedIndividual"
        return GraphNodeData(
            id=str(individual_uri),
            workspace_id=workspace_id,
            type=type_label,
            label=normalized_label,
            properties={},
        )

    async def delete_individual(
        self,
        workspace_id: str,
        graph_uri: str,
        individual_uri: str,
    ) -> None:
        target_graph = URIRef(graph_uri)
        if target_graph in _PROTECTED_URIS:
            raise GraphProtectedError(
                "Individuals cannot be deleted from the Schema or Nexus graph."
            )
        store = self._get_triple_store()
        self._remove_subject_and_object_triples(
            store=store,
            uri=URIRef(individual_uri),
            named_graph=target_graph,
        )

    async def get_graph_kpis(self, workspace_id: str, graph_uri: str) -> GraphKpisData:
        store = self._get_triple_store()
        result = await asyncio.to_thread(_get_graph_kpis, triple_store=store, graph_uri=graph_uri)
        return GraphKpisData(
            individuals=result["individuals"],
            relations=result["relations"],
            properties=result["properties"],
        )

    async def get_graph_overview(
        self, workspace_id: str, graph_uri: str, limit: int = 500
    ) -> GraphOverviewData:
        store = self._get_triple_store()
        return await asyncio.to_thread(
            _build_graph_overview, triple_store=store, graph_uri=URIRef(graph_uri), limit=limit
        )

    async def get_graph_network(
        self, workspace_id: str, graph_uri: str, limit: int = 200
    ) -> GraphNetworkData:
        store = self._get_triple_store()
        return await asyncio.to_thread(
            _list_individuals,
            triple_store=store,
            workspace_id=workspace_id,
            graph_names=[graph_uri],
            graph_filters=[],
            limit=limit,
            depth=2,
        )

    async def list_individuals(
        self,
        workspace_id: str,
        graph_names: list[str],
        graph_filters: list[dict[str, str | None]],
        limit: int = 200,
        depth: int = 2,
    ) -> GraphNetworkData:
        return await asyncio.to_thread(
            _list_individuals,
            triple_store=self._get_triple_store(),
            workspace_id=workspace_id,
            graph_names=graph_names,
            graph_filters=graph_filters,
            limit=limit,
            depth=depth,
        )

    async def search_network(
        self,
        workspace_id: str,
        graph_uri: str,
        search_query: str,
        limit: int = 200,
    ) -> GraphNetworkData:
        return await asyncio.to_thread(
            _search_individuals,
            triple_store=self._get_triple_store(),
            workspace_id=workspace_id,
            graph_names=[graph_uri],
            search_query=search_query,
            limit=limit,
            depth=2,
        )

    async def export_graph_as_ttl(
        self,
        workspace_id: str,
        graph_uri: str,
        batch_size: int = 10000,
        format: str = "turtle",
    ) -> tuple[str, int]:
        """Export all triples from *graph_uri* as Turtle with bound namespaces.

        Fetches triples in batches of *batch_size*, incrementing OFFSET until
        fewer than *batch_size* triples are returned (end of graph).

        Returns (ttl_content, total_triple_count).
        """
        store = self._get_triple_store()
        g = Graph()
        g.bind("rdf", RDF)
        g.bind("rdfs", RDFS)
        g.bind("owl", OWL)
        g.bind("xsd", XSD)
        g.bind("bfo", Namespace("http://purl.obolibrary.org/obo/"))

        try:
            base_uri = ABIModule.get_instance().configuration.nexus_config.ontology_base_uri
            g.bind("abi", Namespace(base_uri))
        except Exception:
            pass

        total_count = 0
        offset = 0

        while True:
            query = f"""
            CONSTRUCT {{ ?s ?p ?o }}
            WHERE {{
                GRAPH <{graph_uri}> {{
                    ?s ?p ?o .
                }}
            }}
            LIMIT {int(batch_size)}
            OFFSET {int(offset)}
            """
            result = store.query(query)
            batch_count = 0
            if isinstance(result, Graph):
                for triple in result:
                    g.add(triple)  # type: ignore[arg-type]
                    batch_count += 1
            else:
                for triple in result:
                    g.add(triple)  # type: ignore[arg-type]
                    batch_count += 1

            total_count += batch_count
            if batch_count < batch_size:
                break
            offset += batch_size

        return g.serialize(format=format), total_count

    async def analyze_graph_file(
        self,
        content: bytes,
        fmt: str,
    ) -> GraphAnalysisData:
        """Parse *content* as an RDF file and count subjects + triples per OWL type category.

        Each subject is assigned to exactly one category based on its highest-priority
        rdf:type (NamedIndividual > Class > Object/DatatypeProperty > Restriction > Unknown).
        The sum of all per-category triple counts equals total_triples; likewise for subjects.
        """
        g = Graph()
        g.parse(data=content, format=fmt)

        # First pass: determine each subject's primary OWL category from rdf:type triples
        subject_category: dict[str, str] = {}
        for s, p, o in g:
            if p == RDF.type:
                s_str = str(s)
                new_cat = _OWL_TYPE_MAP.get(str(o), "unknown")
                current = subject_category.get(s_str, "unknown")
                if _TYPE_PRIORITY.get(new_cat, 0) > _TYPE_PRIORITY.get(current, 0):
                    subject_category[s_str] = new_cat

        # Second pass: accumulate triples and collect unique subject sets per category
        _cats = (
            "named_individual",
            "class",
            "object_property",
            "datatype_property",
            "restriction",
            "unknown",
        )
        triple_counts: dict[str, int] = dict.fromkeys(_cats, 0)
        subject_sets: dict[str, set[str]] = {c: set() for c in _cats}

        for s, _p, _o in g:
            cat = subject_category.get(str(s), "unknown")
            triple_counts[cat] += 1
            subject_sets[cat].add(str(s))

        return GraphAnalysisData(
            total_triples=len(g),
            total_subjects=sum(len(v) for v in subject_sets.values()),
            named_individuals_subjects=len(subject_sets["named_individual"]),
            named_individuals_triples=triple_counts["named_individual"],
            classes_subjects=len(subject_sets["class"]),
            classes_triples=triple_counts["class"],
            object_properties_subjects=len(subject_sets["object_property"]),
            object_properties_triples=triple_counts["object_property"],
            datatype_properties_subjects=len(subject_sets["datatype_property"]),
            datatype_properties_triples=triple_counts["datatype_property"],
            restrictions_subjects=len(subject_sets["restriction"]),
            restrictions_triples=triple_counts["restriction"],
            unknown_subjects=len(subject_sets["unknown"]),
            unknown_triples=triple_counts["unknown"],
        )

    async def import_individuals_to_graph(
        self,
        workspace_id: str,
        content: bytes,
        fmt: str,
        graph_uri: str,
    ) -> int:
        """Parse *content* and insert all OWL NamedIndividual triples into *graph_uri*.

        Returns the number of triples inserted.
        """
        g = Graph()
        g.parse(data=content, format=fmt)

        individual_subjects: set[URIRef] = set()
        for s, p, o in g:
            if p == RDF.type and o == OWL.NamedIndividual and isinstance(s, URIRef):
                individual_subjects.add(s)

        individual_graph = Graph()
        for s, p, o in g:
            if isinstance(s, URIRef) and s in individual_subjects:
                individual_graph.add((s, p, o))

        store = self._get_triple_store()
        store.insert(individual_graph, graph_name=URIRef(graph_uri))
        return len(individual_graph)

    async def get_network_parents(
        self,
        workspace_id: str,
        graph_names: list[str],
        node_iris: list[str],
    ) -> GraphNetworkData:
        """Return parent class nodes for the given frontier node IRIs.

        For each IRI the endpoint detects whether it is an individual or a class:
        - Individual (owl:NamedIndividual in data graph) → returns its rdf:type class + rdf:type edge.
        - Class (owl:Class in schema graph) → returns its rdfs:subClassOf parents + edges.

        One call per progressive level; the frontend advances the frontier.
        """
        if not node_iris:
            return GraphNetworkData(nodes=[], edges=[])
        return await asyncio.to_thread(
            self._get_network_parents_sync, workspace_id, graph_names, node_iris
        )

    def _get_network_parents_sync(
        self,
        workspace_id: str,
        graph_names: list[str],
        node_iris: list[str],
    ) -> GraphNetworkData:
        store = self._get_triple_store()

        iris_values = " ".join(f"<{iri}>" for iri in node_iris)
        graph_values = " ".join(f"<{name}>" for name in graph_names)

        new_nodes: dict[str, GraphNodeData] = {}
        new_edges: dict[str, GraphEdgeData] = {}

        # ── Case 1: individuals → fetch rdf:type from data graphs ────────────
        if graph_values:
            type_query = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?individual ?classType WHERE {{
                VALUES ?individual {{ {iris_values} }}
                VALUES ?g {{ {graph_values} }}
                GRAPH ?g {{
                    ?individual rdf:type ?classType .
                    FILTER(?classType != owl:NamedIndividual)
                    FILTER(isIRI(?classType))
                }}
            }}
            """
            individual_label_cache: dict[str, str] = {}
            for row in store.query(type_query):
                assert isinstance(row, ResultRow)
                ind_iri = str(row.individual)
                cls_iri = str(row.classType)

                # Class node
                if cls_iri not in new_nodes:
                    cls_label = _get_ontology_label(store, cls_iri)
                    bfo_parent = _get_bfo_parent_for_class(store, cls_iri)
                    new_nodes[cls_iri] = GraphNodeData(
                        id=cls_iri,
                        workspace_id=workspace_id,
                        type="Class",
                        label=cls_label,
                        properties={"bfo_parent_iri": bfo_parent or "", "is_class": True},
                    )

                # rdf:type edge: individual → class
                edge_id = f"{ind_iri}|rdf_type|{cls_iri}"
                if edge_id not in new_edges:
                    ind_label = individual_label_cache.get(ind_iri)
                    if ind_label is None:
                        ind_label = _get_ontology_label(store, ind_iri)
                        individual_label_cache[ind_iri] = ind_label
                    new_edges[edge_id] = GraphEdgeData(
                        id=edge_id,
                        workspace_id=workspace_id,
                        source_id=ind_iri,
                        target_id=cls_iri,
                        source_label=ind_label,
                        target_label=new_nodes[cls_iri].label,
                        type="rdf:type",
                        properties={"relation_kind": "is_a"},
                    )

        # ── Case 2: classes → fetch rdfs:subClassOf from schema graph ─────────
        parent_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?subClass ?superClass WHERE {{
            GRAPH <{SCHEMA_GRAPH_URI}> {{
                VALUES ?subClass {{ {iris_values} }}
                ?subClass rdfs:subClassOf ?superClass .
                FILTER(isIRI(?superClass))
            }}
        }}
        """
        for row in store.query(parent_query):
            assert isinstance(row, ResultRow)
            sub_iri = str(row.subClass) if row.subClass else None
            super_iri = str(row.superClass) if row.superClass else None
            if not sub_iri or not super_iri:
                continue

            for iri in (sub_iri, super_iri):
                if iri not in new_nodes:
                    lbl = _get_ontology_label(store, iri)
                    bfo_parent = _get_bfo_parent_for_class(store, iri)
                    new_nodes[iri] = GraphNodeData(
                        id=iri,
                        workspace_id=workspace_id,
                        type="Class",
                        label=lbl,
                        properties={"bfo_parent_iri": bfo_parent or "", "is_class": True},
                    )

            edge_id = f"{sub_iri}|is_a|{super_iri}"
            if edge_id not in new_edges:
                new_edges[edge_id] = GraphEdgeData(
                    id=edge_id,
                    workspace_id=workspace_id,
                    source_id=sub_iri,
                    target_id=super_iri,
                    source_label=new_nodes[sub_iri].label,
                    target_label=new_nodes[super_iri].label,
                    type="is a",
                    properties={"relation_kind": "is_a"},
                )

        return GraphNetworkData(nodes=list(new_nodes.values()), edges=list(new_edges.values()))

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def discover_classes(self, workspace_id: str, graph_uri: str) -> list[DiscoveryClassData]:
        return await asyncio.to_thread(self._discover_classes_sync, workspace_id, graph_uri)

    def _discover_classes_sync(self, workspace_id: str, graph_uri: str) -> list[DiscoveryClassData]:
        store = self._get_triple_store()
        query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?cls (COUNT(DISTINCT ?s) AS ?total)
        WHERE {{
            VALUES ?g {{ <{graph_uri}> }}
            GRAPH ?g {{
                ?s rdf:type ?cls .
            }}
            FILTER(?cls != owl:NamedIndividual)
            FILTER(?cls != owl:Class)
            FILTER(?cls != rdfs:Class)
            FILTER(isIRI(?cls))
        }}
        GROUP BY ?cls
        ORDER BY DESC(?total)
        """
        counts: dict[str, int] = {}
        try:
            for row in store.query(query):
                if not isinstance(row, ResultRow):
                    continue
                cls_value = getattr(row, "cls", None)
                if cls_value is None:
                    continue
                class_uri = str(cls_value)
                if not class_uri:
                    continue
                total_value = getattr(row, "total", None)
                try:
                    count = int(total_value) if total_value is not None else 0
                except (ValueError, TypeError):
                    count = 0
                counts[class_uri] = counts.get(class_uri, 0) + count
        except Exception:
            counts = {}

        # Fallback: if no aggregated rows, scan distinct types directly.
        if not counts:
            distinct_query = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?cls ?s
            WHERE {{
                VALUES ?g {{ <{graph_uri}> }}
                GRAPH ?g {{
                    ?s rdf:type ?cls .
                }}
                FILTER(?cls != owl:NamedIndividual)
                FILTER(isIRI(?cls))
            }}
            """
            try:
                for row in store.query(distinct_query):
                    if not isinstance(row, ResultRow):
                        continue
                    cls_value = getattr(row, "cls", None)
                    if cls_value is None:
                        continue
                    class_uri = str(cls_value)
                    if not class_uri:
                        continue
                    counts[class_uri] = counts.get(class_uri, 0) + 1
            except Exception:
                pass

        results: list[DiscoveryClassData] = []
        for class_uri, count in counts.items():
            try:
                label = _get_ontology_label(store, class_uri)
            except Exception:
                label = ""
            if not label or label == class_uri:
                label = _uri_fragment(class_uri) or class_uri
            results.append(DiscoveryClassData(uri=class_uri, label=label, count=count))
        results.sort(key=lambda d: (-d.count, d.label.lower()))
        return results

    async def discover_properties(
        self,
        workspace_id: str,
        graph_uri: str,
        class_uris: list[str],
    ) -> list[DiscoveryPropertyData]:
        return await asyncio.to_thread(
            self._discover_properties_sync, workspace_id, graph_uri, class_uris
        )

    def _discover_properties_sync(
        self,
        workspace_id: str,
        graph_uri: str,
        class_uris: list[str],
    ) -> list[DiscoveryPropertyData]:
        store = self._get_triple_store()
        if class_uris:
            values = " ".join(f"<{uri}>" for uri in class_uris)
            class_filter = f"VALUES ?cls {{ {values} }} ?s rdf:type ?cls ."
        else:
            class_filter = "?s rdf:type ?cls . FILTER(?cls != owl:NamedIndividual && isIRI(?cls))"
        query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?p WHERE {{
            VALUES ?g {{ <{graph_uri}> }}
            GRAPH ?g {{
                {class_filter}
                ?s ?p ?o .
                FILTER(isLiteral(?o))
                FILTER(?p != rdf:type)
            }}
        }}
        """
        prop_uris: list[str] = []
        try:
            for row in store.query(query):
                if not isinstance(row, ResultRow):
                    continue
                p_value = getattr(row, "p", None)
                if p_value is None:
                    continue
                p_uri = str(p_value)
                if p_uri:
                    prop_uris.append(p_uri)
        except Exception:
            prop_uris = []

        # Always include rdfs:label and skos:prefLabel as canonical defaults
        for canonical in (
            "http://www.w3.org/2000/01/rdf-schema#label",
            "http://www.w3.org/2004/02/skos/core#prefLabel",
        ):
            if canonical not in prop_uris:
                prop_uris.append(canonical)

        results: list[DiscoveryPropertyData] = []
        seen: set[str] = set()
        for uri in prop_uris:
            if uri in seen:
                continue
            seen.add(uri)
            label = _get_ontology_label(store, uri)
            kind = _classify_property(store, uri)
            results.append(DiscoveryPropertyData(uri=uri, label=label, kind=kind))
        results.sort(key=lambda d: d.label.lower())
        return results

    async def discover_instances(
        self,
        workspace_id: str,
        graph_uri: str,
        class_uris: list[str],
        property_uris: list[str],
        search: str,
        limit: int | None = None,
    ) -> list[DiscoveryInstanceData]:
        return await asyncio.to_thread(
            self._discover_instances_sync,
            workspace_id,
            graph_uri,
            class_uris,
            property_uris,
            search,
            limit,
        )

    def _discover_instances_sync(
        self,
        workspace_id: str,
        graph_uri: str,
        class_uris: list[str],
        property_uris: list[str],
        search: str,
        limit: int | None,
    ) -> list[DiscoveryInstanceData]:
        store = self._get_triple_store()

        if class_uris:
            values = " ".join(f"<{uri}>" for uri in class_uris)
            class_filter = f"VALUES ?cls {{ {values} }} ?s rdf:type ?cls ."
        else:
            class_filter = "?s rdf:type ?cls ."

        search_clause = ""
        if search and search.strip():
            escaped = _escape_sparql_string(search.strip().lower())
            search_props = property_uris or ["http://www.w3.org/2000/01/rdf-schema#label"]
            search_values = " ".join(f"<{uri}>" for uri in search_props)
            search_clause = f"""
            {{
                ?s ?searchProp ?searchVal .
                VALUES ?searchProp {{ {search_values} }}
                FILTER(CONTAINS(LCASE(STR(?searchVal)), "{escaped}"))
            }}
            """

        limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""
        query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?s ?cls WHERE {{
            VALUES ?g {{ <{graph_uri}> }}
            GRAPH ?g {{
                {class_filter}
                FILTER(isIRI(?cls))
                FILTER(?cls != owl:NamedIndividual)
                FILTER(isIRI(?s))
                {search_clause}
            }}
        }}
        {limit_clause}
        """

        instances: list[tuple[str, str]] = []
        seen_subjects: set[str] = set()
        try:
            for row in store.query(query):
                if not isinstance(row, ResultRow):
                    continue
                subject_value = getattr(row, "s", None)
                cls_value = getattr(row, "cls", None)
                if subject_value is None or cls_value is None:
                    continue
                subject_uri = str(subject_value)
                if not subject_uri or subject_uri in seen_subjects:
                    continue
                seen_subjects.add(subject_uri)
                instances.append((subject_uri, str(cls_value)))
        except Exception:
            instances = []

        if not instances:
            return []

        subject_uris = [s for s, _c in instances]
        prop_values = _fetch_property_values(
            store,
            graph_uri,
            subject_uris,
            property_uris or ["http://www.w3.org/2000/01/rdf-schema#label"],
        )
        object_prop_values = _fetch_object_property_values(store, graph_uri, subject_uris)
        domain_counts = _fetch_relation_counts(store, graph_uri, subject_uris)
        range_counts = _fetch_range_relation_counts(store, graph_uri, subject_uris)
        data_property_counts = _fetch_data_property_counts(store, graph_uri, subject_uris)

        results: list[DiscoveryInstanceData] = []
        for subject_uri, class_uri in instances:
            class_label = _get_ontology_label(store, class_uri) or _uri_fragment(class_uri)
            label_value = prop_values.get(subject_uri, {}).get(
                "http://www.w3.org/2000/01/rdf-schema#label"
            )
            label = label_value or _uri_fragment(subject_uri)
            bfo_bucket_uri = _get_bfo_parent_for_class(store, class_uri) or ""
            bfo_bucket_label = (
                _get_ontology_label(store, bfo_bucket_uri) or _uri_fragment(bfo_bucket_uri)
                if bfo_bucket_uri
                else ""
            )
            results.append(
                DiscoveryInstanceData(
                    uri=subject_uri,
                    label=label,
                    class_uri=class_uri,
                    class_label=class_label,
                    properties=prop_values.get(subject_uri, {}),
                    object_properties=object_prop_values.get(subject_uri, {}),
                    domain_relations_count=domain_counts.get(subject_uri, 0),
                    range_relations_count=range_counts.get(subject_uri, 0),
                    properties_count=data_property_counts.get(subject_uri, 0),
                    bfo_bucket_uri=bfo_bucket_uri,
                    bfo_bucket_label=bfo_bucket_label,
                )
            )
        results.sort(key=lambda d: d.label.lower())
        return results

    async def discover_instance_detail(
        self,
        workspace_id: str,
        graph_uri: str,
        instance_uri: str,
    ) -> DiscoveryInstanceDetailData:
        return await asyncio.to_thread(
            self._discover_instance_detail_sync, workspace_id, graph_uri, instance_uri
        )

    def _discover_instance_detail_sync(
        self,
        workspace_id: str,
        graph_uri: str,
        instance_uri: str,
    ) -> DiscoveryInstanceDetailData:
        store = self._get_triple_store()

        # Label and class
        label = _get_ontology_label(store, instance_uri) or _uri_fragment(instance_uri)
        class_uri = ""
        class_label = ""
        class_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?cls WHERE {{
            VALUES ?g {{ <{graph_uri}> }}
            GRAPH ?g {{
                <{instance_uri}> rdf:type ?cls .
                FILTER(isIRI(?cls))
                FILTER(?cls != owl:NamedIndividual)
            }}
        }}
        LIMIT 1
        """
        try:
            for row in store.query(class_query):
                if not isinstance(row, ResultRow):
                    continue
                cls = getattr(row, "cls", None)
                if cls:
                    class_uri = str(cls)
                    class_label = _get_ontology_label(store, class_uri) or _uri_fragment(class_uri)
                    break
        except Exception:
            pass

        # All literal (data) properties — fetch predicate labels inline
        data_properties: list[DiscoveryDataProperty] = []
        dp_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?p ?pLabel ?o WHERE {{
            VALUES ?g {{ <{graph_uri}> }}
            GRAPH ?g {{
                <{instance_uri}> ?p ?o .
                FILTER(isLiteral(?o))
            }}
            OPTIONAL {{ ?p rdfs:label ?pLabel . }}
        }}
        ORDER BY ?p
        """
        try:
            for row in store.query(dp_query):
                if not isinstance(row, ResultRow):
                    continue
                p = getattr(row, "p", None)
                o = getattr(row, "o", None)
                if p is None or o is None:
                    continue
                pred_uri = str(p)
                p_label_val = getattr(row, "pLabel", None)
                pred_label = (
                    str(p_label_val) if p_label_val is not None else _uri_fragment(pred_uri)
                )
                data_properties.append(
                    DiscoveryDataProperty(
                        predicate_uri=pred_uri,
                        predicate_label=pred_label,
                        value=str(o),
                    )
                )
        except Exception:
            pass

        # Outgoing relations (instance is domain/subject)
        inspector_relations: list[DiscoveryInspectorRelation] = []
        out_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?p ?pLabel ?o ?oLabel WHERE {{
            VALUES ?g {{ <{graph_uri}> }}
            GRAPH ?g {{
                <{instance_uri}> ?p ?o .
                FILTER(?p != rdf:type)
                FILTER(isIRI(?o))
            }}
            OPTIONAL {{ ?p rdfs:label ?pLabel . }}
            OPTIONAL {{ ?o rdfs:label ?oLabel . }}
        }}
        """
        try:
            for row in store.query(out_query):
                if not isinstance(row, ResultRow):
                    continue
                p = getattr(row, "p", None)
                o = getattr(row, "o", None)
                if p is None or o is None:
                    continue
                pred_uri = str(p)
                other_uri = str(o)
                p_label_val = getattr(row, "pLabel", None)
                o_label_val = getattr(row, "oLabel", None)
                inspector_relations.append(
                    DiscoveryInspectorRelation(
                        role="domain",
                        predicate_uri=pred_uri,
                        predicate_label=str(p_label_val)
                        if p_label_val is not None
                        else _uri_fragment(pred_uri),
                        other_uri=other_uri,
                        other_label=str(o_label_val)
                        if o_label_val is not None
                        else _uri_fragment(other_uri),
                    )
                )
        except Exception:
            pass

        # Incoming relations (instance is range/object)
        in_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?s ?sLabel ?p ?pLabel WHERE {{
            VALUES ?g {{ <{graph_uri}> }}
            GRAPH ?g {{
                ?s ?p <{instance_uri}> .
                FILTER(?p != rdf:type)
                FILTER(isIRI(?s))
            }}
            OPTIONAL {{ ?p rdfs:label ?pLabel . }}
            OPTIONAL {{ ?s rdfs:label ?sLabel . }}
        }}
        """
        try:
            for row in store.query(in_query):
                if not isinstance(row, ResultRow):
                    continue
                s = getattr(row, "s", None)
                p = getattr(row, "p", None)
                if s is None or p is None:
                    continue
                pred_uri = str(p)
                other_uri = str(s)
                p_label_val = getattr(row, "pLabel", None)
                s_label_val = getattr(row, "sLabel", None)
                inspector_relations.append(
                    DiscoveryInspectorRelation(
                        role="range",
                        predicate_uri=pred_uri,
                        predicate_label=str(p_label_val)
                        if p_label_val is not None
                        else _uri_fragment(pred_uri),
                        other_uri=other_uri,
                        other_label=str(s_label_val)
                        if s_label_val is not None
                        else _uri_fragment(other_uri),
                    )
                )
        except Exception:
            pass

        return DiscoveryInstanceDetailData(
            uri=instance_uri,
            label=label,
            class_uri=class_uri,
            class_label=class_label,
            data_properties=data_properties,
            relations=inspector_relations,
        )

    async def discover_relation_types(
        self,
        workspace_id: str,
        graph_uri: str,
        instance_uris: list[str],
    ) -> list[DiscoveryRelationTypeData]:
        return await asyncio.to_thread(
            self._discover_relation_types_sync, workspace_id, graph_uri, instance_uris
        )

    def _discover_relation_types_sync(
        self,
        workspace_id: str,
        graph_uri: str,
        instance_uris: list[str],
    ) -> list[DiscoveryRelationTypeData]:
        if not instance_uris:
            return []
        store = self._get_triple_store()
        values = " ".join(f"<{uri}>" for uri in instance_uris)
        counts: dict[str, int] = {}

        # Count each (?s ?p ?o) triple once even when both ends are in the
        # working set (domain + range queries would otherwise double-count).
        try:
            for row in store.query(f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?p (COUNT(*) AS ?total)
            WHERE {{
                {{
                    SELECT DISTINCT ?s ?p ?o WHERE {{
                        VALUES ?g {{ <{graph_uri}> }}
                        GRAPH ?g {{
                            {{
                                VALUES ?s {{ {values} }}
                                ?s ?p ?o .
                                ?o a owl:NamedIndividual .
                            }}
                            UNION
                            {{
                                VALUES ?o {{ {values} }}
                                ?s ?p ?o .
                                ?s a owl:NamedIndividual .
                            }}
                        }}
                        FILTER(?p != rdf:type)
                    }}
                }}
            }}
            GROUP BY ?p
            """):
                if not isinstance(row, ResultRow):
                    continue
                p_value = getattr(row, "p", None)
                if p_value is None:
                    continue
                total_value = getattr(row, "total", None)
                try:
                    counts[str(p_value)] = int(total_value) if total_value is not None else 0
                except (ValueError, TypeError):
                    continue
        except Exception:
            pass

        # Fallback: if aggregation returned nothing, scan distinct predicates.
        if not counts:
            try:
                for row in store.query(f"""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                SELECT DISTINCT ?p WHERE {{
                    {{
                        SELECT DISTINCT ?s ?p ?o WHERE {{
                            VALUES ?g {{ <{graph_uri}> }}
                            GRAPH ?g {{
                                {{
                                    VALUES ?s {{ {values} }}
                                    ?s ?p ?o .
                                    ?o a owl:NamedIndividual .
                                }}
                                UNION
                                {{
                                    VALUES ?o {{ {values} }}
                                    ?s ?p ?o .
                                    ?s a owl:NamedIndividual .
                                }}
                            }}
                            FILTER(?p != rdf:type)
                        }}
                    }}
                }}
                """):
                    if not isinstance(row, ResultRow):
                        continue
                    p_value = getattr(row, "p", None)
                    if p_value is None:
                        continue
                    counts[str(p_value)] = counts.get(str(p_value), 0) + 1
            except Exception:
                pass

        results: list[DiscoveryRelationTypeData] = []
        for uri, count in counts.items():
            try:
                label = _get_ontology_label(store, uri)
            except Exception:
                label = ""
            if not label or label == uri:
                label = _uri_fragment(uri) or uri
            results.append(DiscoveryRelationTypeData(uri=uri, label=label, count=count))
        results.sort(key=lambda d: (-d.count, d.label.lower()))
        return results

    async def discover_relations(
        self,
        workspace_id: str,
        graph_uri: str,
        instance_uris: list[str],
        relation_uris: list[str],
        limit: int | None = None,
    ) -> list[DiscoveryRelationRowData]:
        return await asyncio.to_thread(
            self._discover_relations_sync,
            workspace_id,
            graph_uri,
            instance_uris,
            relation_uris,
            limit,
        )

    def _discover_relations_sync(
        self,
        workspace_id: str,
        graph_uri: str,
        instance_uris: list[str],
        relation_uris: list[str],
        limit: int | None,
    ) -> list[DiscoveryRelationRowData]:
        if not instance_uris:
            return []
        store = self._get_triple_store()
        inst_values = " ".join(f"<{uri}>" for uri in instance_uris)
        pred_clause = ""
        if relation_uris:
            pred_values = " ".join(f"<{uri}>" for uri in relation_uris)
            pred_clause = f"VALUES ?p {{ {pred_values} }}"

        rel_limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""

        def _build_rel_query(inst_constraint: str, iri_filter: str, other_ni_constraint: str) -> str:
            return f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?s ?p ?o ?sLabel ?oLabel ?sClass ?oClass
            WHERE {{
                VALUES ?g {{ <{graph_uri}> }}
                GRAPH ?g {{
                    {inst_constraint}
                    {other_ni_constraint}
                    {pred_clause}
                    ?s ?p ?o .
                    OPTIONAL {{ ?s rdfs:label ?sLabel . }}
                    OPTIONAL {{ ?o rdfs:label ?oLabel . }}
                    OPTIONAL {{
                        ?s rdf:type ?sClass .
                        FILTER(?sClass != owl:NamedIndividual && isIRI(?sClass))
                    }}
                    OPTIONAL {{
                        ?o rdf:type ?oClass .
                        FILTER(?oClass != owl:NamedIndividual && isIRI(?oClass))
                    }}
                }}
                FILTER(?p != rdf:type)
                FILTER({iri_filter})
            }}
            {rel_limit_clause}
            """

        domain_query = _build_rel_query(f"VALUES ?s {{ {inst_values} }}", "isIRI(?o)", "?o a owl:NamedIndividual .")
        range_query = _build_rel_query(f"VALUES ?o {{ {inst_values} }}", "isIRI(?s)", "?s a owl:NamedIndividual .")

        rows: list[DiscoveryRelationRowData] = []
        # (role, domain_uri, relation_uri, range_uri) to deduplicate within each role
        seen: set[tuple[str, str, str, str]] = set()

        def _build_row(result_row: ResultRow, role: str) -> DiscoveryRelationRowData | None:
            s_value = getattr(result_row, "s", None)
            p_value = getattr(result_row, "p", None)
            o_value = getattr(result_row, "o", None)
            if s_value is None or p_value is None or o_value is None:
                return None
            domain_uri = str(s_value)
            relation_uri = str(p_value)
            range_uri = str(o_value)
            key = (role, domain_uri, relation_uri, range_uri)
            if key in seen:
                return None
            seen.add(key)
            s_label_val = getattr(result_row, "sLabel", None)
            o_label_val = getattr(result_row, "oLabel", None)
            domain_label = str(s_label_val) if s_label_val else _uri_fragment(domain_uri)
            range_label = str(o_label_val) if o_label_val else _uri_fragment(range_uri)
            try:
                relation_label = _get_ontology_label(store, relation_uri)
            except Exception:
                relation_label = ""
            if not relation_label or relation_label == relation_uri:
                relation_label = _uri_fragment(relation_uri) or relation_uri
            s_class_val = getattr(result_row, "sClass", None)
            o_class_val = getattr(result_row, "oClass", None)
            domain_class_uri = str(s_class_val) if s_class_val else ""
            range_class_uri = str(o_class_val) if o_class_val else ""
            domain_class_label = ""
            if domain_class_uri:
                try:
                    domain_class_label = _get_ontology_label(store, domain_class_uri)
                except Exception:
                    domain_class_label = ""
            range_class_label = ""
            if range_class_uri:
                try:
                    range_class_label = _get_ontology_label(store, range_class_uri)
                except Exception:
                    range_class_label = ""
            return DiscoveryRelationRowData(
                relation_uri=relation_uri,
                relation_label=relation_label,
                domain_uri=domain_uri,
                domain_label=domain_label,
                domain_class_uri=domain_class_uri,
                domain_class_label=domain_class_label or _uri_fragment(domain_class_uri),
                range_uri=range_uri,
                range_label=range_label,
                range_class_uri=range_class_uri,
                range_class_label=range_class_label or _uri_fragment(range_class_uri),
                role=role,
            )

        for sparql, role in ((domain_query, "domain"), (range_query, "range")):
            try:
                result_iter = list(store.query(sparql))
            except Exception:
                result_iter = []
            for r in result_iter:
                if not isinstance(r, ResultRow):
                    continue
                built = _build_row(r, role)
                if built is not None:
                    rows.append(built)

        return rows
