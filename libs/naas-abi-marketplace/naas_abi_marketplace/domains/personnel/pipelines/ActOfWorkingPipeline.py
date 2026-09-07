"""Act of Working process pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from pydantic import Field
from rdflib import Graph, URIRef

from naas_abi_marketplace.domains.personnel.paths import module_graph_name
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PersonnelGraphContext,
)


@dataclass
class ActOfWorkingPipelineConfiguration(PipelineConfiguration):
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef(module_graph_name())
    persist: bool = True
    context: PersonnelGraphContext | None = None


class ActOfWorkingPipelineParameters(PipelineParameters):
    first_name: Annotated[str, Field(min_length=1)]
    last_name: Annotated[str, Field(min_length=1)]
    organization: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    site: Annotated[str, Field(min_length=1)]
    start: date
    end: Optional[date] = None
    duration: Optional[str] = None
    mission_label: Annotated[str, Field(min_length=1)]
    mission: Annotated[str, Field(min_length=1)]
    contract_type: Optional[str] = None
    skills: list[str] = []
    source_url: Optional[str] = None
    remuneration_amount: Optional[float] = None
    remuneration_currency: str = "EUR"


class ActOfWorkingPipeline(Pipeline):
    __configuration: ActOfWorkingPipelineConfiguration

    def __init__(self, configuration: ActOfWorkingPipelineConfiguration):
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

    def run(self, parameters: ActOfWorkingPipelineParameters) -> Graph:
        owned_context = self.__configuration.context is None
        context = self.__configuration.context or PersonnelGraphContext()
        person = context.ensure_person(parameters.first_name, parameters.last_name)
        profile = None
        if parameters.source_url:
            profile = context.ensure_work_profile(person, parameters.source_url)
        org = context.ensure_org(parameters.organization)
        site = context.ensure_site(parameters.site)
        skill_nodes = [
            context.ensure_skill(name, person) for name in parameters.skills
        ]
        before = len(context.graph)
        context.add_working(
            person=person,
            org=org,
            site=site,
            skills=skill_nodes,
            profile=profile,
            title=parameters.title,
            mission_label=parameters.mission_label,
            mission_content=parameters.mission,
            contract_type=parameters.contract_type,
            start=parameters.start,
            end=parameters.end,
            duration=parameters.duration,
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
            params = ActOfWorkingPipelineParameters.model_validate(kwargs)
            graph = self.run(params)
            return f"Inserted act of working ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_act_of_working",
                description=(
                    "Register an act of working: a person performing work for an "
                    "organization at a site over a temporal region."
                ),
            )
        ]

    def as_api(self) -> None:
        pass
