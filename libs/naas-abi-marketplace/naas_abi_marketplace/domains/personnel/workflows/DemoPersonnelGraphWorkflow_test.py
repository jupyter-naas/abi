"""Tests for the demo personnel graph workflow."""

from __future__ import annotations

import json
from pathlib import Path

from naas_abi_marketplace.domains.personnel.scripts.demo_graph import (
    build_overlay_graph,
)
from naas_abi_marketplace.domains.personnel.utils.paths import (
    DEMO_SOURCE_DIR,
    PEOPLE_DEMO_SOURCE_DIR,
)
from naas_abi_marketplace.domains.personnel.workflows.DemoPersonnelGraphWorkflow import (
    DemoPersonnelGraphWorkflow,
    DemoPersonnelGraphWorkflowConfiguration,
    DemoPersonnelGraphWorkflowParameters,
)
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS

PEOPLE_ACT_OF_WORKING = URIRef("http://ontology.naas.ai/abi/ActOfWorking")
ACT_OF_EMPLOYMENT = URIRef("http://ontology.naas.ai/abi/ActOfEmployment")
EMPLOYEE_ROLE = URIRef("http://ontology.naas.ai/abi/EmployeeRole")
SERVICE_LINE = URIRef("http://ontology.naas.ai/abi/ServiceLine")
GRADE = URIRef("http://ontology.naas.ai/abi/Grade")


def test_demo_mode_writes_people_and_personnel_together(tmp_path: Path) -> None:
    output = tmp_path / "personnel.ttl"
    workflow = DemoPersonnelGraphWorkflow(DemoPersonnelGraphWorkflowConfiguration())
    result = workflow.run(
        DemoPersonnelGraphWorkflowParameters(
            mode="demo", source_dir=str(DEMO_SOURCE_DIR), output_path=str(output)
        )
    )
    assert result["mode"] == "demo"
    graph = Graph().parse(output)
    # The same act is an act of working (people) and an act of employment (personnel).
    employed = set(graph.subjects(RDF.type, ACT_OF_EMPLOYMENT))
    assert employed
    assert employed <= set(graph.subjects(RDF.type, PEOPLE_ACT_OF_WORKING))


def test_overlay_holds_only_the_employer_records() -> None:
    overlay = build_overlay_graph(DEMO_SOURCE_DIR)
    types = set(overlay.objects(None, RDF.type))
    assert {ACT_OF_EMPLOYMENT, EMPLOYEE_ROLE, SERVICE_LINE, GRADE} <= types
    # The act of working itself, its mission and skills stay in the people graph.
    assert PEOPLE_ACT_OF_WORKING not in types
    assert URIRef("http://ontology.naas.ai/abi/Mission") not in types


def test_every_employee_role_is_the_role_an_act_of_working_realizes(
    tmp_path: Path,
) -> None:
    output = tmp_path / "personnel.ttl"
    DemoPersonnelGraphWorkflow(DemoPersonnelGraphWorkflowConfiguration()).run(
        DemoPersonnelGraphWorkflowParameters(
            mode="demo", source_dir=str(DEMO_SOURCE_DIR), output_path=str(output)
        )
    )
    graph = Graph().parse(output)
    occupation = URIRef("http://ontology.naas.ai/abi/OccupationRole")
    for role in graph.subjects(RDF.type, EMPLOYEE_ROLE):
        assert (role, RDF.type, occupation) in graph


def test_personnel_demo_covers_the_people_demo() -> None:
    people = {p.parent.name for p in PEOPLE_DEMO_SOURCE_DIR.glob("*/index.json")}
    personnel = {p.parent.name for p in DEMO_SOURCE_DIR.glob("*/index.json")}
    assert personnel and personnel <= people


def test_employer_records_live_only_in_personnel_files() -> None:
    hr_keys = {"service_line", "grade", "roster", "employments"}
    for path in PEOPLE_DEMO_SOURCE_DIR.glob("*/index.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert not hr_keys & (set(payload) | set(payload.get("profile") or {})), path
    for path in DEMO_SOURCE_DIR.glob("*/index.json"):
        assert hr_keys <= set(json.loads(path.read_text(encoding="utf-8"))), path


def test_overlay_reads_the_grade_from_the_personnel_file() -> None:
    overlay = build_overlay_graph(DEMO_SOURCE_DIR)
    grades = {
        str(label)
        for g in overlay.subjects(RDF.type, GRADE)
        for label in overlay.objects(g, RDFS.label)
    }
    assert "Partner" in grades
