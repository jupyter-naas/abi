# `pipelines/` — AGENTS.md

> Scope: data pipelines for the `{{module_name_snake}}` module. See the module's [AGENTS.md](../AGENTS.md) for module-wide context.

## What goes here

Steps that **produce RDF Graphs**. Pipelines extract / transform / enrich data from integrations and emit triples that downstream agents and services reason over (via the `triple_store` service).

Pipelines differ from **workflows** in their output contract:
- **Pipeline** — always returns an `rdflib.Graph`.
- **Workflow** — returns dicts / typed objects.

If your output isn't RDF, use a workflow instead.

## File shape

Files are `PascalCase`, one pipeline per file: `<Name>Pipeline.py`.

```python
from dataclasses import dataclass
from typing import Annotated
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import (
    Pipeline, PipelineConfiguration, PipelineParameters,
)
from pydantic import Field
from rdflib import DCTERMS, OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef

@dataclass
class <Name>PipelineConfiguration(PipelineConfiguration):
    """Configuration for <Name>Pipeline."""
    pass

class <Name>PipelineParameters(PipelineParameters):
    """Run-time inputs."""
    target: Annotated[str, Field(..., description="What to ingest")]

class <Name>Pipeline(Pipeline[<Name>PipelineParameters]):
    """One-line description."""

    __configuration: <Name>PipelineConfiguration

    def __init__(self, configuration: <Name>PipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: <Name>PipelineParameters) -> Graph:
        g = Graph()
        # populate g with triples
        return g

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(
                func=self.run,
                name="<Name>",
                description="...",
                args_schema=<Name>PipelineParameters,
            )
        ]
```

## Conventions

- **Output is always `rdflib.Graph`** — never raw dicts.
- **Reuse the module's ontology** in `../ontologies/` as the vocabulary for emitted triples. Add new classes to that TTL rather than coining ad-hoc URIs.
- **Idempotent runs**: re-running with the same parameters should produce the same graph (set deterministic URIs for named individuals).
- **Bulk-insert via `TripleStoreService.insert(graph, graph_name)`** — don't pump triples one at a time.

## Scaffold a new pipeline

```bash
abi new pipeline <name> .
```

This drops `<Name>Pipeline.py` with the canonical RDF-aware skeleton.

## Tests

Colocated as `<Name>Pipeline_test.py`. Assert on the produced graph:

```python
def test_run_emits_expected_triples():
    p = <Name>Pipeline(<Name>PipelineConfiguration(...))
    g = p.run(<Name>PipelineParameters(target="foo"))
    assert (URIRef("..."), RDF.type, URIRef("...")) in g
```

Run:

```bash
uv run pytest {{module_name_snake}}/pipelines
uv run pytest {{module_name_snake}}/pipelines/<Name>Pipeline_test.py -v
```

## Wiring into the module

1. Declare `TripleStoreService` in `ABIModule.dependencies.services`.
2. Expose `pipeline.as_tools()` from an agent in `../agents/`, **or** invoke the pipeline from an orchestration that batches runs and persists results.

## See also

- Triple store service (insert / query / subscribe / views): [`.abi/libs/naas-abi-core/.../services/triple_store/AGENTS.md`](../../../.abi/libs/naas-abi-core/naas_abi_core/services/triple_store/AGENTS.md)
- Module ontologies (TTL files this pipeline emits against): [`../ontologies/AGENTS.md`](../ontologies/AGENTS.md)
- Reference patterns: [`.abi/libs/naas-abi-marketplace/.../domains/ontology_engineer/pipelines/`](../../../.abi/libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/pipelines)
