# CreateClassOntologyYamlWorkflow

## What it is
A workflow that:
- Builds an RDFLib `Graph` from all triples of individuals of a given RDF class (`class_uri`) from a triple store.
- Enriches the graph with `rdfs:label` and `rdf:type` (plus `owl:NamedIndividual`) for ABI URIs found as objects.
- Delegates conversion of the graph to YAML (and pushing to a Naas workspace) to `ConvertOntologyGraphToYamlWorkflow`.

It also includes a trigger hook to run automatically on certain triple-store insert events for an allowlist of class URIs.

## Public API

### Classes

- `CreateClassOntologyYamlWorkflowConfiguration(WorkflowConfiguration)`
  - Holds dependencies:
    - `triple_store: ITripleStoreService` — SPARQL query interface.
    - `convert_ontology_graph_config: ConvertOntologyGraphToYamlWorkflowConfiguration` — downstream workflow configuration.

- `CreateClassOntologyYamlWorkflowParameters(WorkflowParameters)`
  - Parameters:
    - `class_uri: str` — URI of the RDF class to convert to YAML.

- `CreateClassOntologyYamlWorkflow(Workflow)`
  - `__init__(configuration: CreateClassOntologyYamlWorkflowConfiguration)`
    - Instantiates `ConvertOntologyGraphToYamlWorkflow` and `SPARQLUtils` using the provided triple store.
  - `trigger(event: OntologyEvent, triple: tuple[Any, Any, Any]) -> str | None`
    - On `OntologyEvent.INSERT`, attempts to derive a class URI from the inserted subject URI.
    - Only triggers YAML creation for:
      - `https://www.commoncoreontologies.org/ont00001262` (Person)
      - `https://www.commoncoreontologies.org/ont00000443` (Commercial Organization)
    - Returns an ontology id (`str`) if triggered, else `None`.
  - `graph_to_yaml(parameters: CreateClassOntologyYamlWorkflowParameters) -> str`
    - Queries the triple store to:
      - Fetch `rdfs:label` and `skos:definition` for the `class_uri` (used as label/description).
      - Fetch all triples for all individuals of the class (`?subject a <class_uri>; ?predicate ?object`) and add them to an RDFLib graph.
      - For object values that are ABI URIs (`str` starting with `http://ontology.naas.ai/abi/`), query and add their `rdfs:label` and `rdf:type`, plus `owl:NamedIndividual`.
    - Serializes the graph to Turtle and calls `ConvertOntologyGraphToYamlWorkflow.graph_to_yaml(...)`.
    - Returns the resulting ontology id.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool`:
      - Name: `ontology_create_class_yaml`
      - Args schema: `CreateClassOntologyYamlWorkflowParameters`
      - Function: calls `graph_to_yaml(...)`.
  - `as_api(...) -> None`
    - No-op (returns immediately; does not register routes).

## Configuration/Dependencies
- Triple store:
  - `ITripleStoreService` with `.query(query: str)` returning iterable SPARQL result rows.
- Downstream workflow:
  - `ConvertOntologyGraphToYamlWorkflow` configured via `ConvertOntologyGraphToYamlWorkflowConfiguration`.
- Utilities/libraries:
  - `SPARQLUtils` (used for `get_class_uri_from_individual_uri` and `results_to_list`).
  - `rdflib` (`Graph`, `URIRef`, `Literal`, and `RDF`/`RDFS`/`OWL` constants).
  - `langchain_core.tools.StructuredTool`.

## Usage

### Run conversion for a class URI
```python
from naas_abi_marketplace.applications.naas.workflows.CreateClassOntologyYamlWorkflow import (
    CreateClassOntologyYamlWorkflow,
    CreateClassOntologyYamlWorkflowConfiguration,
    CreateClassOntologyYamlWorkflowParameters,
)

triple_store = ...  # ITripleStoreService implementation
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
- `trigger(...)`:
  - Only runs on `OntologyEvent.INSERT`.
  - Skips events where the object does not start with `"http"` or equals `owl:NamedIndividual`.
  - Only triggers for two hard-coded class URIs (Person, Commercial Organization).
- Object handling in `graph_to_yaml(...)`:
  - Only `str` objects starting with `http://ontology.naas.ai/abi/` are treated as URIs; all other values are stored as RDF literals.
- The ABI object enrichment query uses `rdf:type` but does not declare an `rdf:` prefix in the SPARQL query string.
- `as_api(...)` returns immediately and does not expose HTTP endpoints.
