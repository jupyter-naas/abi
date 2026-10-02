"""Act of Employment process pipeline.

An act of employment is an act of working (people module) that the employing
organization records: the employee role behind it, the job position that role
fills, the contract, the remuneration. Register the act of working itself with
``register_act_of_working``; this pipeline adds the employer's records to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PersonnelGraphContext,
)
from naas_abi_marketplace.domains.personnel.utils.paths import module_graph_name
from pydantic import Field
from rdflib import Graph, URIRef


@dataclass
class ActOfEmploymentPipelineConfiguration(PipelineConfiguration):
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef(module_graph_name())
    persist: bool = True
    context: PersonnelGraphContext | None = None


class ActOfEmploymentPipelineParameters(PipelineParameters):
    first_name: Annotated[str, Field(min_length=1)]
    last_name: Annotated[str, Field(min_length=1)]
    # The organization and title identify the act of working this employment
    # is; with the client, when the person is staffed at one.
    organization: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    client: str | None = None
    contract_type: str | None = None
    job_family: str | None = None
    remuneration_amount: float | None = None
    remuneration_currency: str = "EUR"


class ActOfEmploymentPipeline(Pipeline):
    __configuration: ActOfEmploymentPipelineConfiguration

    def __init__(self, configuration: ActOfEmploymentPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def _persist(self, graph: Graph) -> None:
        if (
            self.__configuration.persist
            and self.__configuration.triple_store is not None
            and len(graph) > 0
        ):
            self.__configuration.triple_store.insert(
                graph, graph_name=self.__configuration.graph_name
            )

    def run(self, parameters: ActOfEmploymentPipelineParameters) -> Graph:
        owned_context = self.__configuration.context is None
        context = self.__configuration.context or PersonnelGraphContext()
        before = len(context.graph)

        person = context.ensure_person(parameters.first_name, parameters.last_name)
        org = context.ensure_org(parameters.organization)
        client = context.ensure_org(parameters.client) if parameters.client else None
        context.add_employment(
            person=person,
            org=org,
            title=parameters.title,
            client=client,
            contract_type=parameters.contract_type,
            job_family=parameters.job_family,
            remuneration_amount=parameters.remuneration_amount,
            remuneration_currency=parameters.remuneration_currency,
        )

        delta = Graph()
        for triple in list(context.graph)[before:]:
            delta.add(triple)
        self._persist(delta)
        if owned_context:
            return context.graph
        return delta

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            params = ActOfEmploymentPipelineParameters.model_validate(kwargs)
            graph = self.run(params)
            return f"Registered act of employment ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_act_of_employment",
                description=(
                    "Record an act of working as an act of employment by the "
                    "organization: the employee role, job position, contract and "
                    "remuneration it keeps. Register the act of working itself "
                    "with register_act_of_working."
                ),
            )
        ]

    def as_api(self) -> None:
        pass
