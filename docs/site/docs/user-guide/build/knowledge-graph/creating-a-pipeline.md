# Creating a Pipeline

Pipelines transform raw data from integrations into OWL/RDF triples for the knowledge graph. They are the semantic ingestion layer: a pipeline's `run()` returns an `rdflib.Graph`.

A pipeline lives in a module, and the module's kind decides what it is written on: in an [in-engine module](/user-guide/build/modules/creating-a-module#remote-or-in-engine) it is `naas_abi_core` code, mounted on the REST API; in a [remote module](/user-guide/build/sdk/build-a-remote-module) it is `naas_abi_sdk` code that other modules call over NATS. `abi new pipeline` writes the right one for the module you run it in. This page describes the in-engine pipeline; [the remote one](#in-a-remote-module) follows.

---

## Role in the stack

```bash
Integration (raw API data)  →  Pipeline (transforms to RDF)  →  Triple Store
```

A pipeline:
- Calls an integration to fetch raw data.
- Maps that data to ontology classes and properties.
- Builds an RDF graph and returns it, writing it to the triple store when it is meant to persist it.
- Is exposed as a tool for agents and as an API endpoint.

If your output is not RDF, write a [workflow](/user-guide/build/agents/creating-a-workflow) instead.

---

## Scaffold one

From the project root:

```bash
abi new pipeline Items src/my_module/pipelines
```

It writes `ItemsPipeline.py` (the name is converted to PascalCase and `Pipeline` is appended): a configuration dataclass, a parameters model and a `Pipeline` subclass whose `run()` and `as_tools()` you fill in.

---

## Pipeline class

```python
# pipelines/ItemsPipeline.py
from dataclasses import dataclass
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from my_module import ABIModule
from my_module.integrations.MyIntegration import MyIntegration, MyIntegrationConfiguration
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from pydantic import Field
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef

MY = Namespace("http://ontology.naas.ai/my_module/")  # your module's ontology namespace
GRAPH = URIRef("http://ontology.naas.ai/graph/my_module")


@dataclass
class ItemsPipelineConfiguration(PipelineConfiguration):
    """Configuration for ItemsPipeline."""


class ItemsPipelineParameters(PipelineParameters):
    filter: Annotated[
        str | None, Field(description="Optional filter for the items to ingest")
    ] = None


class ItemsPipeline(Pipeline):
    """Ingest the items of MyService into the knowledge graph."""

    __configuration: ItemsPipelineConfiguration

    def __init__(self, configuration: ItemsPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        module = ABIModule.get_instance()
        self.__triple_store = module.engine.services.triple_store
        self.__integration = MyIntegration(
            MyIntegrationConfiguration(api_key=module.configuration.my_api_key)
        )

    def run(self, parameters: ItemsPipelineParameters) -> Graph:  # type: ignore[override]
        # 1. Fetch raw data
        items = self.__integration.list_items(filter=parameters.filter)

        # 2. Build an RDF graph
        g = Graph()
        for item in items:
            item_uri = URIRef(f"http://ontology.naas.ai/abi/item/{item['id']}")
            g.add((item_uri, RDF.type, MY.Item))  # a class of your ontology
            if item.get("name"):
                g.add((item_uri, RDFS.label, Literal(item["name"])))
            g.add((item_uri, MY.item_id, Literal(item["id"])))

        # 3. Store it, and return it
        self.__triple_store.insert(g, GRAPH)
        return g

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="ingest_myservice_items",
                description="Fetch items from MyService and store them in the knowledge graph.",
                func=lambda **kwargs: len(self.run(ItemsPipelineParameters(**kwargs))),
                args_schema=ItemsPipelineParameters,
            )
        ]
```

How the engine uses it:

- **Discovery.** The engine finds every `Pipeline` subclass under `pipelines/` and instantiates it with `New()` if the class defines one, else with an empty `<Name>PipelineConfiguration()`. A pipeline whose configuration needs arguments the engine cannot supply is skipped and logged, which is why the example reads its services from the module in `__init__`.
- **REST.** `as_api` is inherited from `Expose`: when `run(parameters)` is a real override with a Pydantic parameters model, the API mounts `POST /pipelines/<class name in snake case>` (here `POST /pipelines/items_pipeline`). The returned graph comes back as `{"format": "turtle", "data": "..."}`. See the [REST API](/user-guide/build/applications/api).
- **Tools.** `as_tools()` gives an agent the pipeline as a tool: see [Creating an Agent](/user-guide/build/agents/creating-an-agent).
- **From a terminal.** `abi run script my_script.py` loads the engine and runs a script of yours, which can build the pipeline and call `run()` (in a NATS project it needs the broker).

---

## Using onto2py generated classes

`onto2py` generates typed Python classes from your module's ontology (see [Creating an Ontology](/user-guide/build/knowledge-graph/creating-an-ontology#onto2py-code-generation)). Each class is a Pydantic model with one field per data property and an `rdf()` method that returns its triples, so a pipeline can build entities instead of raw triples:

```python
# generated from ontologies/modules/MyModuleOntology.ttl
from my_module.ontologies.modules.MyModuleOntology import Item

item = Item(_uri=f"http://ontology.naas.ai/abi/item/{item_id}", label=name, item_id=item_id)
g += item.rdf()
```

Omit `_uri` and the entity gets a generated IRI. Property names are the ontology's, in snake case.

---

## Scheduling a pipeline

A pipeline is plain Python, so a [module job](/user-guide/build/modules/module-jobs) runs it on a schedule: declare a `@job` on the module that owns the pipeline. The engine hosts it, and a synchronous handler runs in a worker thread:

```python
from datetime import timedelta
from naas_abi_core.module.jobs import Every, JobContext, job

class ABIModule(BaseModule):
    @job(triggers=(Every("1h"),), timeout=timedelta(minutes=30))
    def sync_items(self, ctx: JobContext) -> dict:
        from my_module.pipelines.ItemsPipeline import (
            ItemsPipeline, ItemsPipelineConfiguration, ItemsPipelineParameters,
        )
        graph = ItemsPipeline(ItemsPipelineConfiguration()).run(ItemsPipelineParameters())
        return {"triples": len(graph)}  # stored on the run record
```

Return something JSON-serializable (a count, not the graph). A run's result, logs and failures show in the Nexus System app's **Jobs** tab, where **Run now** triggers it by hand. Triggers, retries and idempotency: [Module jobs](/user-guide/build/modules/module-jobs).

:::warning Legacy: Dagster
Projects without NATS can schedule a pipeline with a Dagster asset (`abi new orchestration`), a [legacy](/user-guide/build/applications/dagster) extra removed in the next major. New projects use module jobs.
:::

---

## In a remote module

`abi new pipeline catalog pipelines`, run in a remote module's folder, writes a pipeline on `naas_abi_sdk` (no `naas_abi_core` import, and rdflib through the `[rdf]` extra) and a test beside it. `run` is async and returns the `Graph`; the module decides what to do with it:

```python
# src/research/pipelines/CatalogPipeline.py
from naas_abi_sdk.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from pydantic import Field
from rdflib import RDF, RDFS, Graph, Literal, URIRef


class CatalogPipelineParameters(PipelineParameters):
    iri: str = Field(default="urn:example:thing", description="IRI of the individual to describe")
    label: str = Field(default="Thing", description="Its label")


class CatalogPipeline(Pipeline[CatalogPipelineParameters]):
    """Describes an individual as RDF: this text is the description an agent or a caller reads."""

    async def run(self, parameters: CatalogPipelineParameters) -> Graph:
        graph = Graph()
        individual = URIRef(parameters.iri)
        graph.add((individual, RDF.type, RDFS.Resource))
        graph.add((individual, RDFS.label, Literal(parameters.label)))
        # Declare the `triple_store` service to persist it:
        #   await self.engine.services.triple_store.insert(graph, "my-graph")
        return graph
```

- **Discovery.** The module imports every `Pipeline` under `pipelines/`, builds it after `on_initialized` and lists it by its class name in snake case: `catalog_pipeline`. A pipeline that needs the engine's services defines `New(module)` on the class.
- **Calling it.** `graph = await engine.modules["my_project.research"].get_pipeline("catalog_pipeline").run({})` runs it over NATS and returns an rdflib `Graph` (carried as N-Triples; a graph above one NATS message streams, up to 256 MiB). The same deadline, authorization and no-retry rules as a workflow apply. As an agent tool, the graph comes back as `{"format": "turtle", "data": "..."}`.
- **Jobs.** `job = JobSettings(triggers=(Every("1h"),), timeout=timedelta(minutes=30))` on the class runs it on a schedule as the job `pipeline.catalog_pipeline`. The run record keeps up to 64 KiB of the graph as N-Triples (more is cut to a preview), so a pipeline that produces a large graph writes it to the triple store itself.
- **Not mounted on REST.** `POST /pipelines/<slug>` belongs to in-engine modules.

---

## Best practices

- **Idempotent**: running the same pipeline twice should not create duplicate triples. Use `owl:hasKey` in your ontology for entity deduplication, or check for existing triples before inserting.
- **Schema-first**: define (or reuse) an ontology class for every entity type you ingest before writing the pipeline.
- **Small batches**: for large datasets, paginate the integration and commit triples in batches to avoid memory pressure.
- **Log progress**: use `from naas_abi_core import logger`; avoid `print()`.
