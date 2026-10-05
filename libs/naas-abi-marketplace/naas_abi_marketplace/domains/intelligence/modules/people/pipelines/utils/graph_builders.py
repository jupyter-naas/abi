"""Shared RDF builders for people process pipelines.

Everything here is what a published source can say about a person. An
organization's internal records (employee role, job position, contract,
remuneration, grade, service line) are written by the personnel module, which
extends :class:`PeopleGraphContext`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from naas_abi.ontologies.modules.ABIOntology import (
    Site,
    TemporalInstant,
)
from naas_abi.ontologies.modules.ABIOntology import TemporalRegion as AbiTemporalRegion
from naas_abi.ontologies.modules.OrganizationOntology import Organization
from naas_abi.ontologies.modules.PersonOntology import Person
from naas_abi_marketplace.domains.intelligence.modules.people.ontologies.modules.PeopleOntology import (
    AcademicDegree,
    Certification,
    EnrollmentRecord,
    Interest,
    LanguageCapability,
    OccupationRole,
    Portrait,
    ProfileDocument,
    ProfileSummary,
    Recommendation,
    Skill,
    StudentRole,
)
from naas_abi_marketplace.domains.intelligence.modules.people.ontologies.processes.ActOfCertificationProcess import (
    ActOfCertification,
    CertificationCandidateRole,
)
from naas_abi_marketplace.domains.intelligence.modules.people.ontologies.processes.ActOfStudyingProcess import (
    ActOfStudying,
)
from naas_abi_marketplace.domains.intelligence.modules.people.ontologies.processes.ActOfWorkingProcess import (
    ActOfWorking,
    Mission,
)
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

ABI = Namespace("http://ontology.naas.ai/abi/")
PEOPLE = Namespace("http://ontology.naas.ai/people/")
CCO = Namespace("https://www.commoncoreontologies.org/")


def slug(*parts: str) -> str:
    joined = "-".join(p.strip().lower() for p in parts if p and str(p).strip())
    return re.sub(r"[^a-z0-9_\-]+", "-", joined).strip("-") or "unknown"


def individual_uri(ns: str, class_name: str, stable_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", stable_id)
    return f"{ns}{class_name}/{safe}"


def act_of_working_key(
    person_label: str, org_label: str, client_label: str | None, title: str
) -> str:
    """The stable key of one act of working, shared by its role and mission.

    The client (when staffed there by an employer) is part of what makes an act
    of working distinct: the same title recurs across different client
    engagements at one employer, and without the client in the key those
    engagements collide onto the same node and silently merge their missions.
    A module that adds its own records to an act (an employer's contract, say)
    mints the act's IRI from this same key.
    """
    return slug(person_label, org_label, client_label or "", title)


def act_of_working_uri(
    person_label: str, org_label: str, client_label: str | None, title: str
) -> str:
    key = act_of_working_key(person_label, org_label, client_label, title)
    return individual_uri(str(PEOPLE), "ActOfWorking", key)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def period_label(start: date | None, end: date | None) -> str:
    """How a period reads when the source stated only part of it."""
    if start and end:
        return f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"
    if start:
        return f"{start.strftime('%b %Y')} – Present"
    if end:
        return f"Until {end.strftime('%b %Y')}"
    return "Date not recorded"


@dataclass
class PeopleGraphContext:
    """Mutable builder state shared across process pipelines in one batch."""

    graph: Graph = field(default_factory=Graph)
    creator: str = "people_pipeline"
    people: dict[str, Person] = field(default_factory=dict)
    orgs: dict[str, Organization] = field(default_factory=dict)
    sites: dict[str, Site] = field(default_factory=dict)
    skills: dict[str, Skill] = field(default_factory=dict)
    portraits: dict[str, Portrait] = field(default_factory=dict)
    profile_summaries: dict[str, ProfileSummary] = field(default_factory=dict)
    work_profiles: dict[str, ProfileDocument] = field(default_factory=dict)
    education_profiles: dict[str, ProfileDocument] = field(default_factory=dict)
    last_role_uri: str | None = None

    def ensure_person(self, first: str, last: str) -> Person:
        key = f"{first} {last}"
        if key in self.people:
            return self.people[key]
        uri = individual_uri(str(ABI), "Person", slug(first, last))
        person = Person(
            _uri=uri,
            label=key,
            first_name=first,
            last_name=last,
            full_name=key,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += person.rdf()
        self.graph.add((URIRef(uri), RDF.type, CCO.ont00000562))
        self.graph.add(
            (URIRef(uri), ABI.given_name, Literal(first, datatype=XSD.string))
        )
        self.graph.add(
            (URIRef(uri), ABI.family_name, Literal(last, datatype=XSD.string))
        )
        self.people[key] = person
        return person

    def ensure_org(self, label: str, *, educational: bool = False) -> Organization:
        if label in self.orgs:
            return self.orgs[label]
        org = Organization(
            _uri=individual_uri(str(ABI), "Organization", slug(label)),
            label=label,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += org.rdf()
        if educational:
            self.graph.add((URIRef(org._uri), RDF.type, CCO.ont00000564))
        self.orgs[label] = org
        return org

    def ensure_site(self, label: str) -> Site:
        if label in self.sites:
            return self.sites[label]
        site = Site(
            _uri=individual_uri(str(PEOPLE), "Site", slug(label)),
            label=label,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += site.rdf()
        self.sites[label] = site
        return site

    def ensure_skill(self, name: str, person: Person) -> Skill:
        key = f"{person.label}|{name}"
        if key in self.skills:
            return self.skills[key]
        skill = Skill(
            _uri=individual_uri(str(PEOPLE), "Skill", slug(person.label or "", name)),
            label=name,
            skill_name=name,
            inheresIn=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += skill.rdf()
        self.graph.add((URIRef(person._uri), ABI.hasSkill, URIRef(skill._uri)))
        self.skills[key] = skill
        return skill

    def set_profile_slug(self, person: Person, slug_value: str) -> str:
        """Assign the key this person is addressed by in profile URLs and dataset rows."""
        self.graph.add(
            (
                URIRef(person._uri),
                ABI.profile_slug,
                Literal(slug_value, datatype=XSD.string),
            )
        )
        return slug_value

    def set_contact_details(
        self,
        person: Person,
        *,
        email: str | None = None,
        phone: str | None = None,
        linkedin_url: str | None = None,
    ) -> None:
        """State how the person can be reached. Absent values are left unstated."""
        for predicate, value, datatype in (
            (ABI.email_address, email, XSD.string),
            (ABI.telephone_number, phone, XSD.string),
            (ABI.linkedin_url, linkedin_url, XSD.anyURI),
        ):
            if value:
                self.graph.add(
                    (URIRef(person._uri), predicate, Literal(value, datatype=datatype))
                )

    def describe_site(
        self,
        site: Site,
        *,
        office: str | None = None,
        city: str | None = None,
        country: str | None = None,
        country_code: str | None = None,
    ) -> Site:
        """Add the structured place of a site, so it can be grouped and flagged.

        The label stays whatever the caller passed to ensure_site; these
        properties are what a directory reads instead of parsing that label.
        """
        for prop, value in (
            (ABI.office_label, office),
            (ABI.city_name, city),
            (ABI.country_name, country),
            (ABI.site_country_code, country_code.upper() if country_code else None),
        ):
            if value:
                self.graph.add(
                    (URIRef(site._uri), prop, Literal(value, datatype=XSD.string))
                )
        return site

    def ensure_portrait(
        self, person: Person, *, url: str | None = None, path: str | None = None
    ) -> Portrait | None:
        """Where the person's photograph lives. Never the image bytes."""
        if not url and not path:
            return None
        key = person.label or ""
        if key in self.portraits:
            return self.portraits[key]
        portrait = Portrait(
            _uri=individual_uri(str(PEOPLE), "Portrait", slug(key)),
            label=f"Portrait - {person.label}",
            portrait_url=url,
            portrait_path=path,
            is_portrait_of=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += portrait.rdf()
        self.graph.add((URIRef(person._uri), ABI.hasPortrait, URIRef(portrait._uri)))
        self.portraits[key] = portrait
        return portrait

    def add_profile_summary(
        self,
        person: Person,
        *,
        headline: str | None = None,
        about: str | None = None,
        quote: str | None = None,
        years_of_experience: int | None = None,
        profile: ProfileDocument | None = None,
    ) -> ProfileSummary | None:
        """How the person is presented in general, traceable to where it was published.

        years_of_experience is the figure the source claims, not one counted
        from the acts of working in this graph: the graph holds only the
        history that has been recorded.
        """
        # A page that states nothing but a name is still where the person was
        # published: keep the summary so the source stays traceable.
        if not any((headline, about, quote, years_of_experience)) and profile is None:
            return None
        key = person.label or ""
        if key in self.profile_summaries:
            return self.profile_summaries[key]
        summary = ProfileSummary(
            _uri=individual_uri(str(PEOPLE), "ProfileSummary", slug(key)),
            label=headline or f"Profile - {person.label}",
            headline_text=headline,
            summary_content=about,
            quote_content=quote,
            years_of_experience=years_of_experience,
            is_profile_summary_of=[person._uri],
            is_sourced_from=[profile._uri] if profile else None,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += summary.rdf()
        self.graph.add(
            (URIRef(person._uri), ABI.hasProfileSummary, URIRef(summary._uri))
        )
        self.profile_summaries[key] = summary
        return summary

    def add_certification(
        self,
        person: Person,
        *,
        name: str,
        issuer: Organization | None = None,
        issue_date: date | None = None,
        expiry_date: date | None = None,
        status: str | None = None,
        credential_id: str | None = None,
        credential_url: str | None = None,
        site: Site | None = None,
        skills: list[Skill] | None = None,
        profile: ProfileDocument | None = None,
    ) -> Certification:
        """A certification or a licence, and the act of certification that awarded it.

        The distinction between the two is who may withhold it. The Certification
        is what the person carries; the act is how they came to carry it, so a
        certification the source names without saying who issued it or when is
        still an act, just one with no certifying organization or temporal region.
        """
        key = slug(person.label or "", name)
        certification = Certification(
            _uri=individual_uri(str(PEOPLE), "Certification", key),
            label=name,
            certification_name=name,
            issue_date=issue_date,
            expiry_date=expiry_date,
            certification_status=status,
            credential_id=credential_id,
            credential_url=credential_url,
            is_certification_of=[person._uri],
            issued_by_organization=[issuer._uri] if issuer else None,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += certification.rdf()
        self.graph.add(
            (
                URIRef(person._uri),
                ABI.hasCertification,
                URIRef(certification._uri),
            )
        )
        if profile:
            self.graph.add(
                (
                    URIRef(certification._uri),
                    ABI.isSourcedFrom,
                    URIRef(profile._uri),
                )
            )

        # The act ends when the certification is awarded: that is the only moment
        # a source gives, so it bounds the region and the start stays unstated.
        temporal_uri = self.add_temporal_region(
            key=f"{key}-certification",
            label=f"Awarded {issue_date.strftime('%b %Y')}" if issue_date else "",
            start=None,
            end=issue_date,
        )

        role = CertificationCandidateRole(
            _uri=individual_uri(str(PEOPLE), "CertificationCandidateRole", key),
            label=f"Candidate - {name}",
            is_certification_candidate_role_of=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += role.rdf()
        self.graph.add(
            (
                URIRef(person._uri),
                ABI.hasCertificationCandidateRole,
                URIRef(role._uri),
            )
        )

        act_uri = individual_uri(str(PEOPLE), "ActOfCertification", key)
        act = ActOfCertification(
            _uri=act_uri,
            label=f"{name} @ {issuer.label}" if issuer else name,
            hasParticipant=[person._uri],
            occursIn=[site._uri] if site else None,
            occupiesTemporalRegion=[temporal_uri] if temporal_uri else None,
            for_certifying_organization=[issuer._uri] if issuer else None,
            has_awarded_certification=certification._uri,
            is_act_of_certification_of=[person._uri],
            realizes=[role._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += act.rdf()
        self.graph.add(
            (URIRef(person._uri), ABI.hasActOfCertification, URIRef(act_uri))
        )
        # demonstratesSkill is multi-valued but generated single-valued, so the
        # skills are stated directly rather than through the entity.
        for skill in skills or []:
            self.graph.add(
                (URIRef(act_uri), ABI.demonstratesSkill, URIRef(skill._uri))
            )
        return certification

    def add_language(
        self, person: Person, *, name: str, proficiency: str | None = None
    ) -> LanguageCapability:
        key = slug(person.label or "", name)
        capability = LanguageCapability(
            _uri=individual_uri(str(PEOPLE), "LanguageCapability", key),
            label=f"{name} - {proficiency}" if proficiency else name,
            language_name=name,
            proficiency_level=proficiency,
            inheres_in=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += capability.rdf()
        self.graph.add(
            (
                URIRef(person._uri),
                ABI.hasLanguageCapability,
                URIRef(capability._uri),
            )
        )
        return capability

    def add_recommendation(
        self,
        person: Person,
        *,
        author: Person,
        content: str,
        relationship: str | None = None,
        written_on: date | None = None,
    ) -> Recommendation:
        """Two people are required: the subject, and the colleague who wrote it."""
        key = slug(person.label or "", author.label or "", (written_on or "").__str__())
        recommendation = Recommendation(
            _uri=individual_uri(str(PEOPLE), "Recommendation", key),
            label=f"Recommendation for {person.label} by {author.label}",
            recommendation_content=content,
            recommendation_date=written_on,
            relationship_label=relationship,
            is_recommendation_of=[person._uri],
            has_recommendation_author=[author._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += recommendation.rdf()
        self.graph.add(
            (
                URIRef(person._uri),
                ABI.hasRecommendation,
                URIRef(recommendation._uri),
            )
        )
        return recommendation

    def add_interest(
        self,
        person: Person,
        *,
        name: str,
        description: str | None = None,
        kind: str | None = None,
        target_uri: str | None = None,
    ) -> Interest:
        """What the person follows outside the duties of any one job.

        target_uri is optional: most interests have no individual in the graph
        to point at, and then the name is the whole of what is known.
        """
        key = slug(person.label or "", name)
        interest = Interest(
            _uri=individual_uri(str(PEOPLE), "Interest", key),
            label=name,
            interest_name=name,
            interest_description=description,
            interest_kind=kind,
            inheres_in=[person._uri],
            has_interest_target=[target_uri] if target_uri else None,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += interest.rdf()
        self.graph.add((URIRef(person._uri), ABI.hasInterest, URIRef(interest._uri)))
        return interest

    def ensure_work_profile(self, person: Person, source_url: str) -> ProfileDocument:
        key = person.label or ""
        if key in self.work_profiles:
            return self.work_profiles[key]
        doc = ProfileDocument(
            _uri=individual_uri(str(PEOPLE), "ProfileDocument", slug(key, "linkedin")),
            label=f"LinkedIn experience - {person.label}",
            source_url=source_url,
            is_profile_document_of=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += doc.rdf()
        self.graph.add(
            (URIRef(person._uri), ABI.hasProfileDocument, URIRef(doc._uri))
        )
        self.work_profiles[key] = doc
        return doc

    def ensure_education_profile(
        self, person: Person, source_url: str
    ) -> ProfileDocument:
        key = person.label or ""
        if key in self.education_profiles:
            return self.education_profiles[key]
        doc = ProfileDocument(
            _uri=individual_uri(
                str(PEOPLE), "ProfileDocument", slug(key, "linkedin-education")
            ),
            label=f"LinkedIn education - {person.label}",
            source_url=source_url,
            is_profile_document_of=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += doc.rdf()
        self.graph.add(
            (URIRef(person._uri), ABI.hasProfileDocument, URIRef(doc._uri))
        )
        self.education_profiles[key] = doc
        return doc

    def add_temporal_region(
        self,
        *,
        key: str,
        label: str,
        start: date | None,
        end: date | None,
        duration: str | None = None,
    ) -> str | None:
        """The region a record occupies, or ``None`` when it is undated.

        A source that names neither a start nor an end has not told us when
        anything happened. Minting a region anyway would put a temporal claim in
        the graph that nobody made, so the record simply occupies no region.
        """
        if start is None and end is None:
            return None

        def instant(bound: str, moment: date) -> str:
            uri = individual_uri(
                str(ABI), "TemporalInstant", f"{key}-{bound}-{moment.isoformat()}"
            )
            node = TemporalInstant(
                _uri=uri,
                label=moment.strftime("%d/%m/%Y"),
                created=utc_now(),
                creator=self.creator,
            )
            for triple in node.rdf():
                self.graph.add(triple)
            self.graph.add(
                (URIRef(uri), ABI.instant_date, Literal(moment, datatype=XSD.date))
            )
            return uri

        first_uri = instant("start", start) if start else None
        last_uri = instant("end", end) if end else None

        region_uri = individual_uri(str(ABI), "TemporalRegion", key)
        region = AbiTemporalRegion(
            _uri=region_uri,
            label=label,
            has_first_instant=[first_uri] if first_uri else None,
            has_last_instant=[last_uri] if last_uri else None,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += region.rdf()
        if duration:
            self.graph.add(
                (
                    URIRef(region_uri),
                    ABI.duration_label,
                    Literal(duration, datatype=XSD.string),
                )
            )
        return region_uri

    def add_working(
        self,
        *,
        person: Person,
        org: Organization,
        site: Site | None,
        skills: list[Skill],
        profile: ProfileDocument | None,
        title: str,
        mission_label: str,
        mission_content: str,
        employment_type: str | None,
        start: date | None,
        end: date | None,
        duration: str | None,
        client: Organization | None = None,
        mission_context: str | None = None,
    ) -> tuple[str, str]:
        key = act_of_working_key(
            person.label or "", org.label or "", client.label if client else None, title
        )

        temporal_uri = self.add_temporal_region(
            key=f"{key}-working",
            label=period_label(start, end),
            start=start,
            end=end,
            duration=duration,
        )

        mission = Mission(
            _uri=individual_uri(str(PEOPLE), "Mission", key),
            label=mission_label,
            mission_content=mission_content,
            mission_context=mission_context,
            is_mission_carried_by=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += mission.rdf()
        self.graph.add(
            (URIRef(person._uri), ABI.hasMissionCarried, URIRef(mission._uri))
        )
        if profile:
            self.graph.add(
                (URIRef(mission._uri), ABI.isSourcedFrom, URIRef(profile._uri))
            )

        role = OccupationRole(
            _uri=individual_uri(str(PEOPLE), "OccupationRole", key),
            label=title,
            job_title=title,
            is_occupation_role_of=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += role.rdf()
        self.graph.add(
            (URIRef(person._uri), ABI.hasOccupationRole, URIRef(role._uri))
        )
        self.graph.add((URIRef(role._uri), ABI.hasMission, URIRef(mission._uri)))
        self.graph.add((URIRef(mission._uri), ABI.isMissionOf, URIRef(role._uri)))

        working_uri = individual_uri(str(PEOPLE), "ActOfWorking", key)
        working = ActOfWorking(
            _uri=working_uri,
            label=f"{title} @ {org.label}",
            hasParticipant=[person._uri],
            occursIn=[site._uri] if site else None,
            occupiesTemporalRegion=[temporal_uri] if temporal_uri else None,
            for_organization=[org._uri],
            for_client=[client._uri] if client else None,
            employment_type=employment_type,
            is_act_of_working_of=[person._uri],
            realizes=role._uri,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += working.rdf()

        self.graph.add(
            (URIRef(person._uri), ABI.hasActOfWorking, URIRef(working_uri))
        )
        if site:
            self.graph.add(
                (URIRef(person._uri), ABI.hasWorkLocation, URIRef(site._uri))
            )
        # developsSkill is declared in the shared module, which a process slice does
        # not import, so it is not a field of the entity: the relation is stated here.
        for skill in skills:
            self.graph.add(
                (URIRef(working_uri), ABI.developsSkill, URIRef(skill._uri))
            )
            self.graph.add(
                (URIRef(skill._uri), ABI.isSkillDevelopedIn, URIRef(working_uri))
            )
        self.last_role_uri = role._uri
        return working_uri, role._uri

    def add_studying(
        self,
        *,
        person: Person,
        org: Organization | None,
        site: Site | None,
        skills: list[Skill],
        profile: ProfileDocument | None,
        program: str,
        start: date | None,
        end: date | None,
        duration: str | None = None,
        activities: str | None = None,
    ) -> str:
        # A degree the source names without naming the school is still a degree
        # the person holds. The act is recorded; who ran it simply is not known.
        key = slug(person.label or "", org.label if org else "", program)

        temporal_uri = self.add_temporal_region(
            key=f"{key}-studying",
            label=period_label(start, end),
            start=start,
            end=end,
            duration=duration,
        )

        role = StudentRole(
            _uri=individual_uri(str(PEOPLE), "StudentRole", key),
            label=f"Student - {program}",
            is_student_role_of=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += role.rdf()
        self.graph.add((URIRef(person._uri), ABI.hasStudentRole, URIRef(role._uri)))

        enrollment = EnrollmentRecord(
            _uri=individual_uri(str(PEOPLE), "EnrollmentRecord", key),
            label=f"Enrollment - {program}",
            program_name=program,
            enrollment_date=start,
            completion_date=end,
            is_enrollment_record_of=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += enrollment.rdf()
        self.graph.add(
            (URIRef(person._uri), ABI.hasEnrollmentRecord, URIRef(enrollment._uri))
        )
        if profile:
            self.graph.add(
                (URIRef(enrollment._uri), ABI.isSourcedFrom, URIRef(profile._uri))
            )
        if activities:
            self.graph.add(
                (
                    URIRef(enrollment._uri),
                    ABI.activities_content,
                    Literal(activities, datatype=XSD.string),
                )
            )

        degree = AcademicDegree(
            _uri=individual_uri(str(PEOPLE), "AcademicDegree", key),
            label=program,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += degree.rdf()
        if profile:
            self.graph.add(
                (URIRef(degree._uri), ABI.isSourcedFrom, URIRef(profile._uri))
            )

        studying_uri = individual_uri(str(PEOPLE), "ActOfStudying", key)
        studying = ActOfStudying(
            _uri=studying_uri,
            label=f"{program} @ {org.label}" if org else program,
            hasParticipant=[person._uri],
            occursIn=[site._uri] if site else None,
            occupiesTemporalRegion=[temporal_uri] if temporal_uri else None,
            for_educational_organization=[org._uri] if org else None,
            has_enrollment=enrollment._uri,
            has_degree=degree._uri,
            is_act_of_studying_of=[person._uri],
            realizes=role._uri,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += studying.rdf()

        self.graph.add(
            (URIRef(person._uri), ABI.hasActOfStudying, URIRef(studying_uri))
        )
        if site:
            self.graph.add(
                (URIRef(person._uri), ABI.hasStudyLocation, URIRef(site._uri))
            )
        # developsSkill is declared in the shared module, which a process slice does
        # not import, so it is not a field of the entity: the relation is stated here.
        for skill in skills:
            self.graph.add(
                (URIRef(studying_uri), ABI.developsSkill, URIRef(skill._uri))
            )
            self.graph.add(
                (URIRef(skill._uri), ABI.isSkillDevelopedIn, URIRef(studying_uri))
            )
        return studying_uri


def bind_graph_prefixes(graph: Graph) -> None:
    graph.bind("abi", ABI)
    graph.bind("people", PEOPLE)
    graph.bind("cco", CCO)
