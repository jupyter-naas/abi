"""Tests for PersonnelProfilePipeline and ActOfEmploymentPipeline."""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    Grade,
    ServiceLine,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfEmploymentPipeline import (
    ActOfEmploymentPipeline,
    ActOfEmploymentPipelineConfiguration,
    ActOfEmploymentPipelineParameters,
)
from naas_abi_marketplace.domains.personnel.pipelines.PersonnelProfilePipeline import (
    PersonnelProfilePipeline,
    PersonnelProfilePipelineConfiguration,
    PersonnelProfilePipelineParameters,
)
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PersonnelGraphContext,
)
from rdflib import URIRef
from rdflib.namespace import RDF

ABI_HAS_MEMBER_PART = URIRef("http://ontology.naas.ai/abi/hasMemberPart")
IS_EMPLOYED_BY = URIRef("http://ontology.naas.ai/abi/isEmployedBy")
IN_SERVICE_LINE = URIRef("http://ontology.naas.ai/abi/inServiceLine")
ACT_OF_EMPLOYMENT = URIRef("http://ontology.naas.ai/abi/ActOfEmployment")
HAS_CONTRACT = URIRef("http://ontology.naas.ai/abi/hasContract")


def _profile(**overrides: object) -> PersonnelProfilePipelineParameters:
    base: dict[str, object] = {
        "first_name": "Alice",
        "last_name": "Dupont",
        "organization": "Demo",
        "service_line": "Operations",
        "grade": "Partner",
    }
    base.update(overrides)
    return PersonnelProfilePipelineParameters(**base)


def _profile_pipeline(
    context: PersonnelGraphContext | None = None,
) -> PersonnelProfilePipeline:
    return PersonnelProfilePipeline(
        PersonnelProfilePipelineConfiguration(persist=False, context=context)
    )


def test_profile_records_employer_service_line_and_grade() -> None:
    graph = _profile_pipeline().run(_profile())

    types = set(graph.objects(None, RDF.type))
    assert URIRef(ServiceLine._class_uri) in types
    assert URIRef(Grade._class_uri) in types
    assert len(list(graph.triples((None, IS_EMPLOYED_BY, None)))) == 1


def test_person_is_a_member_part_of_the_service_line() -> None:
    """The membership must survive a person whose employment is not recorded."""
    graph = _profile_pipeline().run(_profile())

    lines = list(graph.subjects(RDF.type, URIRef(ServiceLine._class_uri)))
    assert len(lines) == 1
    assert len(list(graph.objects(lines[0], ABI_HAS_MEMBER_PART))) == 1


def test_service_line_attaches_to_recorded_employee_roles() -> None:
    context = PersonnelGraphContext()
    ActOfEmploymentPipeline(
        ActOfEmploymentPipelineConfiguration(persist=False, context=context)
    ).run(
        ActOfEmploymentPipelineParameters(
            first_name="Alice", last_name="Dupont", organization="Demo", title="COO"
        )
    )
    _profile_pipeline(context).run(_profile())

    assert len(list(context.graph.triples((None, IN_SERVICE_LINE, None)))) == 1


def test_employment_types_the_act_of_working_and_records_the_contract() -> None:
    graph = ActOfEmploymentPipeline(
        ActOfEmploymentPipelineConfiguration(persist=False)
    ).run(
        ActOfEmploymentPipelineParameters(
            first_name="Alice",
            last_name="Dupont",
            organization="Demo",
            title="COO",
            contract_type="Permanent",
        )
    )
    acts = list(graph.subjects(RDF.type, ACT_OF_EMPLOYMENT))
    assert len(acts) == 1
    # The act keeps the IRI the people builder mints for the act of working.
    assert str(acts[0]).startswith("http://ontology.naas.ai/people/ActOfWorking/")
    assert len(list(graph.objects(acts[0], HAS_CONTRACT))) == 1
