"""Register a person from a profile source payload (demo index.json shape).

Orchestrates ActOfWorking, ActOfStudying and PersonProfile pipelines in the
order the graph requires. Does not duplicate episode or presentation triples.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal, Union

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.domains.personnel.paths import module_graph_name
from naas_abi_marketplace.domains.personnel.pipelines.ActOfStudyingPipeline import (
    ActOfStudyingPipeline,
    ActOfStudyingPipelineConfiguration,
    ActOfStudyingPipelineParameters,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfWorkingPipeline import (
    ActOfWorkingPipeline,
    ActOfWorkingPipelineConfiguration,
    ActOfWorkingPipelineParameters,
)
from naas_abi_marketplace.domains.personnel.pipelines.PersonProfilePipeline import (
    CertificationInput,
    InterestInput,
    LanguageInput,
    PersonProfilePipeline,
    PersonProfilePipelineConfiguration,
    PersonProfilePipelineParameters,
    RecommendationInput,
)
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PersonnelGraphContext,
)
from pydantic import BaseModel, Field
from rdflib import Graph, URIRef


class SourcePersonInput(BaseModel):
    first_name: Annotated[str, Field(min_length=1)]
    last_name: Annotated[str, Field(min_length=1)]
    linkedin_profile_url: str | None = None


class WorkingRecordInput(BaseModel):
    process_type: Literal["ActOfWorking"] = "ActOfWorking"
    organization: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    site: str | None = None
    start: date | None = None
    end: date | None = None
    duration: str | None = None
    mission_label: Annotated[str, Field(min_length=1)]
    mission: Annotated[str, Field(min_length=1)]
    contract_type: str | None = None
    skills: list[str] = []
    source: str | None = None
    remuneration_amount: float | None = None
    remuneration_currency: str = "EUR"


class StudyingRecordInput(BaseModel):
    process_type: Literal["ActOfStudying"] = "ActOfStudying"
    organization: str | None = None
    program: Annotated[str, Field(min_length=1)]
    site: str | None = None
    start: date | None = None
    end: date | None = None
    duration: str | None = None
    skills: list[str] = []
    activities: str | None = None
    source: str | None = None


SourceRecordInput = Annotated[
    Union[WorkingRecordInput, StudyingRecordInput],
    Field(discriminator="process_type"),
]


class ProfileBlockInput(BaseModel):
    slug: str | None = None
    headline: str | None = None
    about: str | None = None
    quote: str | None = None
    years_of_experience: int | None = None
    organization: str | None = None
    service_line: str | None = None
    grade: str | None = None
    office: str | None = None
    city: str | None = None
    country: str | None = None
    country_code: str | None = None
    photo_url: str | None = None
    photo_path: str | None = None
    skills: list[str] = []
    certifications: list[CertificationInput] = []
    languages: list[LanguageInput] = []
    interests: list[InterestInput] = []
    recommendations: list[RecommendationInput] = []


class ProfileFromSourcePipelineParameters(PipelineParameters):
    person: SourcePersonInput
    records: list[SourceRecordInput] = []
    profile: ProfileBlockInput | None = None


@dataclass
class ProfileFromSourcePipelineConfiguration(PipelineConfiguration):
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef(module_graph_name())
    persist: bool = True
    context: PersonnelGraphContext | None = None


def apply_profile_source_payload(
    parameters: ProfileFromSourcePipelineParameters,
    *,
    context: PersonnelGraphContext,
    working: ActOfWorkingPipeline,
    studying: ActOfStudyingPipeline,
    profile_pipeline: PersonProfilePipeline,
) -> None:
    """Write one person payload into a shared graph context."""
    person = parameters.person
    person_key = f"{person.first_name} {person.last_name}"
    default_profile_url = person.linkedin_profile_url

    for record in parameters.records:
        if isinstance(record, StudyingRecordInput):
            studying.run(
                ActOfStudyingPipelineParameters(
                    first_name=person.first_name,
                    last_name=person.last_name,
                    organization=record.organization,
                    program=record.program,
                    site=record.site,
                    start=record.start,
                    end=record.end,
                    duration=record.duration,
                    skills=record.skills,
                    activities=record.activities,
                    source_url=record.source,
                )
            )
            continue

        if not default_profile_url and not record.source:
            raise ValueError(
                f"ActOfWorking for {person_key!r} needs person.linkedin_profile_url "
                "or record.source for provenance."
            )
        working.run(
            ActOfWorkingPipelineParameters(
                first_name=person.first_name,
                last_name=person.last_name,
                organization=record.organization,
                title=record.title,
                site=record.site,
                start=record.start,
                end=record.end,
                duration=record.duration,
                mission_label=record.mission_label,
                mission=record.mission,
                contract_type=record.contract_type,
                skills=record.skills,
                source_url=record.source or default_profile_url,
                remuneration_amount=record.remuneration_amount,
                remuneration_currency=record.remuneration_currency,
            )
        )

    block = parameters.profile
    if block is not None:
        profile_pipeline.run(
            PersonProfilePipelineParameters(
                first_name=person.first_name,
                last_name=person.last_name,
                slug=block.slug,
                headline=block.headline,
                about=block.about,
                quote=block.quote,
                years_of_experience=block.years_of_experience,
                organization=block.organization,
                service_line=block.service_line,
                grade=block.grade,
                office=block.office,
                city=block.city,
                country=block.country,
                country_code=block.country_code,
                photo_url=block.photo_url,
                photo_path=block.photo_path,
                source_url=default_profile_url,
                skills=block.skills,
                certifications=block.certifications,
                languages=block.languages,
                interests=block.interests,
                recommendations=block.recommendations,
            )
        )


class ProfileFromSourcePipeline(Pipeline):
    __configuration: ProfileFromSourcePipelineConfiguration

    def __init__(self, configuration: ProfileFromSourcePipelineConfiguration):
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

    def run(self, parameters: ProfileFromSourcePipelineParameters) -> Graph:
        owned_context = self.__configuration.context is None
        context = self.__configuration.context or PersonnelGraphContext()
        before = len(context.graph)
        # One persist at the end when we own the context; otherwise each child
        # pipeline persists its own delta (shared external context).
        child_persist = self.__configuration.persist if not owned_context else False

        working = ActOfWorkingPipeline(
            ActOfWorkingPipelineConfiguration(
                triple_store=self.__configuration.triple_store,
                graph_name=self.__configuration.graph_name,
                persist=child_persist,
                context=context,
            )
        )
        studying = ActOfStudyingPipeline(
            ActOfStudyingPipelineConfiguration(
                triple_store=self.__configuration.triple_store,
                graph_name=self.__configuration.graph_name,
                persist=child_persist,
                context=context,
            )
        )
        profile_pipeline = PersonProfilePipeline(
            PersonProfilePipelineConfiguration(
                triple_store=self.__configuration.triple_store,
                graph_name=self.__configuration.graph_name,
                persist=child_persist,
                context=context,
            )
        )

        apply_profile_source_payload(
            parameters,
            context=context,
            working=working,
            studying=studying,
            profile_pipeline=profile_pipeline,
        )

        delta = Graph()
        for triple in list(context.graph)[before:]:
            delta.add(triple)
        if owned_context:
            self._persist(delta)
            return context.graph
        return delta

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            params = ProfileFromSourcePipelineParameters.model_validate(kwargs)
            graph = self.run(params)
            return (
                f"Registered profile from source for {params.person.first_name} "
                f"{params.person.last_name} ({len(graph)} triples in graph context)."
            )

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_profile_from_source",
                description=(
                    "Register a person from a published profile source: run "
                    "register_act_of_working and register_act_of_studying for each "
                    "record, then register_person_profile for presentation facts. "
                    "Pass person, records (ActOfWorking / ActOfStudying), and an "
                    "optional profile block. Does not duplicate missions or skills."
                ),
            )
        ]

    def as_api(self) -> None:
        pass
