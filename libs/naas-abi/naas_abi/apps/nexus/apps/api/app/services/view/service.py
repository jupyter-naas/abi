from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.models import GraphViewModel
from naas_abi.apps.nexus.apps.api.app.services.graph.service import _list_individuals
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import OWL, RDF, RDFS, URIRef
from rdflib.query import ResultRow
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

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


def _model_to_dict(model: GraphViewModel, workspace_id: str) -> dict[str, Any]:
    state: dict[str, Any] = {}
    try:
        parsed = json.loads(model.state)
        if isinstance(parsed, dict):
            state = parsed
    except (json.JSONDecodeError, TypeError):
        state = {}

    return {
        "workspace_id": workspace_id,
        "id": model.id,
        "uri": f"/api/view/{model.id}",
        "label": model.name,
        "name": model.name,
        "description": None,
        "view_type": model.view_type,
        "kind": model.kind,
        "visibility": model.visibility,
        "creator_id": model.creator_id,
        "graph_id": model.graph_id,
        "graph_uri": model.graph_uri,
        "graph_names": [model.graph_id],
        "graph_filters": [],
        "state": state,
        "path": getattr(model, "path", "") or "",
        "scope": model.visibility,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }


class ViewService:
    def __init__(
        self,
        triple_store_getter: Callable[[], TripleStoreService] | None = None,
        db: AsyncSession | None = None,
    ) -> None:
        self._triple_store_getter = triple_store_getter
        self._db = db

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

    def _visibility_clause(self, query, user_id: str | None):
        if user_id:
            return query.where(
                (GraphViewModel.visibility == "workspace")
                | (GraphViewModel.creator_id == user_id)
            )
        return query.where(GraphViewModel.visibility == "workspace")

    async def list_views(
        self,
        workspace_id: str,
        *,
        user_id: str | None = None,
        path: str | None = None,
        recursive: bool = False,
    ) -> list[dict[str, Any]]:
        if self._db is None:
            raise ViewServiceUnavailableError("Database session is not available")

        query = select(GraphViewModel).where(GraphViewModel.workspace_id == workspace_id)
        query = self._visibility_clause(query, user_id)
        if path is not None:
            norm = _normalize_path(path)
            if recursive:
                like = norm.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                prefix = f"{like}/" if like else ""
                query = query.where(
                    (GraphViewModel.path == norm)
                    | (GraphViewModel.path.like(f"{prefix}%", escape="\\"))
                )
            else:
                query = query.where(GraphViewModel.path == norm)

        result = await self._db.execute(query.order_by(GraphViewModel.path, GraphViewModel.name))
        models = result.scalars().all()
        views = [_model_to_dict(model, workspace_id) for model in models]
        views.sort(key=lambda x: (str(x.get("path", "")).lower(), str(x.get("label", "")).lower()))
        return views

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
    ) -> dict[str, Any]:
        """Partial update — rename / move / replace state / change visibility. Preserves id+created_at."""
        if self._db is None:
            raise ViewServiceUnavailableError("Database session is not available")
        result = await self._db.execute(
            select(GraphViewModel).where(
                GraphViewModel.id == view_id, GraphViewModel.workspace_id == workspace_id
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ViewNotFoundError("View not found")

        effective_kind = kind if kind is not None else model.kind
        if name is not None:
            if not name.strip():
                raise ValueError("View name cannot be empty")
            model.name = name.strip()
        if path is not None:
            model.path = _normalize_path(path)
        if visibility is not None:
            if visibility != "workspace":
                raise ValueError("Only 'workspace' visibility is supported")
            model.visibility = visibility
        if view_type is not None:
            model.view_type = (view_type or "Unknown").strip() or "Unknown"
        if kind is not None:
            model.kind = kind
        if state is not None:
            if effective_kind == "query" and not isinstance(state.get("spec"), dict):
                raise ValueError("A query view requires a compiled spec in state")
            model.state = json.dumps(state)
        await self._db.commit()
        await self._db.refresh(model)
        return _model_to_dict(model, workspace_id)

    async def list_folders(self, workspace_id: str, *, user_id: str | None = None) -> list[dict[str, Any]]:
        """Folder tree derived from distinct ``path`` values (folders are implicit)."""
        if self._db is None:
            raise ViewServiceUnavailableError("Database session is not available")
        query = select(GraphViewModel.path).where(GraphViewModel.workspace_id == workspace_id)
        query = self._visibility_clause(query, user_id)
        rows = (await self._db.execute(query)).scalars().all()
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
            folders.append({"path": fp, "name": fp.split("/")[-1], "view_count": direct.get(fp, 0), "total_count": total})
        return folders

    async def rename_folder(
        self, *, workspace_id: str, from_path: str, to_path: str, merge: bool = False
    ) -> dict[str, Any]:
        """Rename/move a folder = prefix-rewrite ``path`` on every view in the subtree, one txn."""
        if self._db is None:
            raise ViewServiceUnavailableError("Database session is not available")
        old = _normalize_path(from_path)
        new = _normalize_path(to_path)
        if not old:
            raise ValueError("from_path (folder to rename) is required")
        if old == new:
            return {"status": "renamed", "from_path": old, "to_path": new, "updated_count": 0}
        if new == old or new.startswith(old + "/"):
            raise ValueError("Cannot move a folder into its own subtree")

        like = old.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        subtree = (GraphViewModel.path == old) | (GraphViewModel.path.like(f"{like}/%", escape="\\"))
        moved = (await self._db.execute(
            select(GraphViewModel).where(GraphViewModel.workspace_id == workspace_id, subtree)
        )).scalars().all()

        if not merge:
            dest_keys = {((new if m.path == old else f"{new}/{m.path[len(old) + 1:]}" if new else m.path[len(old) + 1:]), m.name) for m in moved}
            existing = (await self._db.execute(
                select(GraphViewModel.path, GraphViewModel.name).where(
                    GraphViewModel.workspace_id == workspace_id, ~subtree
                )
            )).all()
            clash = {(p, n) for p, n in existing} & dest_keys
            if clash:
                first = sorted(clash)[0]
                raise ValueError(f"Destination already contains a view named '{first[1]}' at '{first[0]}'. Pass merge=true to combine.")

        # Per-row prefix rewrite (portable across Postgres/SQLite; subtree is small + workspace-scoped).
        for m in moved:
            tail = "" if m.path == old else m.path[len(old) + 1:]
            m.path = new if m.path == old else (f"{new}/{tail}" if new else tail)
        await self._db.commit()
        return {"status": "renamed", "from_path": old, "to_path": new, "updated_count": len(moved)}

    async def get_view(self, view_id: str, workspace_id: str) -> dict[str, Any]:
        if self._db is None:
            raise ViewServiceUnavailableError("Database session is not available")

        result = await self._db.execute(
            select(GraphViewModel).where(
                GraphViewModel.id == view_id,
                GraphViewModel.workspace_id == workspace_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ViewNotFoundError("View not found")
        return _model_to_dict(model, workspace_id)

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
        _ = description, graph_names, filters
        if self._db is None:
            raise ViewServiceUnavailableError("Database session is not available")
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

        view_id = f"view-{uuid4().hex[:12]}"
        model = GraphViewModel(
            id=view_id,
            workspace_id=workspace_id,
            name=name.strip(),
            view_type=(view_type or "Unknown").strip() or "Unknown",
            kind=kind or "network",
            visibility=visibility or "workspace",
            creator_id=creator,
            graph_id=graph_id.strip(),
            graph_uri=graph_uri.strip(),
            state=json.dumps(state),
            path=_normalize_path(path),
        )
        self._db.add(model)
        await self._db.commit()
        await self._db.refresh(model)
        return {
            "status": "created",
            "view_id": model.id,
            "view_uri": f"/api/view/{model.id}",
            "view_label": model.name,
            "view_type": model.view_type,
            "kind": model.kind,
            "visibility": model.visibility,
        }

    async def delete_view(self, view_id_or_uri: str, *, workspace_id: str) -> dict[str, Any]:
        if self._db is None:
            raise ViewServiceUnavailableError("Database session is not available")

        view_id = view_id_or_uri.strip()
        if view_id.startswith("http://") or view_id.startswith("https://"):
            view_id = view_id.rsplit("/", 1)[-1]
        if view_id.startswith("/api/view/"):
            view_id = view_id.removeprefix("/api/view/")

        result = await self._db.execute(
            delete(GraphViewModel).where(
                GraphViewModel.id == view_id,
                GraphViewModel.workspace_id == workspace_id,
            )
        )
        await self._db.commit()
        if result.rowcount == 0:
            raise ViewNotFoundError("View not found")
        return {
            "status": "deleted",
            "view_id": view_id,
        }

    async def get_view_network(self, workspace_id: str, view_id: str, limit: int = 500) -> Any:
        view_info = await self.get_view(view_id=view_id, workspace_id=workspace_id)
        if view_info.get("kind") == "network":
            raise ValueError("Network views do not support legacy network endpoint")
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
