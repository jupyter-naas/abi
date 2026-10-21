# ontology.py (Ontology API endpoints)

## What it is
FastAPI router providing ontology-related endpoints:
- List OWL classes and object properties from registered ontology files.
- Compute overview statistics and build graph views (imports or class/property graph).
- Import (parse) reference ontologies from uploaded content (TTL parsing via regex).
- Export ontology files from the server filesystem.
- Create/delete in-memory “entity” and “relationship” items (not persisted).

All routes require authentication via `get_current_user_required`.

## Public API

### FastAPI router
- `router`: `APIRouter` with dependency `Depends(get_current_user_required)`.

### Pydantic models (request/response shapes)
- `OntologyItem`: Generic ontology item (id, name, type, description, example, parent info, timestamps).
- `ReferenceClass`, `ReferenceProperty`, `ReferenceOntology`: Parsed reference ontology structures.
- `OntologyFileItem`: Metadata for ontology files discovered from ABI modules.
- `OntologyOverviewStats`, `OntologyOverviewAggregateStats`: Count summaries.
- `OntologyTypeCounts`: Counts for `owl:DatatypeProperty` and `owl:NamedIndividual`.
- `OntologyOverviewGraphNode`, `OntologyOverviewGraphEdge`, `OntologyOverviewGraph`: Graph representation.
- `EntityCreate`: Request body for creating an in-memory entity.
- `RelationshipCreate`: Request body for creating an in-memory relationship.
- `ImportRequest`: Request body for importing reference ontology content.

### HTTP endpoints
Base path depends on how this router is mounted.

- `GET ""` → `list_ontology_items()`
  - Returns combined items from `list_classes()` and `list_relations()`.

- `GET "/classes"` → `list_classes(ontology_path: str | None)`
  - Lists OWL classes from one ontology file or all registered ontology files.
  - Uses `get_uri_metadata()` to populate label/definition/example/subClassOf.

- `GET "/relationships"` → `list_relations(ontology_path: str | None)`
  - Lists OWL object properties from one ontology file or all registered ontology files.
  - Uses `get_uri_metadata()` to populate label/definition/subPropertyOf.

- `GET "/overview/stats"` → `get_ontology_overview_stats(ontology_path: str)`
  - Counts classes, object properties, datatype properties, named individuals, imports for a single ontology file.

- `GET "/overview/stats/all"` → `get_all_ontologies_overview_stats()`
  - Aggregates stats by loading and counting across all registered ontology files (skips files that fail to load).

- `GET "/counts/types"` → `get_ontology_type_counts(ontology_path: str | None)`
  - Counts `owl:DatatypeProperty` and `owl:NamedIndividual` across one or all ontology files.

- `GET "/overview/graph"` → `get_ontology_overview_graph(ontology_path: str | None)`
  - If `ontology_path` is provided: returns a graph of classes (nodes) and object-property domain/range relations (edges).
  - If omitted: returns an ontology import dependency graph derived from `owl:imports` across all loaded graphs.

- `POST "/entity"` → `create_entity(data: EntityCreate)`
  - Creates an in-memory `OntologyItem` with type `"entity"`.

- `POST "/relationship"` → `create_relationship(data: RelationshipCreate)`
  - Creates an in-memory `OntologyItem` with type `"relationship"`.

- `DELETE "/{item_id}"` → `delete_item(item_id: str)`
  - Deletes matching items from in-memory list.

- `POST "/import"` → `import_reference_ontology(request: ImportRequest)`
  - Parses uploaded content; currently uses `parse_ttl()` for `.ttl` and also as a fallback for other extensions.
  - Returns `ReferenceOntology` as a dict.

- `GET "/ontologies"` → `list_ontology_files()`
  - Enumerates ontology files from `ABIModule.get_instance().ontologies` plus module ontologies.
  - Filters out paths containing `"sandbox"` or missing `"modules"`.
  - Parses each ontology as Turtle and extracts metadata from the `owl:Ontology` subject.

- `GET "/export"` → `export_ontology_file(ontology_path: str)`
  - Serves a file from the server filesystem as an attachment (404 if not found).

### Internal helpers (module-level)
- `get_triple_store_service() -> TripleStoreService`
- `_load_ontology_graph(ontology_path: str, add_imports: bool = False) -> rdflib.Graph`
- `_resolve_target_ontology_paths(ontology_path: str | None, ontologies: list[OntologyFileItem]) -> list[str]`
- `parse_ttl(content: str, file_path: str) -> ReferenceOntology`
- `get_uri_metadata(uri: str) -> dict` (cached for 1 day)
- `get_ontology_metadata(ontology_iri: str) -> dict`
- `_compute_ontology_stats_for_graph(graph: Graph) -> tuple[int, int, int, int, int]`

## Configuration/Dependencies
- **FastAPI**: `APIRouter`, `Depends`, `HTTPException`, `Query`, `FileResponse`.
- **Authentication**: `get_current_user_required` dependency is enforced on all routes.
- **ABI runtime**:
  - `ABIModule.get_instance()` is used to access:
    - `engine.services.triple_store` for SPARQL querying (`get_uri_metadata`, `get_ontology_metadata`).
    - `ontologies` lists used by `list_ontology_files`.
- **Caching**:
  - `CacheFactory.CacheFS_find_storage(subpath="nexus/ontology")`
  - `get_uri_metadata` is cached as JSON with TTL = 1 day (`DataType.JSON`).
- **RDF parsing**: `rdflib.Graph` plus namespaces (`OWL`, `RDF`, `RDFS`).
- **Filesystem access**:
  - `export_ontology_file` reads server paths.
  - `list_ontology_files` parses ontology files via their path strings (expected to be readable from the server).

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import ontology

app = FastAPI()
app.include_router(ontology.router, prefix="/ontology", tags=["ontology"])
```

### Example requests (assuming authentication handled elsewhere)
```python
import requests

base = "http://localhost:8000/ontology"

# List all classes across registered ontologies
r = requests.get(f"{base}/classes")
print(r.json())

# Get stats for a specific ontology file path
r = requests.get(f"{base}/overview/stats", params={"ontology_path": "/path/to/file.ttl"})
print(r.json())

# Export a file
r = requests.get(f"{base}/export", params={"ontology_path": "/path/to/file.ttl"})
open("file.ttl", "wb").write(r.content)
```

## Caveats
- `create_entity`, `create_relationship`, and `delete_item` operate on an in-memory list (`ontology_items`) and are not persisted.
- `import_reference_ontology` uses regex-based TTL parsing (`parse_ttl`); non-`.ttl` formats are currently treated as “TTL-like” and may not parse correctly.
- Many list/graph endpoints load ontology files from paths returned by `list_ontology_files`; missing/unreadable files can cause errors (some aggregation paths skip failures, others raise 500).
- `get_uri_metadata` and `get_ontology_metadata` query a specific named graph: `GRAPH <http://ontology.naas.ai/graph/schema>`; results depend on triple-store contents and may not match the file-parsed graph.
