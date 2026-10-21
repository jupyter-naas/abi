# CreateClassOntologyYamlWorkflow

## What it is
A workflow that:
- Builds an RDFLib `Graph` from all triples of individuals of a given RDF class (`class_uri`) stored in a triple store.
- Enriches the graph with `rdfs:label` and `rdf:type` (plus `owl:NamedIndividual`) for ABI URIs found as objects.
- Serializes the graph to Turtle and delegates YAML creation + push to Naas workspace to `ConvertOntologyGraphToYamlWorkflow`.

It also provides a `trigger(...)` hook intended for triple-store insert events, with a hard-coded allowlist of class URIs.

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
    - Creates:
      - `SPARQLUtils` bound to the provided triple store
      - a `ConvertOntologyGraphToYamlWorkflow` for downstream conversion
  - `trigger(event: OntologyEvent, triple: tuple[Any, Any, Any]) -> str | None`
    - On insert-like events (checked by string comparison to `OntologyEvent.INSERT`), derives the class URI from the inserted subject (treated as an individual URI) using `SPARQLUtils.get_class_uri_from_individual_uri(s)`.
    - Only runs conversion for these class URIs:
      - `https://www.commoncoreontologies.org/ont00001262` (Person)
      - `https://www.commoncoreontologies.org/ont00000443` (Commercial Organization)
    - Returns the downstream `ontology_id` on success, otherwise `None`.
  - `graph_to_yaml(parameters: CreateClassOntologyYamlWorkflowParameters) -> str`
    - Queries the triple store to:
      - Fetch `rdfs:label` and `skos:definition` for `class_uri` (used as label/description; empty strings if missing).
      - Fetch all triples for all individuals of the class: `?subject a <class_uri> . ?subject ?predicate ?object`.
    - Adds those triples to an RDFLib graph:
      - Objects that are `str` starting with `http://ontology.naas.ai/abi/` are treated as `URIRef` and collected for enrichment.
      - All other objects are stored as RDF literals.
    - For collected ABI URIs, queries their `rdfs:label` and `rdf:type`, and adds:
      - `?object rdf:type ?type`
      - `?object rdf:type owl:NamedIndividual`
      - `?object rdfs:label ?label`
    - Serializes the graph to Turtle and calls `ConvertOntologyGraphToYamlWorkflow.graph_to_yaml(...)`.
    - Returns the resulting `ontology_id`.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool`:
      - Name: `ontology_create_class_yaml`
      - Args schema: `CreateClassOntologyYamlWorkflowParameters`
      - Calls `graph_to_yaml(...)`.
  - `as_api(...) -> None`
    - No-op (returns immediately; does not register routes).

## Configuration/Dependencies
- Requires:
  - `ITripleStoreService` providing `query(query: str)` returning iterable SPARQL rows (`rdflib.query.ResultRow` compatible in usage here).
  - `ConvertOntologyGraphToYamlWorkflowConfiguration` for downstream conversion.
- Uses:
  - `SPARQLUtils` (`get_class_uri_from_individual_uri`, `results_to_list`)
  - `rdflib` (`Graph`, `URIRef`, `Literal`, `RDF`, `RDFS`, `OWL`)
  - `langchain_core.tools.StructuredTool`

## Usage

### Convert a class to YAML
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
  - Only proceeds when `event` string-matches `OntologyEvent.INSERT`.
  - Skips if the triple’s object does not start with `"http"` or is exactly `owl:NamedIndividual`.
  - Only triggers for two hard-coded class URIs (Person, Commercial Organization).
- Object handling in `graph_to_yaml(...)`:
  - Only `str` objects starting with `http://ontology.naas.ai/abi/` are treated as URIs; everything else becomes an RDF literal.
- `as_api(...)` does nothing and exposes no HTTP endpoints.
