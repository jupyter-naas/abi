# CreateClassOntologyYamlWorkflow

## What it is
A workflow that:
- Builds an RDF graph from all triples of individuals of a given RDF class (by `class_uri`),
- Enriches the graph with labels/types for ABI URIs found as objects,
- Delegates conversion of that graph to YAML (and push to Naas workspace) to `ConvertOntologyGraphToYamlWorkflow`.

It also includes a trigger hook to automatically run for specific class URIs on triple-store insert events.

## Public API

### Classes

- `CreateClassOntologyYamlWorkflowConfiguration(WorkflowConfiguration)`
  - Holds dependencies:
    - `triple_store: ITripleStoreService`
    - `convert_ontology_graph_config: ConvertOntologyGraphToYamlWorkflowConfiguration`

- `CreateClassOntologyYamlWorkflowParameters(WorkflowParameters)`
  - Parameters:
    - `class_uri: str` — URI of the RDF class to convert to YAML.

- `CreateClassOntologyYamlWorkflow(Workflow)`
  - `__init__(configuration: CreateClassOntologyYamlWorkflowConfiguration)`
    - Wires the triple store SPARQL utilities and the downstream conversion workflow.
  - `trigger(event: OntologyEvent, triple: tuple[Any, Any, Any]) -> str | None`
    - On `OntologyEvent.INSERT`, attempts to derive a class URI from the inserted subject (treated as an individual URI).
    - Only triggers YAML creation for a fixed allowlist of class URIs:
      - `https://www.commoncoreontologies.org/ont00001262` (Person)
      - `https://www.commoncoreontologies.org/ont00000443` (Commercial Organization)
    - Returns an ontology id (string) on success, otherwise `None`.
  - `graph_to_yaml(parameters: CreateClassOntologyYamlWorkflowParameters) -> str`
    - Queries the triple store to:
      - Fetch `rdfs:label` and `skos:definition` for `class_uri` (used as label/description).
      - Fetch all triples `?subject a <class_uri> ; ?predicate ?object` and add them to an RDFLib `Graph`.
      - For any object that is a string starting with `http://ontology.naas.ai/abi/`, treat it as a URI and additionally query for its `rdfs:label` and `rdf:type`, adding those to the graph (plus `owl:NamedIndividual`).
    - Serializes the graph to Turtle and calls `ConvertOntologyGraphToYamlWorkflow.graph_to_yaml(...)`.
    - Returns the resulting ontology id.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool`:
      - Name: `ontology_create_class_yaml`
      - Args schema: `CreateClassOntologyYamlWorkflowParameters`
      - Calls `graph_to_yaml(...)`.
  - `as_api(...) -> None`
    - Currently a no-op; returns `None` immediately and does not register routes.

## Configuration/Dependencies
- Requires a triple store implementation:
  - `ITripleStoreService` (must support `.query(query: str)`).
- Requires configuration for downstream conversion:
  - `ConvertOntologyGraphToYamlWorkflowConfiguration`
- Uses:
  - `SPARQLUtils` (for `get_class_uri_from_individual_uri` and results conversion),
  - `rdflib` (`Graph`, `URIRef`, `Literal`, RDF/RDFS/OWL constants),
  - `langchain_core.tools.StructuredTool`.

## Usage

### Run conversion for a class URI
```python
from naas_abi_marketplace.applications.naas.workflows.CreateClassOntologyYamlWorkflow import (
    CreateClassOntologyYamlWorkflow,
    CreateClassOntologyYamlWorkflowConfiguration,
    CreateClassOntologyYamlWorkflowParameters,
)

# Provide concrete implementations/configs from your environment:
triple_store = ...  # ITripleStoreService
convert_cfg = ...   # ConvertOntologyGraphToYamlWorkflowConfiguration

wf = CreateClassOntologyYamlWorkflow(
    CreateClassOntologyYamlWorkflowConfiguration(
        triple_store=triple_store,
        convert_ontology_graph_config=convert_cfg,
    )
)

ontology_id = wf.graph_to_yaml(
    CreateClassOntologyYamlWorkflowParameters(
        class_uri="https://www.commoncoreontologies.org/ont00001262"
    )
)
print(ontology_id)
```

### Use as a LangChain tool
```python
tool = wf.as_tools()[0]
result = tool.run({"class_uri": "https://www.commoncoreontologies.org/ont00001262"})
print(result)
```

## Caveats
- `trigger(...)` only runs on `OntologyEvent.INSERT` and only for two hard-coded class URIs (Person, Commercial Organization).
- Objects are treated as ABI URIs only if they are `str` and start with `http://ontology.naas.ai/abi/`; everything else is stored as an RDF literal.
- `as_api(...)` does nothing (early `return None`), so no HTTP endpoints are exposed from this module.
