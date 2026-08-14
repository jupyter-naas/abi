#!/usr/bin/env python3
"""Build the personnel demo instance graph from ontology Python classes.

Loads schema TTLs under ``ontologies/`` (modules + processes) and emits demo
individuals with the generated RDFEntity classes (``abi:Person``,
``personnel:EmploymentRecord``, birth process classes, …). Writes:

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
from naas_abi_marketplace.domains.personnel.individual_uri import (
    personnel_individual_uri,
)
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    AcademicDegree,
    BiologicalSex,
    BirthRecord,
    EmployeeRole,
    EmploymentContract,
    EmploymentRecord,
    EmploymentStatus,
    EnrollmentRecord,
    EyeColor,
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
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.BirthProcess import (
    Birth,
    BirthDeclarationAct,
<<<<<<< HEAD
    BirthProcess,
=======
    BirthRecord,
    BirthRegistrationProcess,
    EyeColor,
    Site,
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.WorkingProcess import (
    EmploymentContract,
    Remuneration,
    Working,
>>>>>>> d0afb02f6501efac691b56296165d7e6077a0e56
)
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

PERSONNEL_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGIES = PERSONNEL_ROOT / "ontologies"
GRAPH_DIR = PERSONNEL_ROOT / "data" / "graph"
GRAPH_FILE = GRAPH_DIR / "personnel_demo.ttl"

ABI = Namespace("http://ontology.naas.ai/abi/")
PERSONNEL = Namespace("http://ontology.naas.ai/personnel/")
CCO = Namespace("https://www.commoncoreontologies.org/")
BFO = Namespace("http://purl.obolibrary.org/obo/")
GRAPH_NAME = URIRef("http://ontology.naas.ai/graph/personnel")

EMPLOYEES = [
    {
        "first": "Jeremy",
        "last": "Ravenel",
        "employee_id": "E-10428",
        "job_title": "CEO",
        "job_family": "Executive",
        "hire_date": date(2018, 3, 1),
        "status": "active",
        "birth_date": date(1989, 12, 5),
        "birth_site": "Vitré",
        "sex": "Male",
        "eye_color": "Green",
        "rich_birth": True,
        "mother": ("Christine", "Ravenel"),
        "father": ("Pascal", "Ravenel"),
        "work_site": "Paris",
        "remuneration": 120_000,
    },
    {
        "first": "Florent",
        "last": "Ravenel",
        "employee_id": "E-10429",
        "job_title": "COO",
        "job_family": "Executive",
        "hire_date": date(2019, 6, 15),
        "status": "active",
        "birth_date": date(1991, 4, 18),
        "sex": "Male",
        "work_site": "Paris",
        "remuneration": 95_000,
        "mother": ("Marie", "Ravenel"),
        "father": ("Henri", "Ravenel"),
    },
    {
        "first": "Maxime",
        "last": "Jublou",
        "employee_id": "E-10430",
        "job_title": "CTO",
        "job_family": "Executive",
        "hire_date": date(2020, 1, 10),
        "status": "active",
        "birth_date": date(1988, 9, 22),
        "sex": "Male",
        "work_site": "Paris",
        "remuneration": 85_000,
    },
]


# Parents are demo stubs, but every Birth process still needs a temporal region,
# so each one gets a plausible date of its own.
PARENT_BIRTH_DATES = {
    ("Christine", "Ravenel"): date(1962, 3, 14),
    ("Pascal", "Ravenel"): date(1959, 11, 2),
    ("Marie", "Ravenel"): date(1964, 7, 21),
    ("Henri", "Ravenel"): date(1961, 5, 9),
}


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
    end: date,
) -> str:
    """Emit one temporal region bounded by a first and a last temporal instant.

    ``abi:TemporalRegion`` is ``owl:equivalentClass bfo:BFO_0000008`` and
    ``abi:TemporalInstant`` is equivalent to ``bfo:BFO_0000203``, so this
    satisfies the ``BFO_0000199 someValuesFrom BFO_0000008`` restrictions the
    process ontologies declare. Each instant carries ``personnel:instant_date``
    so downstream SPARQL can order processes by recency.
    """

    instant_uris: list[str] = []
    for bound, moment in (("start", start), ("end", end)):
        uri = _uri(str(ABI), "TemporalInstant", f"{key}-{bound}-{moment.isoformat()}")
        instant = TemporalInstant(
            _uri=uri,
            label=moment.strftime("%d/%m/%Y"),
            created=_now(),
            creator="generate_demo_graph",
        )
        graph += instant.rdf()
<<<<<<< HEAD
        graph.add(
            (URIRef(uri), PERSONNEL.instant_date, Literal(moment, datatype=XSD.date))
        )
=======
        graph.add((URIRef(uri), PERSONNEL.instant_date, Literal(moment, datatype=XSD.date)))
>>>>>>> d0afb02f6501efac691b56296165d7e6077a0e56
        instant_uris.append(uri)

    first_uri, last_uri = instant_uris

    region_uri = _uri(str(ABI), "TemporalRegion", key)
    region = AbiTemporalRegion(
        _uri=region_uri,
        label=label,
        has_first_instant=[first_uri],
        has_last_instant=[last_uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += region.rdf()
    return region_uri


def load_schema_graph() -> Graph:
    """Parse ontology TTLs (schema only — modules + processes)."""
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

    # Role-based names, held as strings on the person. abi:first_name /
    # abi:last_name above are the positional variants and are set separately.
    graph.add((URIRef(uri), PERSONNEL.given_name, Literal(first, datatype=XSD.string)))
    graph.add((URIRef(uri), PERSONNEL.family_name, Literal(last, datatype=XSD.string)))

    cache[key] = person
    return person


def build_instances() -> Graph:
    """Emit employment + birth individuals with ontology classes."""
    g = Graph()
    people: dict[str, Person] = {}

    org = Organization(
        _uri=_uri(str(ABI), "Organization", "demo"),
        label="Naas.ai",
        created=_now(),
        creator="generate_demo_graph",
    )
    g += org.rdf()

    school = Organization(
        _uri=_uri(str(ABI), "Organization", "universite-de-rennes-1"),
        label="Université de Rennes 1",
        created=_now(),
        creator="generate_demo_graph",
    )
    g += school.rdf()
    g.add((URIRef(school._uri), RDF.type, CCO.ont00000564))

    # Family stubs — parents of Jeremy and Florent.
    christine = _ensure_person(g, people, "Christine", "Ravenel")
    pascal = _ensure_person(g, people, "Pascal", "Ravenel")
    marie = _ensure_person(g, people, "Marie", "Ravenel")
    henri = _ensure_person(g, people, "Henri", "Ravenel")
    florent = _ensure_person(g, people, "Florent", "Ravenel")

    for emp in EMPLOYEES:
        person = _ensure_person(g, people, emp["first"], emp["last"])
        slug = _slug(emp["first"], emp["last"])

        desc = JobDescription(
            _uri=_uri(str(PERSONNEL), "JobDescription", f"{slug}-{emp['employee_id']}"),
            label=f"{emp['job_title']} — {emp['job_family']}",
            created=_now(),
            creator="generate_demo_graph",
        )
        g += desc.rdf()

        record = EmploymentRecord(
            _uri=_uri(str(PERSONNEL), "EmploymentRecord", emp["employee_id"]),
            label=f"Employment record {emp['employee_id']}",
            employee_id=emp["employee_id"],
            hire_date=emp["hire_date"],
            is_employment_record_of=[person._uri],
            created=_now(),
            creator="generate_demo_graph",
        )
        g += record.rdf()
        g.add((URIRef(person._uri), PERSONNEL.hasEmploymentRecord, URIRef(record._uri)))

        position = JobPosition(
            _uri=_uri(str(PERSONNEL), "JobPosition", _slug(emp["job_title"])),
            label=emp["job_title"],
            job_title=emp["job_title"],
            job_family=emp["job_family"],
            has_job_description=[desc._uri],
            created=_now(),
            creator="generate_demo_graph",
        )
        g += position.rdf()

        role = EmployeeRole(
            _uri=_uri(str(PERSONNEL), "EmployeeRole", f"{slug}-{emp['employee_id']}"),
            label=f"{emp['job_title']} role — {person.label}",
            is_employee_role_of=[person._uri],
            has_job_position=[position._uri],
            created=_now(),
            creator="generate_demo_graph",
        )
        g += role.rdf()
        g.add((URIRef(person._uri), PERSONNEL.hasEmployeeRole, URIRef(role._uri)))
        g.add((URIRef(position._uri), PERSONNEL.isJobPositionOf, URIRef(role._uri)))

        status = EmploymentStatus(
            _uri=_uri(str(PERSONNEL), "EmploymentStatus", f"{slug}-{emp['status']}"),
            label=f"{person.label} — {emp['status']}",
            status_value=emp["status"],
            created=_now(),
            creator="generate_demo_graph",
        )
        g += status.rdf()
        g.add((URIRef(person._uri), PERSONNEL.hasEmploymentStatus, URIRef(status._uri)))
        g.add(
            (URIRef(status._uri), PERSONNEL.isEmploymentStatusOf, URIRef(person._uri))
        )

        g.add((URIRef(person._uri), PERSONNEL.isEmployedBy, URIRef(org._uri)))
        g.add((URIRef(org._uri), PERSONNEL.employs, URIRef(person._uri)))

        _add_working(
            g,
            person=person,
            org=org,
            role=role,
            desc=desc,
            work_site=emp["work_site"],
            hire_date=emp["hire_date"],
            remuneration_amount=emp["remuneration"],
        )

        mother = (
            _ensure_person(g, people, emp["mother"][0], emp["mother"][1])
            if emp.get("mother")
            else None
        )
        father = (
            _ensure_person(g, people, emp["father"][0], emp["father"][1])
            if emp.get("father")
            else None
        )
        if emp.get("rich_birth"):
            _add_birth(
                g,
                person=person,
                declarant=florent,
                birth_date=emp.get("birth_date"),
                birth_site=emp.get("birth_site"),
                sex=emp.get("sex"),
                eye_color=emp.get("eye_color"),
                mother=mother,
                father=father,
            )
        elif emp.get("birth_date"):
            _add_birth(
                g,
                person=person,
                declarant=florent,
                birth_date=emp.get("birth_date"),
                sex=emp.get("sex"),
                mother=mother,
                father=father,
            )

    # Parent ledger entries — dated so their Birth process has a temporal region too.
    for parent, names in (
        (christine, ("Christine", "Ravenel")),
        (pascal, ("Pascal", "Ravenel")),
        (marie, ("Marie", "Ravenel")),
        (henri, ("Henri", "Ravenel")),
    ):
        _add_birth(
            g,
            person=parent,
            declarant=florent,
            birth_date=PARENT_BIRTH_DATES[names],
        )
<<<<<<< HEAD

    _add_studying(
        g,
        person=florent,
        org=school,
        program="Licence Informatique",
        study_site="Rennes",
        start=date(2009, 9, 1),
        end=date(2014, 6, 30),
    )
=======
>>>>>>> d0afb02f6501efac691b56296165d7e6077a0e56

    return g


def _add_working(
    graph: Graph,
    *,
    person: Person,
    org: Organization,
    role: EmployeeRole,
    desc: JobDescription,
    work_site: str,
    hire_date: date,
    remuneration_amount: float,
    remuneration_currency: str = "EUR",
) -> str:
    slug = _slug(person.label or person._uri)
    working_uri = _uri(str(PERSONNEL), "ActOfWorking", slug)
    contract_uri = _uri(str(PERSONNEL), "EmploymentContract", slug)
    site_uri = _uri(str(PERSONNEL), "Site", _slug(work_site, "work"))
    remuneration_uri = _uri(str(PERSONNEL), "Remuneration", slug)

    site = Site(
        _uri=site_uri,
        label=work_site,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += site.rdf()

    # Employment is ongoing: the region is closed at the generation date so every
    # temporal region has both bounds and recency ordering stays total.
    temporal_uri = _add_temporal_region(
        graph,
        key=f"{slug}-working-{hire_date.isoformat()}",
        label=f"Since {hire_date.strftime('%d/%m/%Y')}",
        start=hire_date,
        end=_now().date(),
    )

    remuneration = Remuneration(
        _uri=remuneration_uri,
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

    contract = EmploymentContract(
        _uri=contract_uri,
        label=f"Contract — {person.label} / {org.label}",
        is_about_job_description=[desc._uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += contract.rdf()

    working = ActOfWorking(
        _uri=working_uri,
<<<<<<< HEAD
        label=f"Act of working — {person.label} @ {org.label}",
        hasParticipant=[person._uri, remuneration._uri],
        occursIn=[site._uri],
        occupiesTemporalRegion=[temporal_uri],
=======
        label=f"Working — {person.label} @ {org.label}",
        bFO_0000057=[person._uri, remuneration._uri],
        bFO_0000066=[site._uri],
        bFO_0000199=[temporal_uri],
>>>>>>> d0afb02f6501efac691b56296165d7e6077a0e56
        for_organization=[org._uri],
        has_contract=contract._uri,
        is_act_of_working_of=[person._uri],
        realizes=role._uri,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += working.rdf()
    graph.add((URIRef(person._uri), PERSONNEL.hasActOfWorking, URIRef(working_uri)))
    return working_uri


def _add_studying(
    graph: Graph,
    *,
    person: Person,
    org: Organization,
    program: str,
    study_site: str,
    start: date,
    end: date,
) -> str:
    slug = _slug(person.label or person._uri)
    studying_uri = _uri(str(PERSONNEL), "ActOfStudying", slug)
    enrollment_uri = _uri(str(PERSONNEL), "EnrollmentRecord", slug)
    role_uri = _uri(str(PERSONNEL), "StudentRole", slug)
    degree_uri = _uri(str(PERSONNEL), "AcademicDegree", slug)
    site_uri = _uri(str(PERSONNEL), "Site", _slug(study_site, "study"))

    site = Site(
        _uri=site_uri,
        label=study_site,
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += site.rdf()

    temporal_uri = _add_temporal_region(
        graph,
        key=f"{slug}-studying-{start.isoformat()}",
        label=f"{start.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}",
        start=start,
        end=end,
    )

    role = StudentRole(
        _uri=role_uri,
        label=f"Student role — {person.label} / {program}",
        is_student_role_of=[person._uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += role.rdf()
    graph.add((URIRef(person._uri), PERSONNEL.hasStudentRole, URIRef(role._uri)))

    enrollment = EnrollmentRecord(
        _uri=enrollment_uri,
        label=f"Enrollment — {person.label} / {program}",
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
        _uri=degree_uri,
        label=f"{program} — {org.label}",
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += degree.rdf()

    studying = ActOfStudying(
        _uri=studying_uri,
        label=f"Act of studying — {person.label} @ {org.label}",
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


def _add_birth(
    graph: Graph,
    *,
    person: Person,
    declarant: Person,
    birth_date: date | None = None,
    birth_site: str | None = None,
    sex: str | None = None,
    eye_color: str | None = None,
    mother: Person | None = None,
    father: Person | None = None,
    declared_on: date = date(2026, 8, 13),
    declared_content: str | None = None,
) -> str:
    """Emit one Birth (natural process) plus ledger registration behind the scenes.

    The canvas focuses on the Birth process and its BFO satellites. The
    registration process and declaration act remain in the graph for SPARQL/logs.
    """
    slug = _slug(person.label or person._uri)
    dslug = _slug(declarant.label or declarant._uri)
    key = f"{slug}-by-{dslug}"
    birth_uri = _uri(str(PERSONNEL), "Birth", slug)
    declaration_uri = personnel_individual_uri(f"BirthDeclarationAct:{key}")
    registration_uri = personnel_individual_uri(f"BirthProcess:{key}")
    record_uri = _uri(str(PERSONNEL), "BirthRecord", key)

    participants: list = [person._uri]
    sites: list = []
    temporals: list = []

    if sex:
        sex_ind = BiologicalSex(
            _uri=_uri(str(PERSONNEL), "BiologicalSex", f"{slug}-{_slug(sex)}"),
            label=sex,
            inheres_in=[person._uri],
            created=_now(),
            creator="generate_demo_graph",
        )
        graph += sex_ind.rdf()
        participants.append(sex_ind)

    if eye_color:
        eye = EyeColor(
            _uri=_uri(str(PERSONNEL), "EyeColor", f"{slug}-{_slug(eye_color)}"),
            label=eye_color,
            inheres_in=[person._uri],
            created=_now(),
            creator="generate_demo_graph",
        )
        graph += eye.rdf()
        participants.append(eye)

    if mother is not None:
        graph.add((URIRef(person._uri), PERSONNEL.hasMother, URIRef(mother._uri)))
    if father is not None:
        graph.add((URIRef(person._uri), PERSONNEL.hasFather, URIRef(father._uri)))

    if birth_site:
        site = Site(
            _uri=_uri(str(PERSONNEL), "Site", _slug(birth_site)),
            label=birth_site,
            created=_now(),
            creator="generate_demo_graph",
        )
        graph += site.rdf()
        sites.append(site._uri)

    # A birth is instantaneous on the scale we model it: both bounds are the day
    # itself. Every Birth process gets its own region, never a shared one.
    if birth_date is not None:
        temporals.append(
            _add_temporal_region(
                graph,
                key=f"{slug}-birth-{birth_date.isoformat()}",
                label=birth_date.strftime("%d/%m/%Y"),
                start=birth_date,
                end=birth_date,
            )
        )

    participant_refs = [p if isinstance(p, str) else p._uri for p in participants]
    # 1. The birth itself — the natural process, one per person.
    birth = Birth(
        _uri=birth_uri,
        label=f"Birth of {person.label}",
        hasParticipant=participant_refs,
        occursIn=sites or None,
        occupiesTemporalRegion=temporals or None,
        is_registered_by=[registration_uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += birth.rdf()
    graph.add((URIRef(person._uri), PERSONNEL.hasBirth, URIRef(birth_uri)))
    graph.add((URIRef(birth_uri), PERSONNEL.isBirthOf, URIRef(person._uri)))

    # 2. The source — who said what, when. Everything about the attestation
    #    hangs off this act rather than off the registration.
    declared_temporal_uri = _add_temporal_region(
        graph,
        key=f"{key}-declared-{declared_on.isoformat()}",
        label=declared_on.isoformat(),
        start=declared_on,
        end=declared_on,
    )

    declaration = BirthDeclarationAct(
        _uri=declaration_uri,
        declared_content=declared_content
        or f"{person.label} was born"
        + (f" on {birth_date.strftime('%d/%m/%Y')}" if birth_date else "")
        + (f" in {birth_site}" if birth_site else "")
        + (f", sex {sex}" if sex else "")
        + (f", eyes {eye_color}" if eye_color else "")
        + (f", mother {mother.label}" if mother else "")
        + (f", father {father.label}" if father else "")
        + ".",
<<<<<<< HEAD
        occupiesTemporalRegion=[declared_temporal_uri],
=======
        bFO_0000199=[declared_temporal_uri],
>>>>>>> d0afb02f6501efac691b56296165d7e6077a0e56
        ont00001833=[declarant._uri],  # has agent
        ont00001829=record_uri,  # has output
        hasParticipant=[declarant._uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += declaration.rdf()

    # 3. The record — about the birth, output by the registration. It is no
    #    longer concretized by the birth: a natural birth produces a child, not
    #    a document.
    record = BirthRecord(
        _uri=record_uri,
        label=f"Birth record — {person.label} (declared by {declarant.label})",
        genericallyDependsOn=[person._uri],
        isConcretizedBy=[registration_uri],
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += record.rdf()
    graph.add((URIRef(record_uri), CCO.ont00001808, URIRef(birth_uri)))

    # 4. The ledger entry. Its own temporal region is ledger time, distinct
    #    from when the birth happened and from when it was declared.
    ledger_temporal_uri = _add_temporal_region(
        graph,
        key=f"{key}-ledger-{declared_on.isoformat()}",
        label=declared_on.isoformat(),
        start=declared_on,
        end=declared_on,
    )

<<<<<<< HEAD
    registration = BirthProcess(
        _uri=registration_uri,
        has_information_source=[declaration_uri],
        registers_birth=[birth_uri],
        ont00001829=record_uri,
        concretizes=record_uri,
        hasParticipant=[person._uri],
        occupiesTemporalRegion=[ledger_temporal_uri],
=======
    registration = BirthRegistrationProcess(
        _uri=registration_uri,
        has_information_source=[declaration_uri],
        registers_birth=[birth_uri],
        ont00001829=[record_uri],
        bFO_0000199=[ledger_temporal_uri],
>>>>>>> d0afb02f6501efac691b56296165d7e6077a0e56
        created=_now(),
        creator="generate_demo_graph",
    )
    graph += registration.rdf()

    return registration_uri


def bind_prefixes(g: Graph) -> None:
    g.bind("abi", ABI)
    g.bind("personnel", PERSONNEL)
    g.bind("cco", CCO)
    g.bind("bfo", BFO)
    g.bind("rdfs", RDFS)
    g.bind("rdf", RDF)
    g.bind("xsd", XSD)


def main() -> None:
    print("Loading ontology schemas…")
    schema = load_schema_graph()
    print("Building demo individuals…")
    instances = build_instances()

    # Named-graph friendly serialization: write instances into a TriG-like
    # Turtle file with an explicit comment; consumers load into the default
    # graph for local SPARQL (GRAPH clauses are stripped by the export script).
    out = Graph()
    bind_prefixes(out)
    out += schema
    out += instances

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    # Drop noisy blank-node-heavy schema axioms from the demo instance file —
    # keep schema headers lightly by re-serializing instances + essential types.
    # Full schema remains available under ontologies/; the demo TTL focuses on
    # queryable individuals for the cockpit fallback.
    demo = Graph()
    bind_prefixes(demo)
    demo += instances
    # Retain owl:Ontology headers from schema for provenance.
    for s, p, o in schema.triples(
        (None, RDF.type, URIRef("http://www.w3.org/2002/07/owl#Ontology"))
    ):
        demo.add((s, p, o))
        for _, pp, oo in schema.triples((s, None, None)):
            demo.add((s, pp, oo))

    GRAPH_FILE.write_text(demo.serialize(format="turtle"), encoding="utf-8")
    print(f"Wrote {GRAPH_FILE.relative_to(PERSONNEL_ROOT)} ({len(demo)} triples)")


if __name__ == "__main__":
    main()
