"""Person profile pipeline: the person-level facts a directory shows.

Employment and education stay in ActOfWorkingPipeline and ActOfStudyingPipeline.
This pipeline writes what holds of the person rather than of one job: how they
are presented, where they work from, what they are certified in, what languages
they work in, what skills and interests they bear, and what colleagues have
written about them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.domains.personnel.paths import module_graph_name
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    ABI,
    PERSONNEL,
    PersonnelGraphContext,
)
from pydantic import BaseModel, Field
from rdflib import Graph, URIRef


@dataclass
class PersonProfilePipelineConfiguration(PipelineConfiguration):
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef(module_graph_name())
    persist: bool = True
    context: PersonnelGraphContext | None = None


class CertificationInput(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    issuer: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    status: str | None = None
    credential_id: str | None = None
    credential_url: str | None = None


class LanguageInput(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    proficiency: str | None = None


class InterestInput(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    description: str | None = None
    kind: str | None = None


class RecommendationInput(BaseModel):
    """A recommendation needs its author: an unsigned testimonial is not one."""

    author_first_name: Annotated[str, Field(min_length=1)]
    author_last_name: Annotated[str, Field(min_length=1)]
    content: Annotated[str, Field(min_length=1)]
    relationship: str | None = None
    written_on: date | None = None


class PersonProfilePipelineParameters(PipelineParameters):
    first_name: Annotated[str, Field(min_length=1)]
    last_name: Annotated[str, Field(min_length=1)]
    slug: str | None = None
    # Contact details, stated on the person. Whether a directory publishes them
    # is the directory's call (privacy.publish_contact_details), not the graph's.
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
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
    source_url: str | None = None
    # A skill is a quality of the person. Acts of working record where one was
    # developed; a source that states a skill without saying where it came from
    # still states the skill.
    skills: list[str] = []
    certifications: list[CertificationInput] = []
    languages: list[LanguageInput] = []
    interests: list[InterestInput] = []
    recommendations: list[RecommendationInput] = []


class PersonProfilePipeline(Pipeline):
    __configuration: PersonProfilePipelineConfiguration

    def __init__(self, configuration: PersonProfilePipelineConfiguration):
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

    def run(self, parameters: PersonProfilePipelineParameters) -> Graph:
        owned_context = self.__configuration.context is None
        context = self.__configuration.context or PersonnelGraphContext()
        before = len(context.graph)

        person = context.ensure_person(parameters.first_name, parameters.last_name)
        if parameters.slug:
            context.set_profile_slug(person, parameters.slug)
        context.set_contact_details(
            person,
            email=parameters.email,
            phone=parameters.phone,
            linkedin_url=parameters.linkedin_url,
        )

        profile = None
        if parameters.source_url:
            profile = context.ensure_work_profile(person, parameters.source_url)

        context.add_profile_summary(
            person,
            headline=parameters.headline,
            about=parameters.about,
            quote=parameters.quote,
            years_of_experience=parameters.years_of_experience,
            profile=profile,
        )
        context.ensure_portrait(
            person, url=parameters.photo_url, path=parameters.photo_path
        )

        org = None
        if parameters.organization:
            org = context.ensure_org(parameters.organization)
            context.graph.add(
                (
                    URIRef(person._uri),
                    PERSONNEL.isEmployedBy,
                    URIRef(org._uri),
                )
            )

        # A service line is a part of the employing organization, so it cannot be
        # minted without one. Stated alone, it would be an organization with no
        # parent, which is not what the source says.
        if parameters.service_line and org is not None:
            line = context.ensure_service_line(parameters.service_line, org)
            # The person is a member part of the service line whether or not any
            # employee role has been recorded for them yet. Roles come from
            # ActOfWorkingPipeline, which may run after this one, or never.
            context.graph.add(
                (URIRef(line._uri), ABI.hasMemberPart, URIRef(person._uri))
            )
            for role_uri in context.graph.objects(
                URIRef(person._uri),
                PERSONNEL.hasEmployeeRole,
            ):
                context.graph.add(
                    (
                        role_uri,
                        PERSONNEL.inServiceLine,
                        URIRef(line._uri),
                    )
                )

        if parameters.grade:
            context.ensure_grade(parameters.grade, person)

        for skill_name in parameters.skills:
            context.ensure_skill(skill_name, person)

        place = parameters.office or parameters.city or parameters.country
        if place:
            site = context.ensure_site(place)
            context.describe_site(
                site,
                office=parameters.office,
                city=parameters.city,
                country=parameters.country,
                country_code=parameters.country_code,
            )
            context.graph.add(
                (
                    URIRef(person._uri),
                    PERSONNEL.hasWorkLocation,
                    URIRef(site._uri),
                )
            )

        for certification in parameters.certifications:
            context.add_certification(
                person,
                name=certification.name,
                issuer=context.ensure_org(certification.issuer)
                if certification.issuer
                else None,
                issue_date=certification.issue_date,
                expiry_date=certification.expiry_date,
                status=certification.status,
                credential_id=certification.credential_id,
                credential_url=certification.credential_url,
            )

        for language in parameters.languages:
            context.add_language(
                person, name=language.name, proficiency=language.proficiency
            )

        for interest in parameters.interests:
            context.add_interest(
                person,
                name=interest.name,
                description=interest.description,
                kind=interest.kind,
            )

        for recommendation in parameters.recommendations:
            author = context.ensure_person(
                recommendation.author_first_name, recommendation.author_last_name
            )
            context.add_recommendation(
                person,
                author=author,
                content=recommendation.content,
                relationship=recommendation.relationship,
                written_on=recommendation.written_on,
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
            params = PersonProfilePipelineParameters.model_validate(kwargs)
            graph = self.run(params)
            return f"Registered person profile ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_person_profile",
                description=(
                    "Register the person-level facts of a profile: contact details "
                    "(email, phone, LinkedIn URL), headline, summary, quote, portrait, work location, service line, grade, "
                    "certifications, languages, interests and recommendations. "
                    "Jobs are registered with register_act_of_working and studies "
                    "with register_act_of_studying."
                ),
            )
        ]

    def as_api(self) -> None:
        pass
