# graph (Knowledge Graph API endpoints)

## What it is
FastAPI endpoints for managing and querying named RDF graphs backed by `TripleStoreService`. Includes:
- Listing/creating/clearing/deleting named graphs
- Fetching a graph “overview” (basic KPIs and instance counts)
- Fetching a graph “network” (nodes/edges derived from `owl:NamedIndividual` resources)

## Public API

### FastAPI router
- `router: APIRouter`
  - Configured with `Depends(get_current_user_required)` so all routes require an authenticated user.

### Pydantic models
- `GraphInfo`: `{id, uri, label}`
- `GraphCreate`: `{workspace_id, label, description?}`
- `GraphClear`: `{workspace_id, id}`
- `GraphDelete`: `{workspace_id, id}`
- `GraphOverview`: `{kpis: dict, instances_by_class: list[dict]}`
- `GraphNode`: node representation used in network output
- `GraphEdge`: edge representation used in network output
- `GraphData`: `{nodes: list[GraphNode], edges: list[GraphEdge]}`

### HTTP endpoints
- `GET /list` → `list[GraphInfo]`
  - Lists graphs declared in the **Nexus graph** (`NEXUS_GRAPH_URI`) as `KnowledgeGraph` instances.
  - Requires `workspace_id` (query parameter) and workspace access.

- `POST /create` → `GraphInfo`
  - Creates a new named graph under `GRAPH_BASE_URI` using a slug derived from `label`.
  - Inserts a `KnowledgeGraph` resource into the **Nexus graph**.
  - Body: `GraphCreate`.

- `POST /clear` → `{"status": "cleared"}`
  - Clears all triples from a named graph.
  - Body: `GraphClear`.
  - Refuses to clear the schema or nexus graphs.

- `POST /delete` → `{"status": "deleted"}`
  - Drops a named graph.
  - Body: `GraphDelete`.
  - Refuses to delete the schema or nexus graphs.

- `GET /{graph_id}/overview` → `GraphOverview`
  - Returns KPIs and counts by class for `owl:NamedIndividual` instances in the graph.
  - Query params: `workspace_id` (required), `limit` (default 500, max 5000).

- `GET /{graph_id}/network` → `GraphData`
  - Returns nodes/edges by expanding each discovered named individual using `SPARQLUtils.get_subject_graph(...)`.
  - Query params: `workspace_id` (required), `limit` (default 500, max 5000).

### Helper functions (module-level)
- `get_triple_store_service(request: Request) -> TripleStoreService`
  - Fetches `request.app.state.triple_store`, otherwise attempts to load it via `naas_abi.ABIModule.get_instance()`.

- `slugify(value: str) -> str`
  - Converts text to a URL-safe slug.

- `list_individuals(...) -> GraphData`
  - Cached (FS cache, pickle, TTL 1 day).
  - Inputs:
    - `triple_store`, `workspace_id`, `graph_names`, `graph_filters`, `limit=500`, `depth=2`
  - Extracts nodes (named individuals) and edges (IRI objects excluding `rdf:type`) with deterministic edge IDs (SHA-256 of `s|p|o`).

- `build_graph_overview(triple_store, graph_uri, limit=500) -> GraphOverview`
  - Computes:
    - `total_instances`, `total_relationships`, `average_degree`, `density`
    - `instances_by_class` (class label resolved via schema graph)

## Configuration/Dependencies
- **FastAPI**: `APIRouter`, `Request`, `Depends`, `HTTPException`, `Query`
- **Auth**:
  - `get_current_user_required`
  - `require_workspace_access(user_id, workspace_id)` is enforced in every endpoint
- **Triple store**:
  - `TripleStoreService` must be available either at `request.app.state.triple_store` or via `naas_abi.ABIModule`
- **Ontology / RDF tooling**:
  - `rdflib` (`URIRef`, `Literal`, `RDF`, `RDFS`, `OWL`)
  - Schema graph is hard-coded: `SCHEMA_GRAPH_URI = "http://ontology.naas.ai/graph/schema"`
  - Nexus graph is hard-coded: `NEXUS_GRAPH_URI = "http://ontology.naas.ai/graph/nexus"`
- **Caching**:
  - Uses `CacheFactory.CacheFS_find_storage(subpath="nexus/graph")`
  - `list_individuals` cached as `DataType.PICKLE` with TTL = 1 day

## Usage

### Mounting the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import graph

app = FastAPI()
app.include_router(graph.router, prefix="/graph", tags=["graph"])
```

### Providing the triple store in app state
```python
from fastapi import FastAPI
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService

app = FastAPI()
app.state.triple_store = TripleStoreService(...)  # constructed per your environment
```

## Caveats
- `POST /clear` and `POST /delete` reject operations on:
  - `http://ontology.naas.ai/graph/schema`
  - `http://ontology.naas.ai/graph/nexus`
- Graph IDs are derived from `slugify(label)` during creation; collisions are not handled in this module.
- `GET /{graph_id}/network` uses cached `list_individuals`; updates in the triple store may not be reflected until cache expiry (TTL 1 day).
