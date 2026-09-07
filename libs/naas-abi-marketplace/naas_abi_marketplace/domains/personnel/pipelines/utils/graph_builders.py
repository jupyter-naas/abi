"""Shared RDF builders for personnel process pipelines."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from naas_abi.ontologies.modules.ABIOntology import (
    Organization,
    Person,
    Site,
    TemporalInstant,
)
from naas_abi.ontologies.modules.ABIOntology import TemporalRegion as AbiTemporalRegion
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    AcademicDegree,
    EmployeeRole,
    EmploymentContract,
    EnrollmentRecord,
    Remuneration,
    StudentRole,
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.ActOfStudyingProcess import (
    ActOfStudying,
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.ActOfWorkingProcess import (
    ActOfWorking,
    Mission,
    ProfileDocument,
    Skill,
)
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

ABI = Namespace("http://ontology.naas.ai/abi/")
PERSONNEL = Namespace("http://ontology.naas.ai/personnel/")
CCO = Namespace("https://www.commoncoreontologies.org/")


def slug(*parts: str) -> str:
    joined = "-".join(p.strip().lower() for p in parts if p and str(p).strip())
    return re.sub(r"[^a-z0-9_\-]+", "-", joined).strip("-") or "unknown"


def individual_uri(ns: str, class_name: str, stable_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", stable_id)
    return f"{ns}{class_name}/{safe}"


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class PersonnelGraphContext:
    """Mutable builder state shared across process pipelines in one batch."""

    graph: Graph = field(default_factory=Graph)
    creator: str = "personnel_pipeline"
    people: dict[str, Person] = field(default_factory=dict)
    orgs: dict[str, Organization] = field(default_factory=dict)
    sites: dict[str, Site] = field(default_factory=dict)
    skills: dict[str, Skill] = field(default_factory=dict)
    work_profiles: dict[str, ProfileDocument] = field(default_factory=dict)
    education_profiles: dict[str, ProfileDocument] = field(default_factory=dict)
    last_position_uri: str | None = None

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
            (URIRef(uri), PERSONNEL.given_name, Literal(first, datatype=XSD.string))
        )
        self.graph.add(
            (URIRef(uri), PERSONNEL.family_name, Literal(last, datatype=XSD.string))
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
            _uri=individual_uri(str(PERSONNEL), "Site", slug(label)),
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
            _uri=individual_uri(str(PERSONNEL), "Skill", slug(person.label or "", name)),
            label=name,
            skill_name=name,
            inheresIn=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += skill.rdf()
        self.graph.add((URIRef(person._uri), PERSONNEL.hasSkill, URIRef(skill._uri)))
        self.skills[key] = skill
        return skill

    def ensure_work_profile(self, person: Person, source_url: str) -> ProfileDocument:
        key = person.label or ""
        if key in self.work_profiles:
            return self.work_profiles[key]
        doc = ProfileDocument(
            _uri=individual_uri(
                str(PERSONNEL), "ProfileDocument", slug(key, "linkedin")
            ),
            label=f"LinkedIn experience - {person.label}",
            source_url=source_url,
            is_profile_document_of=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += doc.rdf()
        self.graph.add((URIRef(person._uri), PERSONNEL.hasProfileDocument, URIRef(doc._uri)))
        self.work_profiles[key] = doc
        return doc

    def ensure_education_profile(self, person: Person, source_url: str) -> ProfileDocument:
        key = person.label or ""
        if key in self.education_profiles:
            return self.education_profiles[key]
        doc = ProfileDocument(
            _uri=individual_uri(
                str(PERSONNEL), "ProfileDocument", slug(key, "linkedin-education")
            ),
            label=f"LinkedIn education - {person.label}",
            source_url=source_url,
            is_profile_document_of=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += doc.rdf()
        self.graph.add((URIRef(person._uri), PERSONNEL.hasProfileDocument, URIRef(doc._uri)))
        self.education_profiles[key] = doc
        return doc

    def add_temporal_region(
        self,
        *,
        key: str,
        label: str,
        start: date,
        end: date | None,
        duration: str | None = None,
    ) -> str:
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
                (URIRef(uri), PERSONNEL.instant_date, Literal(moment, datatype=XSD.date))
            )
            return uri

        first_uri = instant("start", start)
        last_uri = instant("end", end) if end else None

        region_uri = individual_uri(str(ABI), "TemporalRegion", key)
        region = AbiTemporalRegion(
            _uri=region_uri,
            label=label,
            has_first_instant=[first_uri],
            has_last_instant=[last_uri] if last_uri else None,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += region.rdf()
        if duration:
            self.graph.add(
                (
                    URIRef(region_uri),
                    PERSONNEL.duration_label,
                    Literal(duration, datatype=XSD.string),
                )
            )
        return region_uri

    def add_working(
        self,
        *,
        person: Person,
        org: Organization,
        site: Site,
        skills: list[Skill],
        profile: ProfileDocument | None,
        title: str,
        mission_label: str,
        mission_content: str,
        contract_type: str | None,
        start: date,
        end: date | None,
        duration: str | None,
        remuneration_amount: float | None = None,
        remuneration_currency: str = "EUR",
    ) -> tuple[str, str]:
        key = slug(person.label or "", org.label or "", title)

        temporal_uri = self.add_temporal_region(
            key=f"{key}-working",
            label=(
                f"{start.strftime('%b %Y')} – Present"
                if end is None
                else f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"
            ),
            start=start,
            end=end,
            duration=duration,
        )

        mission = Mission(
            _uri=individual_uri(str(PERSONNEL), "Mission", key),
            label=mission_label,
            mission_content=mission_content,
            is_mission_carried_by=[person._uri],
            is_sourced_from=[profile._uri] if profile else None,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += mission.rdf()
        self.graph.add(
            (URIRef(person._uri), PERSONNEL.hasMissionCarried, URIRef(mission._uri))
        )

        from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
            JobPosition,
        )

        position = JobPosition(
            _uri=individual_uri(str(PERSONNEL), "JobPosition", key),
            label=title,
            job_title=title,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += position.rdf()

        role = EmployeeRole(
            _uri=individual_uri(str(PERSONNEL), "EmployeeRole", key),
            label=title,
            is_employee_role_of=[person._uri],
            has_job_position=[position._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += role.rdf()
        self.graph.add((URIRef(person._uri), PERSONNEL.hasEmployeeRole, URIRef(role._uri)))
        self.graph.add(
            (URIRef(position._uri), PERSONNEL.isJobPositionOf, URIRef(role._uri))
        )
        self.graph.add((URIRef(role._uri), PERSONNEL.hasMission, URIRef(mission._uri)))
        self.graph.add((URIRef(mission._uri), PERSONNEL.isMissionOf, URIRef(role._uri)))

        contract_uri = None
        if contract_type:
            contract = EmploymentContract(
                _uri=individual_uri(str(PERSONNEL), "EmploymentContract", key),
                label=f"{contract_type} - {person.label} / {org.label}",
                created=utc_now(),
                creator=self.creator,
            )
            self.graph += contract.rdf()
            self.graph.add(
                (
                    URIRef(contract._uri),
                    PERSONNEL.contract_type,
                    Literal(contract_type, datatype=XSD.string),
                )
            )
            contract_uri = contract._uri

        participants = [person._uri]
        if remuneration_amount:
            remuneration = Remuneration(
                _uri=individual_uri(str(PERSONNEL), "Remuneration", key),
                label=f"{int(remuneration_amount):,} {remuneration_currency}/year".replace(
                    ",", " "
                ),
                remuneration_amount=remuneration_amount,
                remuneration_currency=remuneration_currency,
                inheresIn=[person._uri],
                created=utc_now(),
                creator=self.creator,
            )
            self.graph += remuneration.rdf()
            participants.append(remuneration._uri)

        working_uri = individual_uri(str(PERSONNEL), "ActOfWorking", key)
        working = ActOfWorking(
            _uri=working_uri,
            label=f"{title} @ {org.label}",
            hasParticipant=participants,
            occursIn=[site._uri],
            occupiesTemporalRegion=[temporal_uri],
            for_organization=[org._uri],
            has_contract=contract_uri,
            is_act_of_working_of=[person._uri],
            realizes=role._uri,
            develops_skill=[s._uri for s in skills] or None,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += working.rdf()

        self.graph.add((URIRef(person._uri), PERSONNEL.hasActOfWorking, URIRef(working_uri)))
        self.graph.add((URIRef(person._uri), PERSONNEL.hasWorkLocation, URIRef(site._uri)))
        for skill in skills:
            self.graph.add(
                (URIRef(skill._uri), PERSONNEL.isSkillDevelopedIn, URIRef(working_uri))
            )
        self.last_position_uri = position._uri
        return working_uri, position._uri

    def add_studying(
        self,
        *,
        person: Person,
        org: Organization,
        site: Site,
        skills: list[Skill],
        profile: ProfileDocument | None,
        program: str,
        start: date,
        end: date | None,
        duration: str | None = None,
        activities: str | None = None,
    ) -> str:
        key = slug(person.label or "", org.label or "", program)

        temporal_uri = self.add_temporal_region(
            key=f"{key}-studying",
            label=(
                f"{start.strftime('%b %Y')} – Present"
                if end is None
                else f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"
            ),
            start=start,
            end=end,
            duration=duration,
        )

        role = StudentRole(
            _uri=individual_uri(str(PERSONNEL), "StudentRole", key),
            label=f"Student - {program}",
            is_student_role_of=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += role.rdf()
        self.graph.add((URIRef(person._uri), PERSONNEL.hasStudentRole, URIRef(role._uri)))

        enrollment = EnrollmentRecord(
            _uri=individual_uri(str(PERSONNEL), "EnrollmentRecord", key),
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
            (URIRef(person._uri), PERSONNEL.hasEnrollmentRecord, URIRef(enrollment._uri))
        )
        if profile:
            self.graph.add(
                (URIRef(enrollment._uri), PERSONNEL.isSourcedFrom, URIRef(profile._uri))
            )
        if activities:
            self.graph.add(
                (
                    URIRef(enrollment._uri),
                    PERSONNEL.activities_content,
                    Literal(activities, datatype=XSD.string),
                )
            )

        degree = AcademicDegree(
            _uri=individual_uri(str(PERSONNEL), "AcademicDegree", key),
            label=program,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += degree.rdf()
        if profile:
            self.graph.add((URIRef(degree._uri), PERSONNEL.isSourcedFrom, URIRef(profile._uri)))

        studying_uri = individual_uri(str(PERSONNEL), "ActOfStudying", key)
        studying = ActOfStudying(
            _uri=studying_uri,
            label=f"{program} @ {org.label}",
            hasParticipant=[person._uri],
            occursIn=[site._uri],
            occupiesTemporalRegion=[temporal_uri],
            for_educational_organization=[org._uri],
            has_enrollment=enrollment._uri,
            has_degree=degree._uri,
            is_act_of_studying_of=[person._uri],
            realizes=role._uri,
            develops_skill=[s._uri for s in skills] or None,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += studying.rdf()

        self.graph.add((URIRef(person._uri), PERSONNEL.hasActOfStudying, URIRef(studying_uri)))
        self.graph.add((URIRef(person._uri), PERSONNEL.hasStudyLocation, URIRef(site._uri)))
        for skill in skills:
            self.graph.add(
                (URIRef(skill._uri), PERSONNEL.isSkillDevelopedIn, URIRef(studying_uri))
            )
        return studying_uri


def bind_graph_prefixes(graph: Graph) -> None:
    graph.bind("abi", ABI)
    graph.bind("personnel", PERSONNEL)
    graph.bind("cco", CCO)
