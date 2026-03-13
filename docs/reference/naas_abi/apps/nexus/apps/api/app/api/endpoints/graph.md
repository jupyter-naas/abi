# graph (Knowledge Graph API endpoints)

## What it is
FastAPI router providing CRUD and query endpoints for a workspace-scoped knowledge graph (nodes/edges) persisted in an ABI `TripleStoreService` (RDF triples via `rdflib`).

## Public API

### FastAPI router
- `router: APIRouter`
  - Global dependency: `Depends(get_current_user_required)` (authentication enforced for all routes).

### Pydantic models (request/response schemas)
- `GraphNode`
  - Node representation: `id`, `workspace_id`, `type`, `label`, `properties`, `created_at`, `updated_at`.
- `GraphEdge`
  - Edge representation: `id`, `workspace_id`, `source_id`, `target_id`, `type`, `properties`, `created_at`.
- `GraphNodeCreate`
  - Create-node payload: `workspace_id`, `type`, `label`, `properties`.
- `GraphNodeUpdate`
  - Update-node payload: optional `label`, `type`, `properties`.
- `GraphEdgeCreate`
  - Create-edge payload: `workspace_id`, `source_id`, `target_id`, `type`, `properties`.
- `GraphData`
  - Workspace graph bundle: `nodes`, `edges`.
- `GraphQuery`
  - Query payload: `query`, `language` (`"natural"` or `"sparql"`), `limit`.
- `GraphQueryResult`
  - Query response: `nodes`, `edges`, optional `query_explanation`.

### Endpoints
- `GET /workspaces/{workspace_id}` → `GraphData`
  - Returns nodes (optionally filtered by `node_type`) and edges connected to those nodes within the workspace.
  - Query params: `node_type: str | None`, `limit: int (<=5000)`.
- `GET /nodes` → `list[GraphNode]`
  - Lists nodes for `workspace_id`, optionally filtered by `type`.
  - Query params: `workspace_id: str` (required), `type: str | None`, `limit (<=1000)`, `offset`.
- `POST /nodes` → `GraphNode`
  - Creates a node; generates `id` as `node-<12 hex>`, sets `created_at` and `updated_at` to current UTC (stored as tz-naive).
- `GET /nodes/{node_id}` → `GraphNode`
  - Fetches a node by its `nodeId` (no workspace access check performed here).
- `PUT /nodes/{node_id}` → `GraphNode`
  - Updates a node (replaces its RDF subject graph); updates `updated_at` (no workspace access check performed here).
- `DELETE /nodes/{node_id}` → `{"status": "deleted", "edges_deleted": int}`
  - Deletes the node and any connected edges found by `sourceId`/`targetId` match (no workspace access check performed here).
- `GET /edges` → `list[GraphEdge]`
  - Lists edges for `workspace_id`, optionally filtered by `type`.
  - Query params: `workspace_id: str` (required), `type: str | None`, `limit (<=1000)`, `offset`.
- `POST /edges` → `GraphEdge`
  - Creates an edge; verifies source and target nodes exist (by `nodeId`), generates `id` as `edge-<12 hex>`.
- `GET /edges/{edge_id}` → `GraphEdge`
  - Fetches an edge by its `edgeId` (no workspace access check performed here).
- `DELETE /edges/{edge_id}` → `{"status": "deleted"}`
  - Deletes an edge (no workspace access check performed here).
- `POST /query` → `GraphQueryResult`
  - Performs a workspace-scoped search over nodes (case-insensitive substring match on label/type); returns edges where **both** endpoints are within the matching node set.
  - Inputs: body `GraphQuery`, query param `workspace_id`.
  - Note: `language` is accepted but not used to switch behavior.
- `GET /statistics/{workspace_id}` → `dict[str, Any]`
  - Returns counts: `total_nodes`, `total_edges`, `nodes_by_type`, `edges_by_type`, `avg_degree`.

## Configuration/Dependencies
- Requires a `TripleStoreService` available as:
  - `request.app.state.triple_store`, or
  - fallback via `naas_abi.ABIModule.get_instance().engine.services.triple_store`.
- AuthN/AuthZ:
  - Router enforces `get_current_user_required`.
  - Some endpoints additionally enforce workspace access via `require_workspace_access(current_user.id, workspace_id)` (see Caveats for where it is missing).
- RDF storage conventions (RDF predicates/subjects):
  - Namespace: `urn:nexus:kg:` with types `NEXUS.Node`, `NEXUS.Edge`.
  - Subjects:
    - Node: `urn:nexus:workspace:{workspace_id}:node:{node_id}`
    - Edge: `urn:nexus:workspace:{workspace_id}:edge:{edge_id}`
  - Properties stored as JSON string literal under `urn:nexus:kg:properties`.
  - Timestamps stored as `xsd:dateTime` string (tz-naive, UTC-normalized if tz-aware input).

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import graph

app = FastAPI()
app.include_router(graph.router, prefix="/graph", tags=["graph"])
```

### Minimal client calls (HTTP)
```python
import requests

base = "http://localhost:8000/graph"
headers = {"Authorization": "Bearer <token>"}

# Create a node
node = requests.post(
    f"{base}/nodes",
    headers=headers,
    json={"workspace_id": "ws1", "type": "Person", "label": "Alice", "properties": {"role": "admin"}},
).json()

# Create another node and connect them
node2 = requests.post(
    f"{base}/nodes",
    headers=headers,
    json={"workspace_id": "ws1", "type": "Person", "label": "Bob", "properties": {}},
).json()

edge = requests.post(
    f"{base}/edges",
    headers=headers,
    json={"workspace_id": "ws1", "source_id": node["id"], "target_id": node2["id"], "type": "knows"},
).json()

# Get workspace graph
graph_data = requests.get(f"{base}/workspaces/ws1", headers=headers).json()
```

## Caveats
- Workspace access checks are **not** applied in:
  - `GET /nodes/{node_id}`, `PUT /nodes/{node_id}`, `DELETE /nodes/{node_id}`
  - `GET /edges/{edge_id}`, `DELETE /edges/{edge_id}`
  - These endpoints rely on authentication but do not call `require_workspace_access(...)`.
- `POST /query` accepts `language` (`natural`/`sparql`) but currently performs only a simple substring search over node label/type; it does not execute arbitrary SPARQL or use the `language` value.
- `properties` are stored as JSON-encoded strings; non-dict JSON (or invalid JSON) is read back as `{}`.
- Deletion of a node removes connected edges by querying for matching `sourceId`/`targetId`; edges are removed by deleting their entire subject graphs.
