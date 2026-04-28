from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphEdgeData,
    GraphInfoData,
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
from naas_abi_core.utils.SPARQL import SPARQLUtils
from rdflib import OWL, RDF, RDFS, Literal, URIRef
from rdflib.query import ResultRow

_cache = CacheFactory.CacheFS_find_storage(subpath="nexus/graph")

GRAPH_BASE_URI = URIRef("http://ontology.naas.ai/graph/")
NEXUS_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus")
SCHEMA_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/schema")

_PROTECTED_URIS = {SCHEMA_GRAPH_URI, NEXUS_GRAPH_URI}


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w\s-]", "", ascii_value).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned)


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
        return str(row.label) if row.label else uri
    return uri


@_cache(
    lambda triple_store, workspace_id, graph_names, graph_filters: (
        f"list_individuals_{str(triple_store)}_{workspace_id}_{str(graph_names)}_{str(graph_filters)}"
    ),
    DataType.PICKLE,
    ttl=timedelta(days=1),
)
def _list_individuals(
    triple_store: TripleStoreService,
    workspace_id: str,
    graph_names: list[str],
    graph_filters: list[dict[str, str | None]],
    limit: int = 500,
    depth: int = 2,
) -> GraphNetworkData:
    sparql_utils = SPARQLUtils(triple_store)
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
    """
    rows = triple_store.query(query)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    for row in rows:
        assert isinstance(row, ResultRow)
        row_uri = str(row.uri)
        subject_graph = sparql_utils.get_subject_graph(
            row_uri, depth=depth, graph_names=graph_names
        )
        for s, p, o in subject_graph:
            subject_uri = str(s)
            subject_label = (
                subject_graph.value(URIRef(subject_uri), RDFS.label)
                if subject_graph.value(URIRef(subject_uri), RDFS.label)
                else subject_uri
            )
            subject_types = list(subject_graph.objects(URIRef(subject_uri), RDF.type))
            if OWL.NamedIndividual not in subject_types:
                continue
            if o == OWL.NamedIndividual or p == RDFS.label:
                continue
            if subject_uri not in nodes:
                nodes[subject_uri] = {"uri": subject_uri, "label": str(subject_label)}
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
            if isinstance(o, Literal):
                nodes[subject_uri][_get_ontology_label(triple_store, str(p))] = str(o)
            elif isinstance(o, URIRef) and p != RDF.type:
                object_uri = str(o)
                edge_id = hashlib.sha256(
                    f"{subject_uri}|{str(p)}|{object_uri}".encode()
                ).hexdigest()
                if edge_id not in edges:
                    object_label = (
                        subject_graph.value(URIRef(object_uri), RDFS.label)
                        if subject_graph.value(URIRef(object_uri), RDFS.label)
                        else object_uri
                    )
                    edges[edge_id] = {
                        "id": edge_id,
                        "label": _get_ontology_label(triple_store, str(p)),
                        "source_id": subject_uri,
                        "source_label": str(subject_label),
                        "target_id": object_uri,
                        "target_label": str(object_label),
                    }

    graph_nodes: list[GraphNodeData] = []
    graph_edges: list[GraphEdgeData] = []

    for node_data in list(nodes.values())[: int(limit)]:
        node_id = str(node_data.get("uri", "") or "").strip()
        if not node_id:
            continue
        graph_nodes.append(
            GraphNodeData(
                id=node_id,
                workspace_id=workspace_id,
                type=str(node_data.get("type_label") or node_data.get("type") or "unknown"),
                label=str(node_data.get("label") or node_id),
                properties={
                    key.split("/")[-1]: value
                    for key, value in node_data.items()
                    if key not in {"uri", "label", "type", "type_label"} and value != "unknown"
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

    kpis: dict[str, Any] = {
        "total_instances": len(nodes),
        "total_relationships": len(edges),
        "average_degree": (2 * len(edges) / len(nodes)) if nodes else 0,
        "density": (len(edges) / (len(nodes) * (len(nodes) - 1))) if len(nodes) > 1 else 0,
    }
    instances_by_class = [
        {"type": node_type, "count": count}
        for node_type, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return GraphOverviewData(kpis=kpis, instances_by_class=instances_by_class)


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

    async def clear_graph(self, workspace_id: str, graph_id: str) -> None:
        graph_uri = GRAPH_BASE_URI + graph_id
        if graph_uri in _PROTECTED_URIS:
            raise GraphProtectedError("Schema or Nexus graph cannot be cleared.")
        self._get_triple_store().clear_graph(graph_uri)

    async def delete_graph(self, workspace_id: str, graph_id: str) -> None:
        graph_uri = GRAPH_BASE_URI + graph_id
        if graph_uri in _PROTECTED_URIS:
            raise GraphProtectedError("Schema or Nexus graph cannot be deleted.")
        self._get_triple_store().drop_graph(graph_uri)

    async def get_graph_overview(
        self, workspace_id: str, graph_id: str, limit: int = 500
    ) -> GraphOverviewData:
        store = self._get_triple_store()
        graph_uri = GRAPH_BASE_URI + graph_id
        return _build_graph_overview(triple_store=store, graph_uri=graph_uri, limit=limit)

    async def get_graph_network(
        self, workspace_id: str, graph_id: str, limit: int = 500
    ) -> GraphNetworkData:
        store = self._get_triple_store()
        graph_uri = str(GRAPH_BASE_URI + graph_id)
        return _list_individuals(
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
        limit: int = 500,
        depth: int = 2,
    ) -> GraphNetworkData:
        return _list_individuals(
            triple_store=self._get_triple_store(),
            workspace_id=workspace_id,
            graph_names=graph_names,
            graph_filters=graph_filters,
            limit=limit,
            depth=depth,
        )
