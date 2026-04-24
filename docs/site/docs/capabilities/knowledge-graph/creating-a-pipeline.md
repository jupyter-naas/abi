# Creating a Pipeline

Pipelines transform raw data from integrations into OWL/RDF triples and store them in the knowledge graph. They are the semantic ingestion layer.

---

## Role in the stack

```bash
Integration (raw API data)  →  Pipeline (transforms to RDF)  →  Triple Store
```

A pipeline:
- Calls an integration to fetch raw data.
- Maps that data to ontology classes and properties.
- Writes RDF triples to the triple store.
- Is exposed as a tool for agents and as an API endpoint.

---

## Pipeline class

```python
# pipelines/MyPipeline.py
from naas_abi_core.pipeline.pipeline import Pipeline, PipelineConfiguration
from naas_abi_core.pipeline.pipeline import PipelineParameters
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi.modules.custom.my_module.integrations.MyIntegration import (
    MyIntegration, MyIntegrationConfiguration,
)
from dataclasses import dataclass
from pydantic import BaseModel, Field
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL

ABI = Namespace("http://ontology.naas.ai/abi/")
CCO = Namespace("https://www.commoncoreontologies.org/")

@dataclass
class MyPipelineConfiguration(PipelineConfiguration):
    integration_config: MyIntegrationConfiguration
    triple_store_service: TripleStoreService

class MyPipelineParameters(PipelineParameters):
    filter: str | None = Field(None, description="Optional filter for items to ingest")

class MyPipeline(Pipeline):
    __configuration: MyPipelineConfiguration

    def __init__(self, configuration: MyPipelineConfiguration):
        self.__configuration = configuration
        self.__integration = MyIntegration(configuration.integration_config)

    def run(self, parameters: MyPipelineParameters) -> dict:
        # 1. Fetch raw data
        items = self.__integration.list_items(filter=parameters.filter)

        # 2. Build an RDF graph
        g = Graph()

        for item in items:
            item_uri = URIRef(f"http://ontology.naas.ai/abi/item/{item['id']}")

            # Map to ontology class
            g.add((item_uri, RDF.type, CCO.InformationContentEntity))

            # Map properties
            if item.get("name"):
                g.add((item_uri, RDFS.label, Literal(item["name"])))
            if item.get("url"):
                g.add((item_uri, ABI.url, Literal(item["url"])))

        # 3. Store in triple store
        triples_added = len(g)
        self.__configuration.triple_store_service.insert_graph(g)

        return {"triples_added": triples_added, "items_processed": len(items)}

    def as_tools(self) -> list:
        from langchain_core.tools import StructuredTool

        return [
            StructuredTool(
                name="ingest_myservice_items",
                description="Fetch items from MyService and store them in the knowledge graph.",
                func=lambda **kwargs: self.run(MyPipelineParameters(**kwargs)),
                args_schema=MyPipelineParameters,
            )
        ]

    def as_api(self, router) -> None:
        from fastapi import APIRouter

        @router.post("/pipelines/myservice/ingest")
        def run_pipeline(parameters: MyPipelineParameters):
            return self.run(parameters)
```

---

## Using onto2py generated classes

If your ontology has been processed by `onto2py`, you can use typed Python classes instead of raw RDF construction:

```python
# onto2py generates this from MyOntology.ttl:
from naas_abi.modules.custom.my_module.ontologies.MyOntology import MyItem

# Use it in the pipeline:
item_obj = MyItem(
    uri=f"http://ontology.naas.ai/abi/item/{item['id']}",
    label=item["name"],
    url=item["url"],
)
g += item_obj.to_graph()
```

See [Creating an Ontology](/capabilities/knowledge-graph/creating-an-ontology) for onto2py setup.

---

## Registering in Dagster

Pipelines can be scheduled via Dagster. Define a Dagster asset in your module:

```python
from dagster import asset

@asset
def my_pipeline_asset(context):
    pipeline = MyPipeline(MyPipelineConfiguration(...))
    return pipeline.run(MyPipelineParameters())
```

---

## Best practices

- **Idempotent**: running the same pipeline twice should not create duplicate triples. Use `owl:hasKey` in your ontology for entity deduplication, or check for existing triples before inserting.
- **Schema-first**: define (or reuse) an ontology class for every entity type you ingest before writing the pipeline.
- **Small batches**: for large datasets, paginate the integration and commit triples in batches to avoid memory pressure.
- **Log progress**: use `abi.logger` for structured logging; avoid `print()`.
