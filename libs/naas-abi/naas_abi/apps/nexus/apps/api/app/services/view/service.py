from __future__ import annotations

from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.service import _list_individuals
from naas_abi.ontologies.modules.NexusPlatformOntology import GraphFilter, GraphView, KnowledgeGraph
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import OWL, RDF, RDFS, Graph, URIRef
from rdflib.query import ResultRow

NEXUS_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus")
GRAPH_BASE_URI = "http://ontology.naas.ai/graph/"


class ViewServiceUnavailableError(Exception):
    """Raised when the triple store service cannot be resolved."""


class ViewNotFoundError(Exception):
    """Raised when a view does not exist."""


def _normalize_filter_part(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() == "unknown":
        return None
    return normalized


def _resolve_graph_uri(graph_name: str) -> str:
    candidate = graph_name.strip()
    if not candidate:
        return ""
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate
    return f"{GRAPH_BASE_URI}{candidate}"


def _sparql_iri(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if any(char in candidate for char in ("<", ">", '"', "'", " ")):
        return None
    return f"<{candidate}>"


def _label_from_iri(iri: str) -> str:
    return iri.split("/")[-1].split("#")[-1]


def _format_typed_label(label: str, type_label: str | None) -> str:
    if type_label and type_label.strip():
        return f"{label} (type: {type_label.strip()})"
    return label


class ViewService:
    def __init__(
        self,
        triple_store_getter: Callable[[], TripleStoreService] | None = None,
    ) -> None:
        self._triple_store_getter = triple_store_getter

    def _get_triple_store(self) -> TripleStoreService:
        if self._triple_store_getter is not None:
            return self._triple_store_getter()
        try:
            from naas_abi import ABIModule

            return ABIModule.get_instance().engine.services.triple_store
        except Exception as exc:  # pragma: no cover - runtime safety
            raise ViewServiceUnavailableError(
                "Triple store is not initialized. Load API through naas_abi.ABIModule."
            ) from exc

    def _resolve_view_uri(self, view_id: str) -> URIRef | None:
        candidate = view_id.strip()
        if not candidate:
            return None
        if candidate.startswith("http://") or candidate.startswith("https://"):
            return URIRef(candidate)
        rows = self._get_triple_store().query(
            f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX nexus: <http://ontology.naas.ai/nexus/>
            SELECT ?uri
            WHERE {{
                GRAPH <{str(NEXUS_GRAPH_URI)}> {{
                    ?uri rdf:type nexus:GraphView .
                    FILTER(STR(?uri) = "{candidate}" || STRENDS(STR(?uri), "/{candidate}"))
                }}
            }}
            LIMIT 1
            """
        )
        for row in rows:
            assert isinstance(row, ResultRow)
            return URIRef(str(row.uri))
        return None

    def get_graph_filters(self, uris: list[str]) -> list[dict[str, Any]]:
        if not uris:
            return []

        values = " ".join(f"<{uri}>" for uri in uris if uri and uri.strip())
        values_clause = f"VALUES ?filter_uri {{ {values} }}" if values else ""
        store = self._get_triple_store()

        def _query(values_block: str = "") -> list[dict[str, Any]]:
            query = f"""
            PREFIX nexus: <http://ontology.naas.ai/nexus/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?filter_uri ?label ?s ?p ?o ?o_is_literal
            WHERE {{
                GRAPH <http://ontology.naas.ai/graph/nexus> {{
                    {values_block}
                    ?filter_uri rdf:type nexus:GraphFilter .
                    OPTIONAL {{ ?filter_uri rdfs:label ?label . }}
                    OPTIONAL {{ ?filter_uri nexus:subject_uri ?s . }}
                    OPTIONAL {{ ?filter_uri nexus:predicate_uri ?p . }}
                    OPTIONAL {{ ?filter_uri nexus:object_uri ?o . }}
                    OPTIONAL {{ ?filter_uri nexus:object_is_literal ?o_is_literal . }}
                }}
            }}
            """
            rows = store.query(query)

            filters: list[dict[str, Any]] = []
            for row in rows:
                assert isinstance(row, ResultRow)

                filter_uri = (
                    str(row.filter_uri)
                    if hasattr(row, "filter_uri") and row.filter_uri
                    else None
                )
                label = str(row.label) if hasattr(row, "label") and row.label else None
                s = _normalize_filter_part(str(row.s) if hasattr(row, "s") and row.s else None)
                p = _normalize_filter_part(str(row.p) if hasattr(row, "p") and row.p else None)
                o = _normalize_filter_part(str(row.o) if hasattr(row, "o") and row.o else None)

                o_is_literal = False
                if hasattr(row, "o_is_literal") and row.o_is_literal:
                    val = str(row.o_is_literal).lower()
                    o_is_literal = val in ["true", "1"]

                if s or p or o:
                    filters.append(
                        {
                            "uri": filter_uri,
                            "label": label,
                            "subject_uri": s,
                            "predicate_uri": p,
                            "object_uri": o,
                            "o_is_literal": o_is_literal,
                        }
                    )
            return filters

        filters = _query(values_clause)
        if filters:
            return filters
        return _query()

    async def list_graph_filter_options(
        self,
        graph_names: list[str] | None = None,
        subject_uri: str | None = None,
        predicate_uri: str | None = None,
        object_uri: str | None = None,
    ) -> dict[str, list[dict[str, str]]]:
        store = self._get_triple_store()
        graph_uris = [_resolve_graph_uri(name) for name in (graph_names or []) if name.strip()]
        if not graph_uris:
            graph_uris = [f"{GRAPH_BASE_URI}default"]
        graph_values = " ".join(f"<{uri}>" for uri in graph_uris)

        subject_iri = _sparql_iri(subject_uri)
        predicate_iri = _sparql_iri(predicate_uri)
        object_iri = _sparql_iri(object_uri)

        subject_filter = f"FILTER(?s = {subject_iri})" if subject_iri else ""
        predicate_filter = f"FILTER(?p = {predicate_iri})" if predicate_iri else ""
        object_filter = f"FILTER(?o = {object_iri})" if object_iri else ""
        predicate_exclusion = f"FILTER(?p != <{str(RDF.type)}>)" if subject_iri else ""

        subject_rows = store.query(
            f"""
            PREFIX rdf: <{str(RDF)}>
            PREFIX rdfs: <{str(RDFS)}>
            SELECT DISTINCT ?s ?sLabel ?typeLabel
            WHERE {{
                VALUES ?g {{ {graph_values} }}
                GRAPH ?g {{
                    ?s ?p ?o .
                    FILTER(isIRI(?s) && isIRI(?o))
                    ?s rdf:type ?sType .
                    {predicate_filter}
                    {object_filter}
                    OPTIONAL {{ ?s rdfs:label ?sLabel . }}
                    OPTIONAL {{ ?sType rdfs:label ?typeLabel . }}
                }}
            }}
            LIMIT 5000
            """
        )
        subject_options: dict[str, str] = {}
        for row in subject_rows:
            assert isinstance(row, ResultRow)
            uri = str(row.s)
            if not uri or uri in subject_options:
                continue
            label = str(getattr(row, "sLabel", "") or _label_from_iri(uri))
            type_label = str(getattr(row, "typeLabel", "") or "").strip() or None
            subject_options[uri] = _format_typed_label(label, type_label)

        predicate_rows = store.query(
            f"""
            PREFIX rdf: <{str(RDF)}>
            PREFIX rdfs: <{str(RDFS)}>
            SELECT DISTINCT ?p ?pLabel
            WHERE {{
                VALUES ?g {{ {graph_values} }}
                GRAPH ?g {{
                    ?s ?p ?o .
                    FILTER(isIRI(?o))
                    {subject_filter}
                    {object_filter}
                    {predicate_exclusion}
                    OPTIONAL {{ ?p rdfs:label ?pLabel . }}
                }}
            }}
            LIMIT 5000
            """
        )
        predicate_options: dict[str, str] = {}
        for row in predicate_rows:
            assert isinstance(row, ResultRow)
            uri = str(row.p)
            if not uri or uri in predicate_options:
                continue
            label = str(getattr(row, "pLabel", "") or _label_from_iri(uri))
            predicate_options[uri] = label

        object_rows = store.query(
            f"""
            PREFIX rdf: <{str(RDF)}>
            PREFIX rdfs: <{str(RDFS)}>
            SELECT DISTINCT ?o ?oLabel ?typeLabel
            WHERE {{
                VALUES ?g {{ {graph_values} }}
                GRAPH ?g {{
                    ?s ?p ?o .
                    FILTER(isIRI(?o))
                    {subject_filter}
                    {predicate_filter}
                    OPTIONAL {{ ?o rdfs:label ?oLabel . }}
                    OPTIONAL {{
                        ?o rdf:type ?oType .
                        OPTIONAL {{ ?oType rdfs:label ?typeLabel . }}
                    }}
                }}
            }}
            LIMIT 5000
            """
        )
        object_options: dict[str, str] = {}
        for row in object_rows:
            assert isinstance(row, ResultRow)
            uri = str(row.o)
            if not uri or uri in object_options:
                continue
            label = str(getattr(row, "oLabel", "") or _label_from_iri(uri))
            type_label = str(getattr(row, "typeLabel", "") or "").strip() or None
            object_options[uri] = _format_typed_label(label, type_label)

        return {
            "subjects": [
                {"uri": uri, "label": label}
                for uri, label in sorted(subject_options.items(), key=lambda item: item[1].lower())
            ],
            "predicates": [
                {"uri": uri, "label": label}
                for uri, label in sorted(
                    predicate_options.items(), key=lambda item: item[1].lower()
                )
            ],
            "objects": [
                {"uri": uri, "label": label}
                for uri, label in sorted(object_options.items(), key=lambda item: item[1].lower())
            ],
        }

    async def preview_graph_filters(
        self,
        graph_names: list[str],
        filters: list[dict[str, str | None]],
        limit: int = 10,
    ) -> dict[str, Any]:
        store = self._get_triple_store()

        graph_uris = [_resolve_graph_uri(name) for name in graph_names if name.strip()]
        if not graph_uris:
            graph_uris = [f"{GRAPH_BASE_URI}default"]
        graph_values = " ".join(f"<{uri}>" for uri in graph_uris)

        normalized_filters = filters or [{}]

        def _filter_conditions(filter_item: dict[str, str | None]) -> str:
            conditions = ["?s ?p ?o ."]
            subject_iri = _sparql_iri(filter_item.get("subject_uri"))
            predicate_iri = _sparql_iri(filter_item.get("predicate_uri"))
            object_iri = _sparql_iri(filter_item.get("object_uri"))
            if subject_iri:
                conditions.append(f"FILTER(?s = {subject_iri})")
            if predicate_iri:
                conditions.append(f"FILTER(?p = {predicate_iri})")
            if object_iri:
                conditions.append(f"FILTER(?o = {object_iri})")
            return " ".join(conditions)

        unique_triples: set[tuple[str, str, str]] = set()
        ordered_triples: list[tuple[str, str, str, bool, bool]] = []

        try:
            for filter_item in normalized_filters:
                filter_clause = _filter_conditions(filter_item)
                triples_rows = store.query(
                    f"""
                    SELECT DISTINCT ?s ?p ?o (isIRI(?o) AS ?o_is_iri) (isLiteral(?o) AS ?o_is_literal)
                    WHERE {{
                        VALUES ?g {{ {graph_values} }}
                        GRAPH ?g {{
                            FILTER(?o != <{str(OWL.NamedIndividual)}>)
                            {filter_clause}
                        }}
                    }}
                    """
                )
                for row in triples_rows:
                    assert isinstance(row, ResultRow)
                    triple = (str(row.s), str(row.p), str(row.o))
                    if triple in unique_triples:
                        continue
                    unique_triples.add(triple)
                    object_is_iri = str(getattr(row, "o_is_iri", "false")).lower() == "true"
                    object_is_literal = (
                        str(getattr(row, "o_is_literal", "false")).lower() == "true"
                    )
                    ordered_triples.append(
                        (
                            triple[0],
                            triple[1],
                            triple[2],
                            object_is_iri,
                            object_is_literal,
                        )
                    )
        except Exception:
            return {
                "count": 0,
                "individual_count": 0,
                "object_properties_count": 0,
                "data_properties_count": 0,
                "rows": [],
            }

        total_count = len(unique_triples)
        object_properties_count = 0
        data_properties_count = 0
        nodes: set[str] = set()
        for subject, predicate, object_value, object_is_iri, object_is_literal in ordered_triples:
            if object_is_iri and predicate != str(RDF.type):
                object_properties_count += 1
            if object_is_literal:
                data_properties_count += 1
            if subject.startswith("http://") or subject.startswith("https://"):
                nodes.add(subject)
            if predicate == str(RDF.type):
                continue
            if object_is_iri and (
                object_value.startswith("http://") or object_value.startswith("https://")
            ):
                nodes.add(object_value)
        individual_count = len(nodes)

        rows: list[dict[str, str]] = []
        for subject, predicate, object_value, _, _ in ordered_triples[: int(limit)]:
            s_label = (
                _label_from_iri(subject) if subject.startswith(("http://", "https://")) else subject
            )
            p_label = (
                _label_from_iri(predicate)
                if predicate.startswith(("http://", "https://"))
                else predicate
            )
            o_label = (
                _label_from_iri(object_value)
                if object_value.startswith(("http://", "https://"))
                else object_value
            )
            rows.append(
                {
                    "subject": s_label,
                    "predicate": p_label,
                    "object": o_label,
                }
            )

        return {
            "count": total_count,
            "individual_count": individual_count,
            "object_properties_count": object_properties_count,
            "data_properties_count": data_properties_count,
            "rows": rows,
        }

    async def list_views(self, workspace_id: str) -> list[dict[str, Any]]:
        rows = self._get_triple_store().query(
            f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX nexus: <http://ontology.naas.ai/nexus/>
            SELECT ?uri ?label ?description ?graph_names ?graph_filters
            WHERE {{
                GRAPH <{str(NEXUS_GRAPH_URI)}> {{
                    ?uri rdf:type nexus:GraphView .
                    ?uri rdfs:label ?label .
                    OPTIONAL {{ ?uri nexus:description ?description . }}
                    ?uri nexus:includesKnowledgeGraph ?graph_names .
                    ?uri nexus:hasGraphFilter ?graph_filters .
                }}
            }}
            """
        )
        views_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            assert isinstance(row, ResultRow)
            view_id = str(row.uri)
            graph_name = str(row.graph_names)
            graph_filter = str(row.graph_filters)

            if view_id not in views_by_id:
                views_by_id[view_id] = {
                    "workspace_id": workspace_id,
                    "id": view_id.split("/")[-1],
                    "uri": view_id,
                    "label": str(row.label),
                    "description": (
                        str(row.description) if getattr(row, "description", None) is not None else None
                    ),
                    "graph_names": [],
                    "graph_filters": [],
                    "scope": "workspace",
                }

            if graph_name not in views_by_id[view_id]["graph_names"]:
                views_by_id[view_id]["graph_names"].append(graph_name)
            if graph_filter not in views_by_id[view_id]["graph_filters"]:
                views_by_id[view_id]["graph_filters"].append(graph_filter)
        views = list(views_by_id.values())
        views.sort(key=lambda x: str(x.get("label", "")).lower())
        return views

    async def get_view(self, view_id: str, workspace_id: str) -> dict[str, Any]:
        view_uri = f"http://ontology.naas.ai/abi/{view_id}"
        rows = self._get_triple_store().query(
            f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX nexus: <http://ontology.naas.ai/nexus/>
            SELECT ?uri ?label ?description ?graph_names ?graph_filters
            WHERE {{
                GRAPH <{str(NEXUS_GRAPH_URI)}> {{
                    FILTER(STR(?uri) = "{view_uri}")
                    ?uri rdfs:label ?label .
                    OPTIONAL {{ ?uri nexus:description ?description . }}
                    ?uri nexus:includesKnowledgeGraph ?graph_names .
                    ?uri nexus:hasGraphFilter ?graph_filters .
                }}
            }}
            """
        )
        view_info: dict[str, Any] | None = None
        for row in rows:
            assert isinstance(row, ResultRow)
            row_view_uri = str(row.uri)
            graph_name = str(row.graph_names)
            graph_filter = str(row.graph_filters)

            if view_info is None:
                view_info = {
                    "workspace_id": workspace_id,
                    "id": row_view_uri.split("/")[-1],
                    "uri": row_view_uri,
                    "label": str(row.label),
                    "description": (
                        str(row.description) if getattr(row, "description", None) is not None else None
                    ),
                    "graph_names": [],
                    "graph_filters": [],
                    "scope": "workspace",
                }

            if graph_name not in view_info["graph_names"]:
                view_info["graph_names"].append(graph_name)
            if graph_filter not in view_info["graph_filters"]:
                view_info["graph_filters"].append(graph_filter)

        if view_info is None:
            raise ViewNotFoundError("View not found")
        return view_info

    async def create_view(
        self,
        *,
        name: str,
        description: str | None,
        graph_names: list[str],
        filters: list[dict[str, str | None]],
        creator: str,
    ) -> dict[str, Any]:
        if len(filters) == 0:
            raise ValueError("At least one filter is required")
        if len(graph_names) == 0:
            raise ValueError("At least one graph is required")

        inserted_graph = Graph()
        graph_filters: list[GraphFilter | URIRef | str] = []
        for filter_item in filters:
            subject_uri = filter_item.get("subject_uri")
            predicate_uri = filter_item.get("predicate_uri")
            object_uri = filter_item.get("object_uri")
            label = f"subject:{subject_uri}|predicate:{predicate_uri}|object:{object_uri}"
            graph_filter = GraphFilter(
                label=label,
                subject_uri=subject_uri if subject_uri else "unknown",
                predicate_uri=predicate_uri if predicate_uri else "unknown",
                object_uri=object_uri if object_uri else "unknown",
                creator=creator,
            )
            inserted_graph += graph_filter.rdf()
            graph_filters.append(graph_filter)

        graphs: list[KnowledgeGraph | URIRef | str] = [GRAPH_BASE_URI + graph_name for graph_name in graph_names]

        view = GraphView(
            label=name,
            description=description,
            has_graph_filter=graph_filters,
            includes_knowledge_graph=graphs,
            creator=creator,
        )
        inserted_graph += view.rdf()
        self._get_triple_store().insert(inserted_graph, graph_name=NEXUS_GRAPH_URI)
        return {
            "status": "created",
            "view_id": str(view._uri).split("/")[-1],  # noqa: SLF001
            "view_uri": str(view._uri),  # noqa: SLF001
            "view_label": view.label,
            "view_description": view.description,
            "view_has_graph_filter": view.has_graph_filter,
            "view_includes_knowledge_graph": view.includes_knowledge_graph,
            "total_triples": len(inserted_graph),
            "graph": inserted_graph.serialize(format="turtle"),
        }

    async def delete_view(self, view_id_or_uri: str) -> dict[str, Any]:
        store = self._get_triple_store()
        view_uri = self._resolve_view_uri(view_id_or_uri)
        if view_uri is None:
            raise ViewNotFoundError("View not found")

        from naas_abi.pipelines.RemoveIndividualPipeline import (
            RemoveIndividualPipeline,
            RemoveIndividualPipelineConfiguration,
            RemoveIndividualPipelineParameters,
        )

        pipeline = RemoveIndividualPipeline(
            configuration=RemoveIndividualPipelineConfiguration(
                triple_store=store,
            )
        )
        graph = pipeline.run(
            parameters=RemoveIndividualPipelineParameters(
                uri=view_uri,
                graph_names=[NEXUS_GRAPH_URI],
            )
        )
        return {
            "status": "deleted",
            "view_id": str(view_uri).split("/")[-1],
            "view_uri": str(view_uri),
            "total_triples": len(graph),
            "graph": graph.serialize(format="turtle"),
        }

    async def get_view_network(self, workspace_id: str, view_id: str, limit: int = 500) -> Any:
        view_info = await self.get_view(view_id=view_id, workspace_id=workspace_id)
        graph_filters_resolved = self.get_graph_filters(view_info.get("graph_filters", []))
        return _list_individuals(
            triple_store=self._get_triple_store(),
            workspace_id=workspace_id,
            graph_names=view_info.get("graph_names", []),
            graph_filters=graph_filters_resolved,
            limit=limit,
            depth=2,
        )

    async def get_view_overview(
        self,
        workspace_id: str,
        view_id: str,
        limit: int = 500,
    ) -> dict[str, Any]:
        view_data = await self.get_view_network(
            workspace_id=workspace_id,
            view_id=view_id,
            limit=limit,
        )
        nodes = view_data.nodes
        edges = view_data.edges

        kpis = {
            "total_instances": len(nodes),
            "total_relationships": len(edges),
            "average_degree": (2 * len(edges) / len(nodes)) if nodes else 0,
            "density": (len(edges) / (len(nodes) * (len(nodes) - 1))) if len(nodes) > 1 else 0,
        }
        type_counts: dict[str, int] = {}
        for node in nodes:
            node_type = (node.type or "unknown").strip() or "unknown"
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

        instances_by_class = [
            {"type": node_type, "count": count}
            for node_type, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        return {"kpis": kpis, "instances_by_class": instances_by_class}
