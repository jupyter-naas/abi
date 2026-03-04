# `ontology` API Endpoints

## What it is
FastAPI endpoints and Pydantic models for:
- Managing in-memory ontology items (entities and relationships).
- Importing and previewing reference ontologies from uploaded text content (currently parsed as Turtle/TTL via regex).
- Serving a bundled BFO7 Buckets TTL reference file from the server.

All routes are protected by a required authentication dependency.

## Public API

### FastAPI router
- `router: APIRouter`
  - Configured with `Depends(get_current_user_required)` for all routes.

### Pydantic models
- `OntologyItem`
  - Represents an ontology item stored in memory.
- `ReferenceClass`
  - Parsed class from a reference ontology (IRI, label, optional definition/examples).
- `ReferenceProperty`
  - Parsed object property from a reference ontology (IRI, label, optional definition).
- `ReferenceOntology`
  - Parsed reference ontology (metadata + lists of classes and properties).
- `EntityCreate`
  - Request body for creating an entity.
- `RelationshipCreate`
  - Request body for creating a relationship.
- `ImportRequest`
  - Request body for import/preview: `content` (text) and `filename` (validated with a regex pattern).

### Functions
- `parse_ttl(content: str, file_path: str) -> ReferenceOntology`
  - Parses TTL/Turtle-like content using regex to extract:
    - `owl:Class` blocks (`rdfs:label`, `skos:definition`, `skos:example`)
    - `owl:ObjectProperty` blocks (`rdfs:label`, `skos:definition`)
    - Ontology name from `dc:title` or falls back to filename.

### Endpoints
- `GET ""` → `list_ontology_items()`
  - Returns `{"items": ontology_items}` (in-memory list).
- `POST "/entity"` → `create_entity(data: EntityCreate)`
  - Creates an `OntologyItem` with `type="entity"` and appends to memory.
- `POST "/relationship"` → `create_relationship(data: RelationshipCreate)`
  - Creates an `OntologyItem` with `type="relationship"`; stores `base_property` into `base_class` field.
- `DELETE "/{item_id}"` → `delete_item(item_id: str)`
  - Removes matching item(s) from memory; returns `{"success": True}`.
- `POST "/import"` → `import_reference_ontology(request: ImportRequest)`
  - Parses `request.content` based on `request.filename` extension (currently always `parse_ttl`).
  - Returns `ReferenceOntology` as a dict (`model_dump()`).
- `POST "/import/preview"` → `preview_ontology_file(request: ImportRequest)`
  - Parses content and returns counts + first 5 classes/properties (serialized).
- `GET "/reference/bfo7"` → `get_bfo7_reference()`
  - Loads `ontology/BFO7Buckets.ttl` from the repo and returns parsed ontology as a dict.

## Configuration/Dependencies
- **FastAPI**: `APIRouter`, `Depends`, `HTTPException`
- **Auth dependency**: `get_current_user_required` is applied to the router globally.
- **Parsing**: Uses `re` regex parsing; not a full RDF/OWL parser.
- **Storage**: Module-level mutable list `ontology_items: list[OntologyItem]` (in-memory).
- **Bundled file**: `GET /reference/bfo7` expects a TTL file at:
  - `<repo-root>/ontology/BFO7Buckets.ttl`
  - Repo root is inferred by walking up from `__file__` until a directory named `apps` is found (up to 6 levels), otherwise uses `parents[4]` as fallback.

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints.ontology import router as ontology_router

app = FastAPI()
app.include_router(ontology_router, prefix="/ontology", tags=["ontology"])
```

### Minimal parsing example (no server required)
```python
from naas_abi.apps.nexus.apps.api.app.api.endpoints.ontology import parse_ttl

ttl = '''
<http://example.org/MyClass> a owl:Class ;
  rdfs:label "My Class" ;
  skos:definition "A demo class" .

<http://example.org/relatesTo> rdf:type owl:ObjectProperty ;
  rdfs:label "relates to" .
dc:title "Demo Ontology"
'''

ref = parse_ttl(ttl, "demo.ttl")
print(ref.name, len(ref.classes), len(ref.properties))
```

## Caveats
- **In-memory storage only**: `ontology_items` is process-local and resets on restart; not safe for multi-worker deployments.
- **Non-deterministic timestamps**: `created_at`/`updated_at` default to `datetime.now()` at model import time (due to direct assignment), not at instance creation time.
- **Naive TTL parsing**: Regex-based extraction may miss valid Turtle constructs and does not resolve prefixes; other formats are currently treated as “TTL-like”.
- **ID generation**: IDs are timestamp-based (`int(datetime.now().timestamp() * 1000)`), which can collide under high concurrency.
- **`create_relationship` mapping**: `base_property` is stored in `OntologyItem.base_class` (field reuse).
