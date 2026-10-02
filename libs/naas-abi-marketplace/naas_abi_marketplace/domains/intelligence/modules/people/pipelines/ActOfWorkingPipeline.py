"""Act of Working process pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.utils.graph_builders import (
    PeopleGraphContext,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.paths import (
    module_graph_name,
)
from pydantic import AliasChoices, Field
from rdflib import Graph, URIRef


@dataclass
class ActOfWorkingPipelineConfiguration(PipelineConfiguration):
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef(module_graph_name())
    persist: bool = True
    context: PeopleGraphContext | None = None


class ActOfWorkingPipelineParameters(PipelineParameters):
    first_name: Annotated[str, Field(min_length=1)]
    last_name: Annotated[str, Field(min_length=1)]
    organization: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    # A profile that lists a role without saying where it was held states no
    # place. Borrowing the person's current city would invent one.
    site: str | None = None
    # A published profile often names a role without saying when it began. The
    # record is still true; it simply occupies no temporal region.
    start: date | None = None
    end: date | None = None
    duration: str | None = None
    mission_label: Annotated[str, Field(min_length=1)]
    mission: Annotated[str, Field(min_length=1)]
    # The client the work was performed for, when the person was staffed there by
    # this organization (a consulting engagement) rather than working for it
    # directly. Unset for a direct employment role.
    client: str | None = None
    mission_context: str | None = None
    # The engagement type the source states ('Full-time', 'Freelance', ...).
    # What was published, not the terms of a contract.
    employment_type: str | None = Field(
        default=None, validation_alias=AliasChoices("employment_type", "contract_type")
    )
    skills: list[str] = []
    source_url: str | None = None


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
        context = self.__configuration.context or PeopleGraphContext()
        person = context.ensure_person(parameters.first_name, parameters.last_name)
        profile = None
        if parameters.source_url:
            profile = context.ensure_work_profile(person, parameters.source_url)
        org = context.ensure_org(parameters.organization)
        client = context.ensure_org(parameters.client) if parameters.client else None
        site = context.ensure_site(parameters.site) if parameters.site else None
        skill_nodes = [context.ensure_skill(name, person) for name in parameters.skills]
        before = len(context.graph)
        context.add_working(
            person=person,
            org=org,
            client=client,
            site=site,
            skills=skill_nodes,
            profile=profile,
            title=parameters.title,
            mission_label=parameters.mission_label,
            mission_content=parameters.mission,
            mission_context=parameters.mission_context,
            employment_type=parameters.employment_type,
            start=parameters.start,
            end=parameters.end,
            duration=parameters.duration,
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
