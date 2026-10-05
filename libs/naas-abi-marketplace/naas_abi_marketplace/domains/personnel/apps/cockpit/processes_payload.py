"""Static BFO process documentation for the Processes cockpit page."""

from __future__ import annotations

from datetime import UTC, datetime

SCHEMA = "1.0"

_PROCESSES: list[dict] = [
    {
        "id": "working",
        "status": "implemented",
        "source": "ontologies/processes/ActOfWorkingProcess.ttl",
        "iri": "http://ontology.naas.ai/people/ActOfWorking",
        "label": "Act of Working",
        "kicker": "Working experience",
        "title": "Act of Working",
        "subtitle": (
            "A CCO Planned Act of performing work for an organization: person, "
            "organization, office building, temporal region, role, mission, skills and contract "
            "decomposed across the seven BFO buckets."
        ),
        "definition": (
            "A Planned Act, and an Act of Employment, in which a person performs work "
            "for an organization in an office building over a temporal region, realizing an employee "
            "role, developing skills, under an employment contract."
        ),
        "example": (
            "Alice Dupont working as COO for Demo, worldwide, since April 2023."
        ),
        "comment": (
            "Act of Working is the process counterpart to employment continuants "
            "(EmploymentRecord, EmployeeRole). The role is the WHY that inheres in the "
            "person; the Mission it concretizes is the stated remit and is a GDC, so it "
            "survives the person leaving the post."
        ),
        "buckets": {
            "what": {
                "bfo": "Process",
                "label": "Act of Working",
                "class": "people:ActOfWorking",
            },
            "when": {
                "bfo": "Temporal Region",
                "label": "Temporal region · first and last instant (last absent while ongoing)",
                "class": "abi:TemporalRegion · abi:hasFirstInstant · abi:hasLastInstant",
            },
            "who": {
                "bfo": "Material Entity",
                "label": "Person · Organization",
                "class": "abi:Person · abi:Organization",
            },
            "where": {
                "bfo": "Site",
                "label": "Office building of execution",
                "class": "cco:OfficeBuilding",
            },
            "how_to_know": {
                "bfo": "Generically dependent continuant",
                "label": "Mission · Employment contract · Profile document",
                "class": (
                    "people:Mission · personnel:EmploymentContract · "
                    "people:ProfileDocument"
                ),
            },
            "how_it_is": {
                "bfo": "Qualities",
                "label": "Skills · Remuneration",
                "class": "people:Skill · personnel:Remuneration",
            },
            "why": {
                "bfo": "Realizable Entities",
                "label": "Employee role",
                "class": "personnel:EmployeeRole",
            },
        },
        "restrictions": [
            {
                "on": "Act of Working",
                "property": "for organization",
                "property_iri": "people:forOrganization",
                "someValuesFrom": "abi:Organization",
                "definition": "Every act of working is performed for an organization.",
                "example": "Demo",
            },
            {
                "on": "Act of Working",
                "property": "occurs in",
                "property_iri": "abi:occursIn",
                "someValuesFrom": "cco:OfficeBuilding",
                "definition": "The act is executed in an office building.",
                "example": "World",
            },
            {
                "on": "Act of Working",
                "property": "occupies temporal region",
                "property_iri": "abi:occupiesTemporalRegion",
                "someValuesFrom": "abi:TemporalRegion",
                "definition": (
                    "The act spans a temporal region bounded by a first instant and, "
                    "unless ongoing, a last instant."
                ),
                "example": "Apr 2023 – Present",
            },
            {
                "on": "Act of Working",
                "property": "realizes",
                "property_iri": "abi:realizes",
                "someValuesFrom": "personnel:EmployeeRole",
                "definition": (
                    "The act realizes the employee role borne by the person. The role "
                    "concretizes a JobPosition and a Mission, both GDCs."
                ),
                "example": "COO",
            },
            {
                "on": "Act of Working",
                "property": "develops skill",
                "property_iri": "people:developsSkill",
                "someValuesFrom": "people:Skill",
                "definition": (
                    "Skills are qualities inhering in the person, exercised and developed "
                    "in the act. One skill node is shared by every act that develops it."
                ),
                "example": "Python",
            },
            {
                "on": "Employee Role",
                "property": "has mission",
                "property_iri": "people:hasMission",
                "someValuesFrom": "people:Mission",
                "definition": (
                    "The role concretizes the mission: rdfs:label carries the opening "
                    "sentence, people:mission_content the full stated text."
                ),
                "example": "Lead platform operations and agent orchestration…",
            },
            {
                "on": "Mission",
                "property": "is sourced from",
                "property_iri": "people:isSourcedFrom",
                "someValuesFrom": "people:ProfileDocument",
                "definition": (
                    "Provenance: every asserted mission points back at the profile page "
                    "it was read from."
                ),
                "example": "demo.example/profiles/alice-dupont",
            },
            {
                "on": "Person",
                "property": "has act of working",
                "property_iri": "people:hasActOfWorking",
                "someValuesFrom": "people:ActOfWorking",
                "definition": "Links a person to each act of working they perform.",
                "example": "Alice Dupont → COO @ Demo",
            },
        ],
    },
    {
        "id": "studying",
        "status": "implemented",
        "source": "ontologies/processes/ActOfStudyingProcess.ttl",
        "iri": "http://ontology.naas.ai/people/ActOfStudying",
        "label": "Act of Studying",
        "kicker": "Education history",
        "title": "Act of Studying",
        "subtitle": (
            "A CCO Planned Act of educational training acquisition: person, educational "
            "organization, educational facility, temporal region, student role, skills, enrollment record "
            "and academic degree."
        ),
        "definition": (
            "A Planned Act, and an Act of Educational Training Acquisition, in which a "
            "person acquires knowledge of a curriculum from an educational organization in "
            "an educational facility over a temporal region, realizing a student role, developing skills, "
            "under an enrollment record and academic degree."
        ),
        "example": (
            "Alice Dupont studying for a Master's Degree in Corporate Finance at Demo "
            "Business School in Bordeaux from 2012 to 2016."
        ),
        "comment": (
            "Act of Studying is the process counterpart to study continuants "
            "(EnrollmentRecord, StudentRole, AcademicDegree). Enrollment records and "
            "degrees point back to the education profile page through "
            "people:isSourcedFrom."
        ),
        "buckets": {
            "what": {
                "bfo": "Process",
                "label": "Act of Studying",
                "class": "people:ActOfStudying",
            },
            "when": {
                "bfo": "Temporal Region",
                "label": "Temporal region · first and last instant",
                "class": "abi:TemporalRegion · abi:hasFirstInstant · abi:hasLastInstant",
            },
            "who": {
                "bfo": "Material Entity",
                "label": "Person · Educational organization",
                "class": "abi:Person · abi:Organization",
            },
            "where": {
                "bfo": "Site",
                "label": "Educational facility",
                "class": "cco:EducationalFacility",
            },
            "how_to_know": {
                "bfo": "Generically dependent continuant",
                "label": "Enrollment record · Academic degree · Profile document",
                "class": (
                    "people:EnrollmentRecord · people:AcademicDegree · "
                    "people:ProfileDocument"
                ),
            },
            "how_it_is": {
                "bfo": "Qualities",
                "label": "Skills",
                "class": "people:Skill",
            },
            "why": {
                "bfo": "Realizable Entities",
                "label": "Student role",
                "class": "people:StudentRole",
            },
        },
        "restrictions": [
            {
                "on": "Act of Studying",
                "property": "for educational organization",
                "property_iri": "people:forEducationalOrganization",
                "someValuesFrom": "abi:Organization",
                "definition": (
                    "Every act of studying is performed with an educational organization."
                ),
                "example": "Demo Business School",
            },
            {
                "on": "Act of Studying",
                "property": "occurs in",
                "property_iri": "abi:occursIn",
                "someValuesFrom": "cco:EducationalFacility",
                "definition": "The act is executed in an educational facility.",
                "example": "Bordeaux",
            },
            {
                "on": "Act of Studying",
                "property": "occupies temporal region",
                "property_iri": "abi:occupiesTemporalRegion",
                "someValuesFrom": "abi:TemporalRegion",
                "definition": (
                    "The act spans a temporal region bounded by a first instant and a last "
                    "instant."
                ),
                "example": "2012 – 2016",
            },
            {
                "on": "Act of Studying",
                "property": "realizes",
                "property_iri": "abi:realizes",
                "someValuesFrom": "people:StudentRole",
                "definition": "The act realizes the student role borne by the person.",
            },
            {
                "on": "Act of Studying",
                "property": "has enrollment",
                "property_iri": "people:hasEnrollment",
                "someValuesFrom": "people:EnrollmentRecord",
                "definition": (
                    "Concretizes the enrollment record that documents the course of study."
                ),
            },
            {
                "on": "Act of Studying",
                "property": "has degree",
                "property_iri": "people:hasDegree",
                "someValuesFrom": "people:AcademicDegree",
                "definition": (
                    "Concretizes the academic degree awarded for the course of study."
                ),
            },
            {
                "on": "Act of Studying",
                "property": "develops skill",
                "property_iri": "people:developsSkill",
                "someValuesFrom": "people:Skill",
                "definition": (
                    "Skills are qualities inhering in the person, exercised and developed "
                    "in the act."
                ),
                "example": "Microsoft Excel",
            },
            {
                "on": "Enrollment Record",
                "property": "is sourced from",
                "property_iri": "people:isSourcedFrom",
                "someValuesFrom": "people:ProfileDocument",
                "definition": (
                    "Provenance: every enrollment record points back at the education "
                    "profile page it was read from."
                ),
                "example": "demo.example/profiles/alice-dupont/education",
            },
            {
                "on": "Person",
                "property": "has act of studying",
                "property_iri": "people:hasActOfStudying",
                "someValuesFrom": "people:ActOfStudying",
                "definition": "Links a person to an act of studying.",
                "example": (
                    "Alice Dupont → Master's Degree, Corporate Finance @ Demo Business School"
                ),
            },
        ],
    },
]


def build_processes_page_payload(
    *, entity_id: str, data_version: str | None = None
) -> dict:
    """Return the Processes page dataset (ontology docs, not instance data)."""
    version = data_version or datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    return {
        "schema_version": SCHEMA,
        "data_version": version,
        "entity_id": entity_id,
        "records": [],
        "processes": _PROCESSES,
    }
