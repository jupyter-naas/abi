# NexusPlatformPipeline

## What it is
- A `Pipeline` that initializes the Nexus platform RDF named graph by:
  - registering all available named graphs as `KnowledgeGraph` instances,
  - registering runtime agents (from loaded ABI modules) as `Agent` instances,
  - creating a default `GraphView` (currently an “Agent” view).
- Writes all produced triples into the configured Nexus named graph via `TripleStoreService`.

## Public API

### Configuration / Parameters
- `NexusPlatformPipelineConfiguration(PipelineConfiguration)`
  - `triple_store: TripleStoreService` (required): triple store adapter/service.
  - `nexus_namespace: Namespace` (default: `http://ontology.naas.ai/nexus/`)
  - `nexus_graph_uri: URIRef` (default: `http://ontology.naas.ai/graph/nexus`)
  - `force_update: bool` (default: `True`): if `True`, clears the Nexus graph during initialization.
- `NexusPlatformPipelineParameters(PipelineParameters)`
  - No fields; used only for type checking.

### Pipeline
- `class NexusPlatformPipeline(Pipeline)`
  - `list_nexus_graphs() -> List[Dict]`
    - Lists `KnowledgeGraph` instances currently stored in the Nexus graph.
  - `initialize_nexus_graphs() -> rdflib.Graph`
    - Ensures each named graph known to the triple store (plus the Nexus graph itself) is represented as a `KnowledgeGraph` instance in the Nexus graph.
  - `list_nexus_agents(metadata: dict[str, URIRef] = {}) -> List[Dict]`
    - Lists `Agent` instances in the Nexus graph; optional metadata fields are retrieved via OPTIONAL patterns.
  - `initialize_nexus_agents() -> rdflib.Graph`
    - Creates several `AgentRole` instances and registers runtime agents discovered from loaded ABI modules into the Nexus graph.
  - `list_nexus_graph_views(metadata: dict[str, URIRef] = {}) -> List[Dict]`
    - Lists `GraphView` instances in the Nexus graph.
  - `initialize_nexus_graph_views() -> rdflib.Graph`
    - Creates a `GraphView` labeled `"Agent"` using a `GraphFilter` matching `rdf:type Agent`.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Type-checks parameters (`NexusPlatformPipelineParameters`) and runs all three initialization steps; returns the combined `rdflib.Graph`.
  - `as_tools() -> list[BaseTool]`
    - Returns an empty list.
  - `as_api(...) -> None`
    - No-op (Nexus initialization is handled during engine startup).

## Configuration/Dependencies
- Requires:
  - `naas_abi_core.services.triple_store.TripleStoreService` for graph list/create/clear/query/insert.
  - `naas_abi.ontologies.modules.NexusPlatformOntology` classes (`Agent`, `KnowledgeGraph`, `GraphView`, etc.) to generate RDF.
  - `rdflib` for RDF graphs (`Graph`, `Namespace`, `URIRef`) and common namespaces.
- Side effects during `__init__`:
  - Creates the Nexus named graph if missing.
  - If `force_update=True`, clears the Nexus named graph.

## Usage

```python
from naas_abi_core.engine.Engine import Engine
from naas_abi.pipelines.NexusPlatformPipeline import (
    NexusPlatformPipeline,
    NexusPlatformPipelineConfiguration,
    NexusPlatformPipelineParameters,
)

engine = Engine()
engine.load(module_names=["naas_abi"])
store = engine.services.triple_store

pipeline = NexusPlatformPipeline(
    NexusPlatformPipelineConfiguration(triple_store=store, force_update=True)
)
graph = pipeline.run(NexusPlatformPipelineParameters())

print(graph.serialize(format="turtle"))
```

## Caveats
- `force_update=True` clears the Nexus named graph on startup; use with care in persistent environments.
- `initialize_nexus_agents()` prints the inserted RDF (`turtle`) to stdout (`print(...)`), which may be noisy in production logs.
- Agent discovery depends on the ABI engine/module loading (`ABIModule.get_instance()`, `engine.modules`); if modules aren’t loaded, few or no agents will be registered.
