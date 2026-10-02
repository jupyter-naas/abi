"""Tests for the demo personnel graph workflow."""

from __future__ import annotations

from pathlib import Path

from naas_abi_marketplace.domains.personnel.graph.demo import build_overlay_graph
from naas_abi_marketplace.domains.personnel.paths import DEMO_SOURCE_DIR
from naas_abi_marketplace.domains.personnel.workflows.DemoPersonnelGraphWorkflow import (
    DemoPersonnelGraphWorkflow,
    DemoPersonnelGraphWorkflowConfiguration,
    DemoPersonnelGraphWorkflowParameters,
)
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

PEOPLE_ACT_OF_WORKING = URIRef("http://ontology.naas.ai/people/ActOfWorking")
ACT_OF_EMPLOYMENT = URIRef("http://ontology.naas.ai/personnel/ActOfEmployment")
EMPLOYEE_ROLE = URIRef("http://ontology.naas.ai/personnel/EmployeeRole")
SERVICE_LINE = URIRef("http://ontology.naas.ai/personnel/ServiceLine")
GRADE = URIRef("http://ontology.naas.ai/personnel/Grade")


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
    assert URIRef("http://ontology.naas.ai/people/Mission") not in types


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
    occupation = URIRef("http://ontology.naas.ai/people/OccupationRole")
    for role in graph.subjects(RDF.type, EMPLOYEE_ROLE):
        assert (role, RDF.type, occupation) in graph
