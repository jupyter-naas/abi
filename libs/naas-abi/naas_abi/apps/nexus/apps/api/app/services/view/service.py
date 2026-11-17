from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import GraphAccessError
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import sparql_iri
from naas_abi.apps.nexus.apps.api.app.services.graph.service import _list_individuals
from naas_abi.apps.nexus.apps.api.app.services.view.port import (
    GraphViewRecord,
    GraphViewStorePort,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import OWL, RDF, RDFS, URIRef
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


def _normalize_path(raw: str | None) -> str:
    """Normalize a folder path: slash-joined segments, no leading/trailing slash, no ./.. .

    Root = "". Raises ValueError on over-long segments/paths.
    """
    if not raw:
        return ""
    segments = [s.strip() for s in raw.replace("\\", "/").split("/")]
    cleaned = [s for s in segments if s and s not in (".", "..")]
    if any(len(s) > 128 for s in cleaned):
        raise ValueError("Folder name segment too long (max 128 chars)")
    path = "/".join(cleaned)
    if len(path) > 1024:
        raise ValueError("Folder path too long (max 1024 chars)")
    return path


def _resolve_graph_uri(graph_name: str) -> str:
    candidate = graph_name.strip()
    if not candidate:
        return ""
    if candidate.startswith(("http://", "https://", "urn:")):
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


_EMPTY_PREVIEW: dict[str, Any] = {
    "count": 0,
    "individual_count": 0,
    "object_properties_count": 0,
    "data_properties_count": 0,
    "rows": [],
}


def _preview(store: Any, graph_values: str, patterns: list[str], limit: int) -> dict[str, Any]:
    """Count the distinct triples matching any filter on the store, and read
    only the ``limit`` rows shown: memory does not grow with the graphs."""
    union = " UNION ".join("{ " + pattern + " }" for pattern in patterns)
    matching = f"""
        VALUES ?g {{ {graph_values} }}
        GRAPH ?g {{
            FILTER(?o != <{OWL.NamedIndividual}>)
            {union}
        }}"""
    triples = f"SELECT DISTINCT ?s ?p ?o WHERE {{ {matching} }}"
    rdf_type = f"<{RDF.type}>"
    web = 'FILTER(STRSTARTS(STR(?node), "http://") || STRSTARTS(STR(?node), "https://"))'

    def numbers(sparql: str) -> list[int]:
        for row in store.query(sparql):
            return [int(value) if value is not None else 0 for value in row]
        return []

    try:
        count, objects, data = numbers(
            "SELECT (COUNT(*) AS ?triples) "
            f"(SUM(IF(isIRI(?o) && ?p != {rdf_type}, 1, 0)) AS ?objects) "
            "(SUM(IF(isLiteral(?o), 1, 0)) AS ?data) "
            f"WHERE {{ {{ {triples} }} }}"
        )
        # Nodes: http(s) subjects, and http(s) objects of non-type relations.
        (individuals,) = numbers(
            "SELECT (COUNT(DISTINCT ?node) AS ?individuals) WHERE { "
            f"{{ SELECT DISTINCT (?s AS ?node) WHERE {{ {matching} }} }} UNION "
            f"{{ SELECT DISTINCT (?o AS ?node) WHERE {{ {matching} "
            f"FILTER(isIRI(?o) && ?p != {rdf_type}) }} }} {web} }}"
        )
        shown = list(store.query(f"{triples} LIMIT {max(0, limit)}"))
    except Exception:
        return dict(_EMPTY_PREVIEW)

    rows: list[dict[str, str]] = []
    for row in shown:
        assert isinstance(row, ResultRow)
        labels = [
            _label_from_iri(value) if value.startswith(("http://", "https://")) else value
            for value in (str(row.s), str(row.p), str(row.o))
        ]
        rows.append(dict(zip(("subject", "predicate", "object"), labels, strict=True)))
    return {
        "count": count,
        "individual_count": individuals,
        "object_properties_count": objects,
        "data_properties_count": data,
        "rows": rows,
    }


def _format_typed_label(label: str, type_label: str | None) -> str:
    if type_label and type_label.strip():
        return f"{label} (type: {type_label.strip()})"
    return label


def _view_to_dict(view: GraphViewRecord) -> dict[str, Any]:
    return {
        "workspace_id": view.workspace_id,
        "id": view.id,
        "uri": f"/api/view/{view.id}",
        "label": view.name,
        "name": view.name,
        "description": view.description,
        "view_type": view.view_type,
        "kind": view.kind,
        "visibility": view.visibility,
        "creator_id": view.creator_id,
        "graph_id": view.graph_id,
        "graph_uri": view.graph_uri,
        "graph_names": [view.graph_id],
        "graph_filters": [],
        "state": view.state,
        "path": view.path or "",
        "scope": view.visibility,
        "created_at": view.created_at.isoformat() if view.created_at else None,
        "updated_at": view.updated_at.isoformat() if view.updated_at else None,
    }


def _visible(view: GraphViewRecord, user_id: str | None) -> bool:
    """Workspace views, and a user's own."""
    return view.visibility == "workspace" or (user_id is not None and view.creator_id == user_id)


def _in_subtree(path: str, folder: str) -> bool:
    """``path`` is ``folder`` or below it (the root holds every path)."""
    return not folder or path == folder or path.startswith(folder + "/")


class ViewService:
    def __init__(
        self,
        triple_store_getter: Callable[[], TripleStoreService] | None = None,
        store: GraphViewStorePort | None = None,
        access_scope: GraphAccessScope | None = None,
        catalog_store_getter: Callable[[], TripleStoreService] | None = None,
    ) -> None:
        self._triple_store_getter = triple_store_getter
        self._catalog_store_getter = catalog_store_getter
        self._store = store
        self._access_scope = access_scope

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

    def _get_catalog_store(self) -> TripleStoreService:
        """Nexus application metadata (GraphFilter defs) lives outside data scopes."""
        if self._catalog_store_getter is not None:
            return self._catalog_store_getter()
        return self._get_triple_store()

    def get_graph_filters(self, uris: list[str]) -> list[dict[str, Any]]:
        if not uris:
            return []
        # Filter definitions are catalog metadata. Data access is enforced on the
        # view's graph_names before this runs; do not require the scoped store here.
        safe_uris = [uri for uri in uris if uri and uri.strip()]
        for uri in safe_uris:
            sparql_iri(uri)
        values = " ".join(sparql_iri(uri) for uri in safe_uris)
        values_clause = f"VALUES ?filter_uri {{ {values} }}" if values else ""
        store = self._get_catalog_store()

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
                    str(row.filter_uri) if hasattr(row, "filter_uri") and row.filter_uri else None
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
        if self._access_scope is None:
            raise GraphAccessError("A workspace graph scope is required")
        if not graph_uris:
            graph_uris = sorted(self._access_scope.readable)
        self._access_scope.require(self._access_scope.workspace_id, graph_uris)
        graph_values = " ".join(sparql_iri(uri) for uri in graph_uris)

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
        if self._access_scope is None:
            raise GraphAccessError("A workspace graph scope is required")
        if not graph_uris:
            graph_uris = sorted(self._access_scope.readable)
        self._access_scope.require(self._access_scope.workspace_id, graph_uris)
        graph_values = " ".join(sparql_iri(uri) for uri in graph_uris)

        patterns = [_filter_conditions(item) for item in filters or [{}]]
        return await asyncio.to_thread(_preview, store, graph_values, patterns, int(limit))

    def _require_store(self) -> GraphViewStorePort:
        if self._store is None:
            raise ViewServiceUnavailableError("Database session is not available")
        return self._store

    async def list_views(
        self,
        workspace_id: str,
        *,
        user_id: str | None = None,
        path: str | None = None,
        recursive: bool = False,
    ) -> list[dict[str, Any]]:
        store = self._require_store()
        views = [view for view in await store.list(workspace_id) if _visible(view, user_id)]
        if path is not None:
            norm = _normalize_path(path)
            if recursive:
                views = [view for view in views if _in_subtree(view.path, norm)]
            else:
                views = [view for view in views if view.path == norm]
        listed = [_view_to_dict(view) for view in views]
        listed.sort(key=lambda x: (str(x.get("path", "")).lower(), str(x.get("label", "")).lower()))
        return listed

    async def update_view(
        self,
        view_id: str,
        *,
        workspace_id: str,
        name: str | None = None,
        path: str | None = None,
        state: dict[str, Any] | None = None,
        visibility: str | None = None,
        view_type: str | None = None,
        kind: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Partial update — rename / move / replace state / change visibility / description.

        ``description`` is partial too: ``None`` leaves it untouched; pass an empty string to
        clear it (stored as NULL).
        """
        store = self._require_store()
        view = await store.get(workspace_id, view_id)
        if view is None:
            raise ViewNotFoundError("View not found")

        effective_kind = kind if kind is not None else view.kind
        if name is not None:
            if not name.strip():
                raise ValueError("View name cannot be empty")
            view.name = name.strip()
        if description is not None:
            view.description = description.strip() or None
        if path is not None:
            view.path = _normalize_path(path)
        if visibility is not None:
            if visibility != "workspace":
                raise ValueError("Only 'workspace' visibility is supported")
            view.visibility = visibility
        if view_type is not None:
            view.view_type = (view_type or "Unknown").strip() or "Unknown"
        if kind is not None:
            view.kind = kind
        if state is not None:
            if effective_kind == "query" and not isinstance(state.get("spec"), dict):
                raise ValueError("A query view requires a compiled spec in state")
            view.state = state
        saved = await store.save(view)
        if saved is None:
            raise ViewNotFoundError("View not found")
        return _view_to_dict(saved)

    async def list_folders(
        self, workspace_id: str, *, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Folder tree derived from distinct ``path`` values (folders are implicit)."""
        store = self._require_store()
        rows = [view.path for view in await store.list(workspace_id) if _visible(view, user_id)]
        direct: dict[str, int] = {}
        for p in rows:
            direct[p or ""] = direct.get(p or "", 0) + 1
        all_folders: set[str] = set()
        for p in direct:
            if not p:
                continue
            parts = p.split("/")
            for i in range(1, len(parts) + 1):
                all_folders.add("/".join(parts[:i]))
        folders = []
        for fp in sorted(all_folders):
            total = sum(c for pp, c in direct.items() if pp == fp or pp.startswith(fp + "/"))
            folders.append(
                {
                    "path": fp,
                    "name": fp.split("/")[-1],
                    "view_count": direct.get(fp, 0),
                    "total_count": total,
                }
            )
        return folders

    async def rename_folder(
        self, *, workspace_id: str, from_path: str, to_path: str, merge: bool = False
    ) -> dict[str, Any]:
        """Rename/move a folder = prefix-rewrite ``path`` on every view in the subtree, one txn."""
        store = self._require_store()
        old = _normalize_path(from_path)
        new = _normalize_path(to_path)
        if not old:
            raise ValueError("from_path (folder to rename) is required")
        if old == new:
            return {"status": "renamed", "from_path": old, "to_path": new, "updated_count": 0}
        if new == old or new.startswith(old + "/"):
            raise ValueError("Cannot move a folder into its own subtree")

        views = await store.list(workspace_id)
        moved = [view for view in views if _in_subtree(view.path, old)]

        def destination(current: str) -> str:
            tail = "" if current == old else current[len(old) + 1 :]
            return new if current == old else (f"{new}/{tail}" if new else tail)

        if not merge:
            dest_keys = {(destination(view.path), view.name) for view in moved}
            existing = {(view.path, view.name) for view in views if not _in_subtree(view.path, old)}
            clash = existing & dest_keys
            if clash:
                first = sorted(clash)[0]
                raise ValueError(
                    f"Destination already contains a view named '{first[1]}' at '{first[0]}'. Pass merge=true to combine."
                )

        await store.move(workspace_id, {view.id: destination(view.path) for view in moved})
        return {"status": "renamed", "from_path": old, "to_path": new, "updated_count": len(moved)}

    async def get_view(self, view_id: str, workspace_id: str) -> dict[str, Any]:
        store = self._require_store()
        view = await store.get(workspace_id, view_id)
        if view is None:
            raise ViewNotFoundError("View not found")
        return _view_to_dict(view)

    async def create_view(
        self,
        *,
        workspace_id: str,
        name: str,
        view_type: str,
        kind: str,
        visibility: str,
        graph_id: str,
        graph_uri: str,
        state: dict[str, Any],
        creator: str,
        description: str | None = None,
        graph_names: list[str] | None = None,
        filters: list[dict[str, str | None]] | None = None,
        path: str | None = None,
    ) -> dict[str, Any]:
        _ = graph_names, filters
        store = self._require_store()
        if not name.strip():
            raise ValueError("View name is required")
        if not graph_id.strip():
            raise ValueError("Graph id is required")
        if not graph_uri.strip():
            raise ValueError("Graph uri is required")
        if kind == "network" and not state.get("selectedClassIds"):
            raise ValueError("At least one selected class is required for network views")
        if kind == "query" and not isinstance(state.get("spec"), dict):
            raise ValueError("A query view requires a compiled spec in state")

        clean_description = description.strip() if description and description.strip() else None
        view = await store.add(
            GraphViewRecord(
                id=f"view-{uuid4().hex[:12]}",
                workspace_id=workspace_id,
                name=name.strip(),
                description=clean_description,
                view_type=(view_type or "Unknown").strip() or "Unknown",
                kind=kind or "network",
                visibility=visibility or "workspace",
                creator_id=creator,
                graph_id=graph_id.strip(),
                graph_uri=graph_uri.strip(),
                state=state,
                path=_normalize_path(path),
            )
        )
        return {
            "status": "created",
            "view_id": view.id,
            "view_uri": f"/api/view/{view.id}",
            "view_label": view.name,
            "view_type": view.view_type,
            "kind": view.kind,
            "visibility": view.visibility,
        }

    async def delete_view(self, view_id_or_uri: str, *, workspace_id: str) -> dict[str, Any]:
        store = self._require_store()

        view_id = view_id_or_uri.strip()
        if view_id.startswith("http://") or view_id.startswith("https://"):
            view_id = view_id.rsplit("/", 1)[-1]
        if view_id.startswith("/api/view/"):
            view_id = view_id.removeprefix("/api/view/")

        if not await store.delete(workspace_id, view_id):
            raise ViewNotFoundError("View not found")
        return {
            "status": "deleted",
            "view_id": view_id,
        }

    async def get_view_network(self, workspace_id: str, view_id: str, limit: int = 500) -> Any:
        view_info = await self.get_view(view_id=view_id, workspace_id=workspace_id)
        if view_info.get("kind") == "network":
            raise ValueError("Network views do not support legacy network endpoint")
        if self._access_scope is None:
            raise GraphAccessError("A workspace graph scope is required")
        self._access_scope.require(
            workspace_id, [_resolve_graph_uri(g) for g in view_info.get("graph_names", [])]
        )
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
            for node_type, count in sorted(
                type_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ]
        return {"kpis": kpis, "instances_by_class": instances_by_class}
