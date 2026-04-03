# AIAgentOntologyGenerationPipeline

## What it is
A pipeline that:
- Loads the latest **Artificial Analysis** LLM JSON dataset from a datastore folder
- Groups models into AI-agent “modules” (e.g., `chatgpt`, `claude`, `llama`) using name/slug/provider heuristics
- Generates **TTL ontology files** per agent (BFO-structured content as strings)
- Writes outputs into a **timestamped datastore directory** and also **deploys a “current” TTL into module ontologies folders**
- Inserts a small summary `rdflib.Graph` (file count + timestamp) into a configured triple store

## Public API

### Classes

- `AIAgentOntologyGenerationConfiguration(PipelineConfiguration)`
  - Configuration for the pipeline.
  - Fields:
    - `triple_store: ITripleStoreService` (required) - target triple store service used to `insert(Graph)`
    - `datastore_path: str` - output root for generated ontologies (timestamped subfolders)
    - `source_datastore_path: str` - input folder containing `*_llms_data.json` files
    - `max_models_per_agent: int` - cap per agent for performance

- `AIAgentOntologyGenerationParameters(PipelineParameters)`
  - Execution parameters.
  - Fields:
    - `force_regenerate: bool` - defined but not used in current implementation
    - `agent_filter: Optional[List[str]]` - restrict generation to specific agent modules (keys like `["chatgpt","claude"]`)

- `AIAgentOntologyGenerationPipeline(Pipeline)`
  - Main pipeline implementation.

### Methods (intended for external use)

- `AIAgentOntologyGenerationPipeline.run(parameters: PipelineParameters) -> rdflib.Graph`
  - Runs the pipeline end-to-end.
  - Validates parameter type (`AIAgentOntologyGenerationParameters`).
  - Loads latest AA dataset, generates/deploys TTL files, writes a JSON summary file, inserts a summary graph into the triple store, and returns that graph.

- `AIAgentOntologyGenerationPipeline.as_tools() -> list[BaseTool]`
  - Exposes the pipeline as a LangChain `StructuredTool` named `ai_agent_ontology_generation`.
  - Tool calls `run(AIAgentOntologyGenerationParameters(**kwargs))`.

- `AIAgentOntologyGenerationPipeline.as_api(...) -> None`
  - Present but currently does nothing (returns `None`).

- `AIAgentOntologyGenerationPipeline.get_configuration() -> AIAgentOntologyGenerationConfiguration`
  - Returns the pipeline configuration instance.

## Configuration/Dependencies

### Required dependencies
- `rdflib` (`Graph`, `Literal`, `Namespace`) - graph returned/inserted, though TTL is generated as plain text files.
- `naas_abi_core.pipeline` - base `Pipeline`, `PipelineConfiguration`, `PipelineParameters`.
- `naas_abi_core.services.triple_store.TripleStorePorts.ITripleStoreService`
  - Must provide an `insert(graph: Graph)` method.
- `langchain_core.tools` - for `as_tools()` (`BaseTool`, `StructuredTool`).

### Filesystem inputs/outputs
- **Input**: latest file matching `*_llms_data.json` in `source_datastore_path`.
- **Output**: under `datastore_path/<UTC_TIMESTAMP>/`
  - `<AgentTitle>Ontology.ttl` (current)
  - `<UTC_TIMESTAMP>_<AgentTitle>Ontology.ttl` (audit copy)
  - `generation_summary_<UTC_TIMESTAMP>.json`
- **Deployment output**: also writes `<AgentTitle>Ontology.ttl` into:
  - `Path(__file__).parent.parent.parent / <agent_module> / "ontologies" / <AgentTitle>Ontology.ttl`

## Usage

```python
from naas_abi.pipelines.AIAgentOntologyGenerationPipeline import (
    AIAgentOntologyGenerationPipeline,
    AIAgentOntologyGenerationConfiguration,
    AIAgentOntologyGenerationParameters,
)

# Minimal triple store stub for demonstration
class TripleStoreStub:
    def insert(self, graph):
        pass

pipeline = AIAgentOntologyGenerationPipeline(
    AIAgentOntologyGenerationConfiguration(
        triple_store=TripleStoreStub(),
        source_datastore_path="storage/datastore/core/modules/abi/ArtificialAnalysisWorkflow",
        datastore_path="storage/datastore/core/modules/abi/AIAgentOntologyGenerationPipeline",
        max_models_per_agent=50,
    )
)

graph = pipeline.run(
    AIAgentOntologyGenerationParameters(agent_filter=["chatgpt", "claude"])
)

print(len(graph))  # summary triples count
```

## Caveats
- `force_regenerate` parameter is currently unused.
- The LangChain tool description states “datastore only, no module deployment”, but `run()` **does deploy** TTL files into module folders.
- Module deployment path is derived from `__file__` by going up 3 directories; this assumes a specific repo/layout and may write files into unexpected locations depending on installation.
- Ontology TTL content is written as text and is not parsed/validated before writing.
- If no `*_llms_data.json` exists (or source directory missing), `run()` raises `ValueError`.
