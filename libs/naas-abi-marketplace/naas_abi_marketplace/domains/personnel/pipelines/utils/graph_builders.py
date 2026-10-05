"""RDF builders for what an organization records about its own staff.

:class:`PersonnelGraphContext` extends the people builder. Everything a
published source says about a person (their acts of working, roles, missions,
skills) is written by :class:`PeopleGraphContext` into the people graph; this
context adds the employer's records on top of the same individuals: the service
line and grade it assigns, and, for an act of working performed for it, the
employee role, job position, contract and remuneration that make it an act of
employment.

Same individual, two graphs: an act of employment is the act of working the
people graph already holds (``act_of_working_uri``), typed
``personnel:ActOfEmployment`` here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from naas_abi.ontologies.modules.OrganizationOntology import Organization
from naas_abi.ontologies.modules.PersonOntology import Person
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.utils.graph_builders import (
    ABI,
    CCO,
    PEOPLE,
    PeopleGraphContext,
    act_of_working_key,
    individual_uri,
    slug,
    utc_now,
)
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    EmploymentContract,
    Grade,
    JobPosition,
    Remuneration,
    ServiceLine,
)
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

PERSONNEL = Namespace("http://ontology.naas.ai/personnel/")


@dataclass
class PersonnelGraphContext(PeopleGraphContext):
    """Builder state for one batch of personnel records."""

    creator: str = "personnel_pipeline"
    service_lines: dict[str, ServiceLine] = field(default_factory=dict)
    grades: dict[str, Grade] = field(default_factory=dict)
    last_position_uri: str | None = None

    def set_employer(self, person: Person, org: Organization) -> None:
        """The organization's own record that it employs the person."""
        self.graph.add((URIRef(person._uri), PERSONNEL.isEmployedBy, URIRef(org._uri)))

    def ensure_service_line(self, label: str, org: Organization) -> ServiceLine:
        """A service line of one organization: itself an organization, not a label."""
        key = f"{org.label}|{label}"
        if key in self.service_lines:
            return self.service_lines[key]
        line = ServiceLine(
            _uri=individual_uri(
                str(PERSONNEL), "ServiceLine", slug(org.label or "", label)
            ),
            label=label,
            is_service_line_of=[org._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += line.rdf()
        self.graph.add((URIRef(org._uri), PERSONNEL.hasServiceLine, URIRef(line._uri)))
        self.service_lines[key] = line
        return line

    def ensure_grade(self, value: str, person: Person) -> Grade:
        key = f"{person.label}|{value}"
        if key in self.grades:
            return self.grades[key]
        grade = Grade(
            _uri=individual_uri(
                str(PERSONNEL), "Grade", slug(person.label or "", value)
            ),
            label=value,
            grade_value=value,
            inheres_in=[person._uri],
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += grade.rdf()
        self.graph.add((URIRef(person._uri), PERSONNEL.hasGrade, URIRef(grade._uri)))
        self.grades[key] = grade
        return grade

    def add_employment(
        self,
        *,
        person: Person,
        org: Organization,
        title: str,
        client: Organization | None = None,
        contract_type: str | None = None,
        job_family: str | None = None,
        remuneration_amount: float | None = None,
        remuneration_currency: str = "EUR",
    ) -> str:
        """Record an act of working as an act of employment by ``org``.

        The act and its occupation role keep the IRIs the people builder mints
        for them, so this adds to the act of working rather than restating it.
        Returns the act's IRI.
        """
        key = act_of_working_key(
            person.label or "", org.label or "", client.label if client else None, title
        )
        act = URIRef(individual_uri(str(PEOPLE), "ActOfWorking", key))
        role = URIRef(individual_uri(str(PEOPLE), "OccupationRole", key))
        person_uri = URIRef(person._uri)

        self.graph.add((act, RDF.type, PERSONNEL.ActOfEmployment))
        self.graph.add((act, ABI.realizes, role))
        self.graph.add((role, RDF.type, PERSONNEL.EmployeeRole))
        self.graph.add((person_uri, PERSONNEL.hasEmployeeRole, role))
        self.graph.add((role, PERSONNEL.isEmployeeRoleOf, person_uri))
        self.set_employer(person, org)

        position = JobPosition(
            _uri=individual_uri(str(PERSONNEL), "JobPosition", key),
            label=title,
            job_title=title,
            job_family=job_family,
            created=utc_now(),
            creator=self.creator,
        )
        self.graph += position.rdf()
        self.graph.add((role, PERSONNEL.hasJobPosition, URIRef(position._uri)))
        self.graph.add((URIRef(position._uri), PERSONNEL.isJobPositionOf, role))
        self.last_position_uri = position._uri

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
            self.graph.add((act, PERSONNEL.hasContract, URIRef(contract._uri)))

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
            self.graph.add((act, ABI.hasParticipant, URIRef(remuneration._uri)))

        return str(act)


def bind_graph_prefixes(graph: Graph) -> None:
    graph.bind("abi", ABI)
    graph.bind("people", PEOPLE)
    graph.bind("personnel", PERSONNEL)
    graph.bind("cco", CCO)
