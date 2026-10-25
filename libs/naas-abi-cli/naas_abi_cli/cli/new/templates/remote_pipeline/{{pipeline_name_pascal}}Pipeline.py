"""{{pipeline_name_pascal}}Pipeline: a pipeline of this remote module.

Written like an in-engine pipeline, on ``naas_abi_sdk`` only. ``run`` returns an
rdflib ``Graph``; the module decides what to do with it, for instance write it
to the engine's triple store (declare the ``triple_store`` service):

    await self.engine.services.triple_store.insert(graph, "my-graph")

``ABIModule`` finds the pipeline under ``pipelines/`` and builds it once
``on_initialized`` has run. The module's agents call it as a tool (the graph comes
back as turtle):

    tools = self.get_pipeline("{{pipeline_name_snake}}_pipeline").as_tools()

Its name, ``{{pipeline_name_snake}}_pipeline``, is the class name in snake case.
Built with an empty ``{{pipeline_name_pascal}}PipelineConfiguration`` unless it needs
more: define ``New(module)`` on the class (sync or async; read credentials with
``await module.engine.services.secret.get("KEY")``), or bind an instance in
``on_initialized`` with ``self.expose_pipeline(name, instance)``.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_sdk.pipeline import (
    Pipeline,
    PipelineConfiguration,
    PipelineParameters,
)
from pydantic import Field
from rdflib import RDF, RDFS, Graph, Literal, URIRef


@dataclass
class {{pipeline_name_pascal}}PipelineConfiguration(PipelineConfiguration):
    """Configuration for {{pipeline_name_pascal}}Pipeline."""


class {{pipeline_name_pascal}}PipelineParameters(PipelineParameters):
    """Parameters for {{pipeline_name_pascal}}Pipeline: the tool's arguments."""

    iri: str = Field(
        default="urn:example:thing", description="IRI of the individual to describe"
    )
    label: str = Field(default="Thing", description="Its label")


class {{pipeline_name_pascal}}Pipeline(Pipeline[{{pipeline_name_pascal}}PipelineParameters]):
    """Describes an individual as RDF. Replace with what the pipeline does: this
    text is the description an agent reads to decide when to call it."""

    __configuration: {{pipeline_name_pascal}}PipelineConfiguration

    def __init__(self, configuration: {{pipeline_name_pascal}}PipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    async def run(self, parameters: {{pipeline_name_pascal}}PipelineParameters) -> Graph:
        graph = Graph()
        individual = URIRef(parameters.iri)
        graph.add((individual, RDF.type, RDFS.Resource))
        graph.add((individual, RDFS.label, Literal(parameters.label)))
        return graph
