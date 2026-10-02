"""Act of Certification process pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.domains.personnel.paths import module_graph_name
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PersonnelGraphContext,
)
from pydantic import Field
from rdflib import Graph, URIRef


@dataclass
class ActOfCertificationPipelineConfiguration(PipelineConfiguration):
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef(module_graph_name())
    persist: bool = True
    context: PersonnelGraphContext | None = None


class ActOfCertificationPipelineParameters(PipelineParameters):
    first_name: Annotated[str, Field(min_length=1)]
    last_name: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    # A source often lists a certification with neither its issuer nor a date.
    # Both stay absent rather than being guessed: the certification section reads
    # the name, and the rest is shown only when it was stated.
    issuer: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    status: str | None = None
    credential_id: str | None = None
    credential_url: str | None = None
    site: str | None = None
    skills: list[str] = []
    source_url: str | None = None


class ActOfCertificationPipeline(Pipeline):
    __configuration: ActOfCertificationPipelineConfiguration

    def __init__(self, configuration: ActOfCertificationPipelineConfiguration):
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

    def run(self, parameters: ActOfCertificationPipelineParameters) -> Graph:
        owned_context = self.__configuration.context is None
        context = self.__configuration.context or PersonnelGraphContext()
        person = context.ensure_person(parameters.first_name, parameters.last_name)
        profile = (
            context.ensure_work_profile(person, parameters.source_url)
            if parameters.source_url
            else None
        )
        issuer = context.ensure_org(parameters.issuer) if parameters.issuer else None
        site = context.ensure_site(parameters.site) if parameters.site else None
        skill_nodes = [context.ensure_skill(name, person) for name in parameters.skills]
        before = len(context.graph)
        context.add_certification(
            person,
            name=parameters.name,
            issuer=issuer,
            issue_date=parameters.issue_date,
            expiry_date=parameters.expiry_date,
            status=parameters.status,
            credential_id=parameters.credential_id,
            credential_url=parameters.credential_url,
            site=site,
            skills=skill_nodes,
            profile=profile,
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
            params = ActOfCertificationPipelineParameters.model_validate(kwargs)
            graph = self.run(params)
            return f"Inserted act of certification ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_act_of_certification",
                description=(
                    "Register an act of certification: a certifying organization "
                    "attesting that a person has demonstrated a competence or "
                    "holds a licence, and the certification it awards."
                ),
                args_schema=ActOfCertificationPipelineParameters,
            )
        ]

    def as_api(self) -> None:
        pass
