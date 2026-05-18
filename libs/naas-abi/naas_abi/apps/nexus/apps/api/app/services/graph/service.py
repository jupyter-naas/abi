from __future__ import annotations

import asyncio
import hashlib
import re
import unicodedata
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from naas_abi import ABIModule
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
from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef
from rdflib.query import ResultRow

_cache = CacheFactory.CacheFS_find_storage(subpath="nexus/graph")

GRAPH_BASE_URI = URIRef(
    ABIModule.get_instance().configuration.nexus_config.ontology_base_uri + "graph/"
)
NEXUS_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus")
SCHEMA_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/schema")

_PROTECTED_URIS = {SCHEMA_GRAPH_URI, NEXUS_GRAPH_URI}

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
        return str(row.label) if row.label else uri
    return uri


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
            where_clauses.append(
                f"OPTIONAL {{ ?o{i - 1} ?p{i} ?o{i} . FILTER(isIRI(?o{i - 1})) }}"
            )

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
            edge_id = hashlib.sha256(
                f"{subject_uri}|{str(p)}|{object_uri}".encode()
            ).hexdigest()
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
    total_instances = int(count_rows[0].total) if count_rows else len(nodes)  # type: ignore[attr-defined]

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

    async def delete_graph(self, workspace_id: str, graph_uri: str) -> None:
        uri = URIRef(graph_uri)
        if uri in _PROTECTED_URIS:
            raise GraphProtectedError("Schema or Nexus graph cannot be deleted.")
        self._get_triple_store().drop_graph(uri)

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
