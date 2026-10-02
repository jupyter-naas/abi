"""Personnel profile pipeline: what the employer records about one of its people.

The person-level facts a published profile states (headline, portrait, skills,
languages...) are people intelligence: ``register_person_profile`` in the people
module. This pipeline writes the employer's own records about the person: that
it employs them, the service line it places them in and the grade it gives them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.utils.graph_builders import (
    ABI,
)
from naas_abi_marketplace.domains.personnel.paths import module_graph_name
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PERSONNEL,
    PersonnelGraphContext,
)
from pydantic import Field
from rdflib import Graph, URIRef


@dataclass
class PersonnelProfilePipelineConfiguration(PipelineConfiguration):
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef(module_graph_name())
    persist: bool = True
    context: PersonnelGraphContext | None = None


class PersonnelProfilePipelineParameters(PipelineParameters):
    first_name: Annotated[str, Field(min_length=1)]
    last_name: Annotated[str, Field(min_length=1)]
    organization: Annotated[str, Field(min_length=1)]
    service_line: str | None = None
    grade: str | None = None


class PersonnelProfilePipeline(Pipeline):
    __configuration: PersonnelProfilePipelineConfiguration

    def __init__(self, configuration: PersonnelProfilePipelineConfiguration):
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

    def run(self, parameters: PersonnelProfilePipelineParameters) -> Graph:
        owned_context = self.__configuration.context is None
        context = self.__configuration.context or PersonnelGraphContext()
        before = len(context.graph)

        person = context.ensure_person(parameters.first_name, parameters.last_name)
        org = context.ensure_org(parameters.organization)
        context.set_employer(person, org)

        if parameters.service_line:
            line = context.ensure_service_line(parameters.service_line, org)
            # The person is a member part of the service line whether or not any
            # employee role has been recorded for them yet. Roles come from
            # ActOfEmploymentPipeline, which may run after this one, or never.
            context.graph.add(
                (URIRef(line._uri), ABI.hasMemberPart, URIRef(person._uri))
            )
            for role_uri in context.graph.objects(
                URIRef(person._uri), PERSONNEL.hasEmployeeRole
            ):
                context.graph.add(
                    (role_uri, PERSONNEL.inServiceLine, URIRef(line._uri))
                )

        if parameters.grade:
            context.ensure_grade(parameters.grade, person)

        delta = Graph()
        for triple in list(context.graph)[before:]:
            delta.add(triple)
        self._persist(delta)
        if owned_context:
            return context.graph
        return delta

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            params = PersonnelProfilePipelineParameters.model_validate(kwargs)
            graph = self.run(params)
            return f"Registered personnel profile ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_personnel_profile",
                description=(
                    "Record what the organization keeps about one of its people: "
                    "that it employs them, their service line and their grade. "
                    "Published profile facts go through register_person_profile."
                ),
            )
        ]

    def as_api(self) -> None:
        pass
