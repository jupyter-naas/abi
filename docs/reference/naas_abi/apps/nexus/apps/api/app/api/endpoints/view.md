# view (Dedicated Graph Views API endpoints)

## What it is
FastAPI router implementing CRUD-like endpoints for **Graph Views** stored in a triple store, plus helper endpoints to:
- list available filter options (subjects/predicates/objects) from selected graphs
- preview triples matched by ad-hoc filters
- fetch a view’s network and computed overview KPIs

All data is backed by RDF graphs (notably the Nexus graph).

## Public API

### FastAPI router
- `router: APIRouter`
  - Declared with `dependencies=[Depends(get_current_user_required)]` (all endpoints require an authenticated user).

### Pydantic models (request/response)
- `GraphViewInfo`
  - View metadata: `workspace_id`, `id`, `uri`, `label`, optional `description`, `graph_names`, `graph_filters`, `scope`.
- `GraphTripleFilter`
  - Triple pattern filter: optional `subject_uri`, `predicate_uri`, `object_uri`.
- `GraphFilterOption`
  - Option item: `uri`, `label`.
- `GraphFilterOptionsResponse`
  - Lists of `subjects`, `predicates`, `objects` as `GraphFilterOption`.
- `CreateGraphView`
  - Create payload: `workspace_id`, `name`, optional `description`, `graph_names`, `filters`, `scope`, optional `user_id`.
- `UpdateGraphView`
  - Defined but not used by any endpoint in this module.
- `DeleteGraphView`
  - Delete payload: `workspace_id`, optional `id`, optional `uri`.
- `ViewOverview`
  - Overview response: `kpis` and `instances_by_class`.
- `TriplePreviewRequest`
  - Preview payload: `workspace_id`, `graph_names`, `filters`, `limit` (1–100).
- `TriplePreviewRow`, `TriplePreviewResponse`
  - Preview output: counts + sampled rows.

### Endpoints
- `GET /filters/options` → `GraphFilterOptionsResponse`
  - Lists distinct subject/predicate/object IRIs from selected graphs, optionally constrained by `subject_uri`, `predicate_uri`, `object_uri`.
- `POST /filters/preview` → `TriplePreviewResponse`
  - Runs the provided triple filters against selected graphs and returns counts plus up to `limit` labelized rows.
  - Returns all-zero response on any query/processing exception (stability fallback).
- `GET /list` → `list[GraphViewInfo]`
  - Lists all `nexus:GraphView` instances from the Nexus graph, aggregating their graph names and graph filter URIs.
- `GET /{view_id}` → `GraphViewInfo`
  - Fetches a single view by constructing a fixed ABI URI: `http://ontology.naas.ai/abi/{view_id}` and querying it in the Nexus graph.
- `POST /` (and `POST ""`) → `dict[str, Any]`
  - Creates graph filters and a graph view, inserts them into the Nexus graph, returns created metadata plus inserted RDF as Turtle.
- `DELETE /{view_id}` → `dict[str, Any]`
  - Deletes a view individual (and associated triples in the Nexus graph) via `RemoveIndividualPipeline`.
  - Accepts `workspace_id` either as query param or in JSON payload.
  - `view_id` may be a URI or an ID; resolution is attempted via `_resolve_view_uri`.
- `GET /{view_id}/network` → `Any`
  - Loads the view, resolves its stored `graph_filters` to filter definitions, then delegates to `graph_endpoints.list_individuals(...)` with `depth=2`.
- `GET /{view_id}/overview` → `ViewOverview`
  - Calls `/network`, then computes basic KPIs and counts instances by node type.

### Internal helpers (module-level)
- `get_triple_store_service(request: Request) -> TripleStoreService`
  - Retrieves `request.app.state.triple_store` or loads it from `naas_abi.ABIModule.get_instance().engine.services.triple_store`; raises HTTP 500 if unavailable.
- `_resolve_view_uri(store, view_id) -> URIRef | None`
  - Accepts a URI or an identifier; queries Nexus graph for a matching `nexus:GraphView` URI.
- `_normalize_filter_part(value) -> str | None`
  - Strips and converts `"unknown"`/empty to `None`.
- `_resolve_graph_uri(graph_name) -> str`
  - Returns as-is if already http(s); otherwise prefixes with `GRAPH_BASE_URI`.
- `_sparql_iri(value) -> str | None`
  - Produces `<iri>` if safe (rejects whitespace/quotes/angle brackets), else `None`.
- `_label_from_iri(iri) -> str`
  - Last path/hash segment.
- `_format_typed_label(label, type_label) -> str`
  - Appends `(type: ...)` when available.
- `get_graph_filters(triple_store, uris) -> list[dict]`
  - Loads `nexus:GraphFilter` definitions from the Nexus graph, optionally constrained by provided URIs; falls back to loading all filters if none match.

## Configuration/Dependencies
- **FastAPI**: `APIRouter`, `Depends`, `Request`, `Query`, `HTTPException`
- **Auth dependencies** (imported):
  - `get_current_user_required`
  - `require_workspace_access`
- **Triple store**:
  - `naas_abi_core.services.triple_store.TripleStoreService`
  - Initialized either via `request.app.state.triple_store` or `naas_abi.ABIModule`
- **RDF/OWL**:
  - `rdflib` (`RDF`, `RDFS`, `OWL`, `URIRef`) and SPARQL queries
- **Ontology classes**:
  - `GraphView`, `GraphFilter`, `KnowledgeGraph` from `naas_abi.ontologies.modules.NexusPlatformOntology`
- **Deletion pipeline**:
  - `naas_abi.pipelines.RemoveIndividualPipeline`

Constants:
- `NEXUS_GRAPH_URI = "http://ontology.naas.ai/graph/nexus"`
- `GRAPH_BASE_URI = "http://ontology.naas.ai/graph/"`

## Usage

### Mount the router (minimal)
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints.view import router as view_router

app = FastAPI()
app.include_router(view_router, prefix="/views", tags=["views"])
```

### Call the preview endpoint (HTTP example)
```python
import requests

resp = requests.post(
    "http://localhost:8000/views/filters/preview",
    headers={"Authorization": "Bearer <token>"},
    json={
        "workspace_id": "ws_123",
        "graph_names": ["default"],
        "filters": [{"subject_uri": None, "predicate_uri": None, "object_uri": None}],
        "limit": 10,
    },
)
print(resp.json())
```

## Caveats
- `GET /{view_id}` and `GET /{view_id}/network` have workspace access checks commented out in code; do not assume enforcement at these endpoints.
- `GET /{view_id}` only searches for the URI `http://ontology.naas.ai/abi/{view_id}`; it does **not** use `_resolve_view_uri`.
- `POST /` requires **at least one** `filters` entry and **at least one** `graph_names` entry (otherwise 400).
- `/filters/preview` swallows all exceptions and returns zeros/empty rows if the triple store rejects the query pattern.
- Graph name handling differs by endpoint:
  - options/preview normalize names via `_resolve_graph_uri` and default to `.../graph/default` when none provided
  - create uses `GRAPH_BASE_URI + graph_name` (no URI normalization)
