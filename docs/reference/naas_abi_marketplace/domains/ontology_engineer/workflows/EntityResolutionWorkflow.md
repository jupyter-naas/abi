# EntityResolutionWorkflow

## What it is
A workflow that identifies potential duplicate RDF individuals (`owl:NamedIndividual`) by:
- Loading schema (TBox) and individuals (ABox) either from Turtle files or a triplestore.
- Finding each individual’s class types and class keys (`owl:hasKey`, including inherited keys via `rdfs:subClassOf`).
- Detecting duplicates using:
  - A business rule for key values equal to `"unknown"`.
  - Fuzzy matching (`thefuzz.fuzz.token_sort_ratio`) over key values.

It returns a report of duplicate pairs as `(keep, remove)`.

## Public API

### Classes

- `EntityResolutionWorkflowConfiguration(WorkflowConfiguration)`
  - **Purpose:** Provides dependencies for the workflow.
  - **Fields:**
    - `triple_store: ITripleStoreService` — service used for SPARQL queries when loading from the triplestore.

- `EntityResolutionWorkflowParameters(WorkflowParameters)`
  - **Purpose:** Runtime parameters controlling data loading and matching.
  - **Fields:**
    - `tbox_paths: Optional[List[str]]` — Turtle files to load schema from; if omitted, schema is loaded from triplestore.
    - `abox_paths: Optional[List[str]]` — Turtle files to load individuals from; if omitted, individuals are loaded from triplestore.
    - `similarity_threshold: int` — minimum score (0–100) to treat two entities as duplicates (default `100`).
    - `uri_prefix_filter: Optional[str]` — prefix filter when loading individuals from triplestore (default `"http://ontology.naas.ai/abi/"`).
    - `limit: Optional[int]` — limit on individuals loaded from triplestore.

- `EntityResolutionWorkflow(Workflow[EntityResolutionWorkflowParameters])`
  - **Purpose:** Runs entity resolution and returns duplicates.

### Methods (public)

- `run(parameters: EntityResolutionWorkflowParameters) -> dict`
  - **Purpose:** Executes the full workflow: load graphs, discover classes, query key values per class, detect duplicates.
  - **Returns:**
    - `classes: List[str]` — class URIs discovered from individuals.
    - `duplicates: List[{"keep": str, "remove": str}]` — duplicate pairs to merge/remove.
    - `summary: {"total_classes": int, "total_individuals": int, "total_duplicates": int}`

- `resolve_duplicate_entities(result_rows: List[ResultRow], similarity_threshold: int = 90) -> List[Tuple[URIRef, URIRef]]`
  - **Purpose:** Given SPARQL rows of `(individual_uri, key1, key2, ...)`, returns duplicate pairs.
  - **Rules:**
    - If multiple entities contain a key value `"unknown"` (case-insensitive), keep the first and mark the rest as duplicates.
    - For remaining entities, fuzzy-compare concatenated key values; if score ≥ threshold, mark later entity for removal.

- `get_classes_from_individuals_sparql(graph: Graph) -> List[URIRef]`
  - **Purpose:** Returns distinct `rdf:type` values found in the individuals graph, excluding types in the `owl:` namespace.

- `get_keys_for_class(graph: Graph, class_uri: URIRef) -> Optional[List[Node]]`
  - **Purpose:** Returns the list of predicates in `owl:hasKey` for the class (extracts from the RDF list), or `None`.

- `get_keys_for_class_recursive(graph: Graph, class_uri: URIRef, visited: Optional[Set[URIRef]] = None) -> Optional[List[Node]]`
  - **Purpose:** Looks up `owl:hasKey` for the class; if absent, checks parent classes via `rdfs:subClassOf` recursively (cycle-safe).

- `as_tools() -> list[BaseTool]`
  - **Purpose:** Exposes the workflow as a LangChain `StructuredTool` named `"resolve_duplicate_entities"` that invokes `run(...)`.

- `as_api(...) -> None`
  - **Purpose:** Stub; does not register any FastAPI routes (always returns `None`).

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation in `EntityResolutionWorkflowConfiguration` for triplestore loading.
- Uses:
  - `rdflib` for RDF graphs and SPARQL queries.
  - `thefuzz` for fuzzy matching.
  - `naas_abi_core.workflow.Workflow` base class.
- Input data expectations:
  - Individuals must be typed as `owl:NamedIndividual`.
  - Classes should define `owl:hasKey` (as an RDF list) for key-based matching.

## Usage

### Minimal example (load from local Turtle files)
```python
from naas_abi_marketplace.domains.ontology_engineer.workflows.EntityResolutionWorkflow import (
    EntityResolutionWorkflow,
    EntityResolutionWorkflowConfiguration,
    EntityResolutionWorkflowParameters,
)

# triple_store is still required by the configuration, even if you only use files.
# Provide a real ITripleStoreService from your environment.
triple_store = ...

workflow = EntityResolutionWorkflow(
    EntityResolutionWorkflowConfiguration(triple_store=triple_store)
)

result = workflow.run(
    EntityResolutionWorkflowParameters(
        tbox_paths=["path/to/schema.ttl"],
        abox_paths=["path/to/individuals.ttl"],
        similarity_threshold=100,
    )
)

print(result["summary"])
print(result["duplicates"])
```

### Example (load from triplestore)
```python
result = workflow.run(
    EntityResolutionWorkflowParameters(
        tbox_paths=None,
        abox_paths=None,
        uri_prefix_filter="http://ontology.naas.ai/abi/",
        limit=1000,
        similarity_threshold=95,
    )
)
```

## Caveats
- Duplicate detection only considers individuals that:
  - Are `owl:NamedIndividual`, and
  - Have all key predicates present in the individuals graph for the relevant class (the per-class query requires each key triple).
- The `"unknown"` business rule triggers when **any** key value equals `"unknown"` (case-insensitive).
- `similarity_threshold` default is `100` in parameters (exact match), which may yield no fuzzy duplicates unless keys are identical after normalization.
- `as_api(...)` is not implemented; no HTTP endpoints are exposed by this module.
