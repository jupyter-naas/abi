#!/usr/bin/env python3
"""Build the personnel demo instance graph from ontology Python classes.

Loads schema TTLs under ``ontologies/`` (modules + processes) and emits demo
individuals with the generated RDFEntity classes. The working experiences are
transcribed from ``apps/cockpit/data/source/person/*/index.json`` (one row =
one process per ``index.json``)
and expanded into the seven buckets the Act of Working slice declares:

    WHO          Person, Organization
    WHAT         ActOfWorking
    WHEN         TemporalRegion → two TemporalInstants (last one absent if ongoing)
    WHERE        Site
    WHY          EmployeeRole → concretizes → Mission
    HOW IT IS    Skill (borne by the person, developed in the act)
    HOW WE KNOW  Mission, EmploymentContract, ProfileDocument

Writes::

    data/graph/personnel_demo.ttl

Run from the personnel module root or any cwd::

    python scripts/generate_demo_graph.py
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path

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
    EmploymentRecord,
    EmploymentStatus,
    EnrollmentRecord,
    JobDescription,
    JobPosition,
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
from naas_abi_marketplace.domains.personnel.scripts.load_person_sources import (
    load_person_sources,
    sources_to_employees,
    sources_to_experiences,
    sources_to_profile_urls,
)
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

PERSONNEL_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGIES = PERSONNEL_ROOT / "ontologies"
GRAPH_DIR = PERSONNEL_ROOT / "data" / "graph"
GRAPH_FILE = GRAPH_DIR / "personnel_demo.ttl"
SOURCE_DIR = PERSONNEL_ROOT / "apps" / "cockpit" / "data" / "source" / "person"

ABI = Namespace("http://ontology.naas.ai/abi/")
PERSONNEL = Namespace("http://ontology.naas.ai/personnel/")
CCO = Namespace("https://www.commoncoreontologies.org/")
BFO = Namespace("http://purl.obolibrary.org/obo/")
GRAPH_NAME = URIRef("http://ontology.naas.ai/graph/personnel")

# Roster and experiences are loaded from apps/cockpit/data/source/person/*/index.json
# at build time (see scripts/load_person_sources.py).


def _slug(*parts: str) -> str:
    joined = "-".join(p.strip().lower() for p in parts if p and str(p).strip())
    return re.sub(r"[^a-z0-9_\-]+", "-", joined).strip("-") or "unknown"


def _uri(ns: str, class_name: str, stable_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", stable_id)
    return f"{ns}{class_name}/{safe}"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _add_temporal_region(
    graph: Graph,
    *,
    key: str,
    label: str,
    start: date,
    end: date | None,
    duration: str | None = None,
) -> str:
    """Emit one temporal region bounded by a first and, unless ongoing, a last instant.

    ``abi:TemporalRegion`` is ``owl:equivalentClass bfo:BFO_0000008`` and
    ``abi:TemporalInstant`` is equivalent to ``bfo:BFO_0000203``, so this
    satisfies the ``BFO_0000199 someValuesFrom BFO_0000008`` restrictions the
    process ontologies declare. Each instant carries ``personnel:instant_date``
    so downstream SPARQL can order processes by recency.

    An ongoing experience (LinkedIn "Present") gets **no** last instant: the
    region is genuinely open, and inventing a closing bound would assert an end
    that has not happened.
    """

    def instant(bound: str, moment: date) -> str:
        uri = _uri(str(ABI), "TemporalInstant", f"{key}-{bound}-{moment.isoformat()}")
        node = TemporalInstant(
            _uri=uri,
            label=moment.strftime("%d/%m/%Y"),
            created=_now(),
            creator="generate_demo_graph",
        )
        for triple in node.rdf():
            graph.add(triple)
        graph.add(
            (URIRef(uri), PERSONNEL.instant_date, Literal(moment, datatype=XSD.date))
        )
        return uri

    first_uri = instant("start", start)
    last_uri = instant("end", end) if end else None

    region_uri = _uri(str(ABI), "TemporalRegion", key)
    region = AbiTemporalRegion(
        _uri=region_uri,
        label=label,
        has_first_instant=[first_uri],
        has_last_instant=[last_uri] if last_uri else None,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += region.rdf()
    if duration:
        graph.add(
            (
                URIRef(region_uri),
                PERSONNEL.duration_label,
                Literal(duration, datatype=XSD.string),
            )
        )
    return region_uri


def load_schema_graph() -> Graph:
    """Parse ontology TTLs (schema only - modules + processes)."""
    g = Graph()
    for path in sorted(ONTOLOGIES.rglob("*.ttl")):
        if "queries" in path.parts:
            continue
        g.parse(path, format="turtle")
        print(f"  schema  {path.relative_to(PERSONNEL_ROOT)}")
    return g


def _ensure_person(
    graph: Graph, cache: dict[str, Person], first: str, last: str
) -> Person:
    key = f"{first} {last}"
    if key in cache:
        return cache[key]
    uri = _uri(str(ABI), "Person", _slug(first, last))
    person = Person(
        _uri=uri,
        label=key,
        first_name=first,
        last_name=last,
        full_name=key,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += person.rdf()
    graph.add((URIRef(uri), RDF.type, CCO.ont00000562))
    graph.add((URIRef(uri), PERSONNEL.given_name, Literal(first, datatype=XSD.string)))
    graph.add((URIRef(uri), PERSONNEL.family_name, Literal(last, datatype=XSD.string)))
    cache[key] = person
    return person


def _ensure_org(
    graph: Graph, cache: dict[str, Organization], label: str, *, educational: bool = False
) -> Organization:
    if label in cache:
        return cache[label]
    org = Organization(
        _uri=_uri(str(ABI), "Organization", _slug(label)),
        label=label,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += org.rdf()
    if educational:
        graph.add((URIRef(org._uri), RDF.type, CCO.ont00000564))
    cache[label] = org
    return org


def _ensure_site(graph: Graph, cache: dict[str, Site], label: str) -> Site:
    if label in cache:
        return cache[label]
    site = Site(
        _uri=_uri(str(PERSONNEL), "Site", _slug(label)),
        label=label,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += site.rdf()
    cache[label] = site
    return site


def _ensure_skill(
    graph: Graph, cache: dict[str, Skill], name: str, person: Person
) -> Skill:
    """One Skill node per person and name.

    A skill is a quality inhering in the person, not in the act, so the same
    skill exercised across several jobs is a single node that several acts of
    working point at - which is what makes those jobs neighbours in the graph.
    """
    key = f"{person.label}|{name}"
    if key in cache:
        return cache[key]
    skill = Skill(
        _uri=_uri(str(PERSONNEL), "Skill", _slug(person.label or "", name)),
        label=name,
        skill_name=name,
        inheresIn=[person._uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += skill.rdf()
    graph.add((URIRef(person._uri), PERSONNEL.hasSkill, URIRef(skill._uri)))
    cache[key] = skill
    return skill


def _add_profile_document(
    graph: Graph, person: Person, source_url: str
) -> ProfileDocument:
    """The LinkedIn page every experience below was read from."""
    doc = ProfileDocument(
        _uri=_uri(str(PERSONNEL), "ProfileDocument", _slug(person.label or "", "linkedin")),
        label=f"LinkedIn experience - {person.label}",
        source_url=source_url,
        is_profile_document_of=[person._uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += doc.rdf()
    graph.add((URIRef(person._uri), PERSONNEL.hasProfileDocument, URIRef(doc._uri)))
    return doc


def _add_working(
    graph: Graph,
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
    """Emit one act of working and everything hanging off it.

    Returns ``(act_uri, position_uri)`` - the roster pass tags the position of a
    person's current job with its job family rather than minting a second,
    competing position for the same post.
    """
    key = _slug(person.label or "", org.label or "", title)

    temporal_uri = _add_temporal_region(
        graph,
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

    # HOW WE KNOW - the stated remit. Opening sentence is the label, full text
    # is the content, and provenance points back at the profile page.
    mission = Mission(
        _uri=_uri(str(PERSONNEL), "Mission", key),
        label=mission_label,
        mission_content=mission_content,
        is_mission_carried_by=[person._uri],
        is_sourced_from=[profile._uri] if profile else None,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += mission.rdf()
    graph.add((URIRef(person._uri), PERSONNEL.hasMissionCarried, URIRef(mission._uri)))

    # HOW WE KNOW - the position as published by the organization.
    position = JobPosition(
        _uri=_uri(str(PERSONNEL), "JobPosition", key),
        label=title,
        job_title=title,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += position.rdf()

    # WHY - the role the person bears, concretizing both position and mission.
    role = EmployeeRole(
        _uri=_uri(str(PERSONNEL), "EmployeeRole", key),
        label=title,
        is_employee_role_of=[person._uri],
        has_job_position=[position._uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += role.rdf()
    graph.add((URIRef(person._uri), PERSONNEL.hasEmployeeRole, URIRef(role._uri)))
    # No reasoner runs over the demo graph, so the owl:inverseOf pair has to be
    # asserted by hand - find_open_job_positions tests the inverse direction.
    graph.add((URIRef(position._uri), PERSONNEL.isJobPositionOf, URIRef(role._uri)))
    # personnel:hasMission lives in the process slice, so it is not a field on
    # the shared EmployeeRole model - assert the role → mission link directly.
    graph.add((URIRef(role._uri), PERSONNEL.hasMission, URIRef(mission._uri)))
    graph.add((URIRef(mission._uri), PERSONNEL.isMissionOf, URIRef(role._uri)))

    contract_uri = None
    if contract_type:
        contract = EmploymentContract(
            _uri=_uri(str(PERSONNEL), "EmploymentContract", key),
            label=f"{contract_type} - {person.label} / {org.label}",
            created=_now(),
            creator="generate_demo_graph",
        )
        graph += contract.rdf()
        graph.add(
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
            _uri=_uri(str(PERSONNEL), "Remuneration", key),
            label=f"{int(remuneration_amount):,} {remuneration_currency}/year".replace(
                ",", " "
            ),
            remuneration_amount=remuneration_amount,
            remuneration_currency=remuneration_currency,
            inheresIn=[person._uri],
            created=_now(),
            creator="generate_demo_graph",
        )
        graph += remuneration.rdf()
        participants.append(remuneration._uri)

    working_uri = _uri(str(PERSONNEL), "ActOfWorking", key)
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
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += working.rdf()

    graph.add((URIRef(person._uri), PERSONNEL.hasActOfWorking, URIRef(working_uri)))
    # WHO ↔ WHERE - the shortcut from the worker to the site of execution.
    graph.add((URIRef(person._uri), PERSONNEL.hasWorkLocation, URIRef(site._uri)))
    for skill in skills:
        graph.add(
            (URIRef(skill._uri), PERSONNEL.isSkillDevelopedIn, URIRef(working_uri))
        )
    return working_uri, position._uri


def _add_studying(
    graph: Graph,
    *,
    person: Person,
    org: Organization,
    site: Site,
    program: str,
    start: date,
    end: date,
) -> str:
    key = _slug(person.label or "", program)

    temporal_uri = _add_temporal_region(
        graph,
        key=f"{key}-studying",
        label=f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}",
        start=start,
        end=end,
    )

    role = StudentRole(
        _uri=_uri(str(PERSONNEL), "StudentRole", key),
        label=f"Student - {program}",
        is_student_role_of=[person._uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += role.rdf()
    graph.add((URIRef(person._uri), PERSONNEL.hasStudentRole, URIRef(role._uri)))

    enrollment = EnrollmentRecord(
        _uri=_uri(str(PERSONNEL), "EnrollmentRecord", key),
        label=f"Enrollment - {program}",
        program_name=program,
        enrollment_date=start,
        completion_date=end,
        is_enrollment_record_of=[person._uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += enrollment.rdf()
    graph.add(
        (URIRef(person._uri), PERSONNEL.hasEnrollmentRecord, URIRef(enrollment._uri))
    )

    degree = AcademicDegree(
        _uri=_uri(str(PERSONNEL), "AcademicDegree", key),
        label=program,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += degree.rdf()

    studying_uri = _uri(str(PERSONNEL), "ActOfStudying", key)
    studying = ActOfStudying(
        _uri=studying_uri,
        label=f"{program} @ {org.label}",
        hasParticipant=[person._uri],
        occursIn=[site._uri],
        occupiesTemporalRegion=[temporal_uri],
        for_educational_organization=[org._uri],
        has_enrollment=enrollment._uri,
        is_act_of_studying_of=[person._uri],
        realizes=role._uri,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += studying.rdf()
    graph.add((URIRef(person._uri), PERSONNEL.hasActOfStudying, URIRef(studying_uri)))
    return studying_uri


def build_instances() -> Graph:
    """Emit demo individuals from ``source/person/*/index.json``."""
    payloads = load_person_sources(SOURCE_DIR)
    employees = sources_to_employees(payloads)
    profile_urls = sources_to_profile_urls(payloads)
    experiences = sources_to_experiences(payloads)

    g = Graph()
    people: dict[str, Person] = {}
    orgs: dict[str, Organization] = {}
    sites: dict[str, Site] = {}
    skills: dict[str, Skill] = {}

    profiles: dict[str, ProfileDocument] = {}
    current_position: dict[str, str] = {}

    for item in experiences:
        first, last = item["person"]
        person = _ensure_person(g, people, first, last)
        person_key = person.label or f"{first} {last}"

        if item["kind"] == "studying":
            _add_studying(
                g,
                person=person,
                org=_ensure_org(g, orgs, item["organization"], educational=True),
                site=_ensure_site(g, sites, item["site"]),
                program=item["program"],
                start=item["start"],
                end=item["end"],
            )
            continue

        if person_key not in profiles:
            profile_url = profile_urls.get(person_key)
            if not profile_url:
                raise KeyError(f"No profile URL for {person_key!r}")
            profiles[person_key] = _add_profile_document(g, person, profile_url)

        org = _ensure_org(g, orgs, item["organization"])
        site = _ensure_site(g, sites, item["site"])
        exp_skills = [_ensure_skill(g, skills, name, person) for name in item["skills"]]

        roster = next(
            (
                e
                for e in employees
                if (e["first"], e["last"]) == item["person"]
                and item["organization"].lower().startswith("naas")
            ),
            None,
        )
        remuneration = item.get("remuneration_amount")
        if remuneration is None and roster:
            remuneration = roster.get("remuneration")

        _, position_uri = _add_working(
            g,
            person=person,
            org=org,
            site=site,
            skills=exp_skills,
            profile=profiles[person_key],
            title=item["title"],
            mission_label=item["mission_label"],
            mission_content=item["mission"],
            contract_type=item["contract_type"],
            start=item["start"],
            end=item["end"],
            duration=item["duration"],
            remuneration_amount=remuneration,
            remuneration_currency=item.get("remuneration_currency") or "EUR",
        )
        if roster:
            current_position[person.label] = position_uri

    for emp in employees:
        person = _ensure_person(g, people, emp["first"], emp["last"])
        slug = _slug(emp["first"], emp["last"])

        desc = JobDescription(
            _uri=_uri(str(PERSONNEL), "JobDescription", f"{slug}-{emp['employee_id']}"),
            label=f"{emp['job_title']} - {emp['job_family']}",
            created=_now(),
            creator="generate_demo_graph",
        )
        g += desc.rdf()

        record = EmploymentRecord(
            _uri=_uri(str(PERSONNEL), "EmploymentRecord", emp["employee_id"]),
            label=f"Employment record {emp['employee_id']}",
            employee_id=emp["employee_id"],
            hire_date=emp["hire_date"],
            termination_date=emp.get("termination_date"),
            is_employment_record_of=[person._uri],
            created=_now(),
            creator="generate_demo_graph",
        )
        g += record.rdf()
        g.add((URIRef(person._uri), PERSONNEL.hasEmploymentRecord, URIRef(record._uri)))

        # job_family marks the one position that counts as the person's current
        # post. Roster reporting keys off it, so exactly one position per person
        # may carry it - every other position they have ever held must not.
        position_uri = current_position.get(person.label or "")
        if position_uri is None:
            # No current act of working for this person, so the post itself is
            # only documented by the roster: mint it, and the role that fills it.
            position = JobPosition(
                _uri=_uri(str(PERSONNEL), "JobPosition", f"{slug}-roster"),
                label=emp["job_title"],
                job_title=emp["job_title"],
                has_job_description=[desc._uri],
                created=_now(),
                creator="generate_demo_graph",
            )
            g += position.rdf()
            position_uri = position._uri

            role = EmployeeRole(
                _uri=_uri(str(PERSONNEL), "EmployeeRole", f"{slug}-roster"),
                label=emp["job_title"],
                is_employee_role_of=[person._uri],
                has_job_position=[position_uri],
                created=_now(),
                creator="generate_demo_graph",
            )
            g += role.rdf()
            g.add((URIRef(person._uri), PERSONNEL.hasEmployeeRole, URIRef(role._uri)))
            g.add((URIRef(position_uri), PERSONNEL.isJobPositionOf, URIRef(role._uri)))
        else:
            g.add((URIRef(position_uri), PERSONNEL.hasJobDescription, URIRef(desc._uri)))

        g.add(
            (
                URIRef(position_uri),
                PERSONNEL.job_family,
                Literal(emp["job_family"], datatype=XSD.string),
            )
        )

        status = EmploymentStatus(
            _uri=_uri(str(PERSONNEL), "EmploymentStatus", slug),
            label=emp["status"],
            status_value=emp["status"],
            is_employment_status_of=[person._uri],
            created=_now(),
            creator="generate_demo_graph",
        )
        g += status.rdf()
        g.add(
            (URIRef(person._uri), PERSONNEL.hasEmploymentStatus, URIRef(status._uri))
        )

    return g


def bind_prefixes(g: Graph) -> None:
    g.bind("abi", ABI)
    g.bind("personnel", PERSONNEL)
    g.bind("cco", CCO)
    g.bind("bfo", BFO)


def main() -> None:
    print("Loading ontology schema…")
    schema = load_schema_graph()

    print("Building demo individuals…")
    instances = build_instances()

    out = Graph()
    out += schema
    out += instances
    bind_prefixes(out)

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    out.serialize(destination=str(GRAPH_FILE), format="turtle")

    print(
        f"\nWrote {GRAPH_FILE.relative_to(PERSONNEL_ROOT)} "
        f"({len(schema)} schema + {len(instances)} instance triples)"
    )


if __name__ == "__main__":
    main()
