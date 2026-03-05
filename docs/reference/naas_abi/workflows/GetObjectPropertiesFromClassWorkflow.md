# GetObjectPropertiesFromClassWorkflow

## What it is
- A workflow that loads an OWL ontology (from a Turtle file or from a triple store schema graph) and returns **OWL object properties** whose **domain** matches a given **class URI**.
- Outputs object properties with their labels and **range** information, including basic handling of complex OWL class expressions (`unionOf`, `intersectionOf`, `complementOf`) mapped to logical operators (`or`, `and`, `not`).

## Public API

### Configuration
- `GetObjectPropertiesFromClassWorkflowConfiguration(WorkflowConfiguration)`
  - `triple_store: ITripleStoreService` — triple store service used when `ontology_file_path` is not provided.
  - `ontology_file_path: Optional[str] = None` — path to a Turtle ontology file to parse with RDFLib.

### Parameters
- `GetObjectPropertiesFromClassWorkflowParameters(WorkflowParameters)`
  - `class_uri: str` — required; must match pattern `^http.*`.

### Workflow
- `GetObjectPropertiesFromClassWorkflow(Workflow)`
  - `get_object_properties_from_class(parameters) -> dict`
    - Validates the URI is an `owl:Class`.
    - Finds all `owl:ObjectProperty` in the graph.
    - Selects those whose (mapped) domain contains the class URI (supports simple `or` / `and` dict structures).
    - Returns:
      - `{"class_uri": ..., "object_properties": [{"object_property_uri", "object_property_label", "ranges"}...]}`

  - `as_tools() -> list[BaseTool]`
    - Exposes the workflow as a LangChain `StructuredTool` named `get_object_properties_from_class`.

  - `as_api(...) -> None`
    - Present but not implemented (always returns `None`).

### Helper methods (non-API but callable)
- `get_linked_classes(cls_id, rel_type=None)`
  - Recursively expands OWL list structures and class expression nodes for `unionOf`, `intersectionOf`, `complementOf`.
- `map_ranges_domains(x)`
  - Maps `domain`/`range` items: if not an HTTP URI, attempts to expand via `get_linked_classes`.
- `is_class(uri) -> bool`
  - Checks `(uri, rdf:type, owl:Class)` membership in the graph.
  - **Prints** the entire graph serialized as Turtle (side-effect).
- `_class_matches_domain(class_uri, domains) -> bool`
  - Checks whether the class is in a domain list or inside simple `{"or": [...]}` / `{"and": [...]}`.
- `_process_ranges(ranges) -> list`
  - Converts range URIs into `{"uri": ..., "label": ...}` and recurses through `or/and/not` structures.

## Configuration/Dependencies
- Requires:
  - `rdflib` (`Graph`, `URIRef`, `RDF`, `RDFS`, `OWL`)
  - `pydash`
  - `pydantic` (for parameter validation)
  - `langchain_core.tools` (for `as_tools`)
  - `naas_abi_core` workflow base classes and `ITripleStoreService`
- Ontology source:
  - If `ontology_file_path` is set: `Graph.parse(..., format="turtle")`
  - Else: `configuration.triple_store.get_schema_graph()` must return an RDFLib-like graph.

## Usage

### Direct workflow call
```python
from naas_abi.workflows.GetObjectPropertiesFromClassWorkflow import (
    GetObjectPropertiesFromClassWorkflow,
    GetObjectPropertiesFromClassWorkflowConfiguration,
    GetObjectPropertiesFromClassWorkflowParameters,
)

# Provide an ITripleStoreService instance from your environment
triple_store_service = ...

wf = GetObjectPropertiesFromClassWorkflow(
    GetObjectPropertiesFromClassWorkflowConfiguration(
        triple_store=triple_store_service,
        ontology_file_path=None,  # or "path/to/ontology.ttl"
    )
)

result = wf.get_object_properties_from_class(
    GetObjectPropertiesFromClassWorkflowParameters(
        class_uri="http://purl.obolibrary.org/obo/BFO_0000015"
    )
)

print(result["class_uri"])
print(len(result["object_properties"]))
```

### As a LangChain tool
```python
tools = wf.as_tools()
tool = tools[0]
out = tool.run({"class_uri": "http://purl.obolibrary.org/obo/BFO_0000015"})
print(out)
```

## Caveats
- `is_class()` prints the entire graph serialized as Turtle, which can be very large and noisy.
- Class-expression support is limited to `unionOf`, `intersectionOf`, `complementOf` structures discovered via internal preprocessing; domain matching only checks for:
  - exact string match, or
  - membership in simple `{"or": [...]}` / `{"and": [...]}` dicts (no deeper semantic reasoning).
- `as_api()` is a stub and does not register any routes.
