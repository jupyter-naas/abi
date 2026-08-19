"""Act of Studying process pipeline."""

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
class ActOfStudyingPipelineConfiguration(PipelineConfiguration):
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef(module_graph_name())
    persist: bool = True
    context: PersonnelGraphContext | None = None


class ActOfStudyingPipelineParameters(PipelineParameters):
    first_name: Annotated[str, Field(min_length=1)]
    last_name: Annotated[str, Field(min_length=1)]
    organization: Annotated[str, Field(min_length=1)]
    program: Annotated[str, Field(min_length=1)]
    site: Annotated[str, Field(min_length=1)]
    start: date
    end: Optional[date] = None
    duration: Optional[str] = None
    skills: list[str] = []
    activities: Optional[str] = None
    source_url: Optional[str] = None


class ActOfStudyingPipeline(Pipeline):
    __configuration: ActOfStudyingPipelineConfiguration

    def __init__(self, configuration: ActOfStudyingPipelineConfiguration):
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

    def run(self, parameters: ActOfStudyingPipelineParameters) -> Graph:
        owned_context = self.__configuration.context is None
        context = self.__configuration.context or PersonnelGraphContext()
        person = context.ensure_person(parameters.first_name, parameters.last_name)
        profile = None
        if parameters.source_url:
            profile = context.ensure_education_profile(person, parameters.source_url)
        org = context.ensure_org(parameters.organization, educational=True)
        site = context.ensure_site(parameters.site)
        skill_nodes = [
            context.ensure_skill(name, person) for name in parameters.skills
        ]
        before = len(context.graph)
        context.add_studying(
            person=person,
            org=org,
            site=site,
            skills=skill_nodes,
            profile=profile,
            program=parameters.program,
            start=parameters.start,
            end=parameters.end,
            duration=parameters.duration,
            activities=parameters.activities,
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
            params = ActOfStudyingPipelineParameters.model_validate(kwargs)
            graph = self.run(params)
            return f"Inserted act of studying ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_act_of_studying",
                description=(
                    "Register an act of studying: a person acquiring a curriculum "
                    "from an educational organization at a site over a temporal region."
                ),
            )
        ]

    def as_api(self) -> None:
        pass
