import pytest
from naas_abi_core.engine.Engine import Engine
from naas_abi_marketplace.domains.ontology_engineer.pipelines.MergeIndividualsPipeline import (
    MergeIndividualsPipelineConfiguration,
)
from naas_abi_marketplace.domains.ontology_engineer.workflows.EntityResolutionWorkflow import (
    EntityResolutionWorkflow,
    EntityResolutionWorkflowConfiguration,
    EntityResolutionWorkflowParameters,
)
from rdflib import Graph

# Load TBox graph from files
tbox_paths = [
    "libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/ontologies/BFO7BucketsProcessOntology.ttl",
    "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/ontologies/modules/ActOfConnectionsOnLinkedIn.ttl",
]
graph_tbox = Graph()
for tbox_path in tbox_paths:
    graph_tbox.parse(tbox_path, format="turtle")


@pytest.fixture
def workflow():
    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.domains.ontology_engineer"])
    triple_store_service = engine.services.triple_store
    object_storage_service = engine.services.object_storage
    merge_duplicates_pipeline_configuration = MergeIndividualsPipelineConfiguration(
        triple_store=triple_store_service,
        object_storage=object_storage_service,
    )
    return EntityResolutionWorkflow(
        EntityResolutionWorkflowConfiguration(
            triple_store=triple_store_service,
            merge_pipeline_configuration=merge_duplicates_pipeline_configuration,
        )
    )


def test_similar_persons(workflow: EntityResolutionWorkflow):
    # Create ABox graph from Person entity
    from naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn import (
        Person,
        ProfilePage,
    )

    person_1 = Person(
        label="Florent Ravenel",
        first_name="Florent",
        last_name="Ravenel",
        given_name="Florent Ravenel",
    )
    person_2 = Person(
        label="Florent Ravenel",
        first_name="Florent",
        last_name="Ravenel",
        given_name="Florent Ravenel",
    )
    linkedin_profile_page = ProfilePage(
        label="https://www.linkedin.com/in/florent-ravenel/",
    )
    person_1.is_owner_of = [linkedin_profile_page]
    person_2.is_owner_of = [linkedin_profile_page]

    graph_abox = Graph()
    graph_abox += person_1.rdf()
    graph_abox += person_2.rdf()
    graph_abox += linkedin_profile_page.rdf()
    print(graph_abox.serialize(format="turtle"))

    result = workflow.run(
        EntityResolutionWorkflowParameters(
            tbox_graph=graph_tbox,
            abox_graph=graph_abox,
            similarity_threshold=100,
            uri_prefix_filter="http://ontology.naas.ai/abi/",
        )
    )
    print(result)
    assert len(result["duplicates"]) == 1, result["duplicates"]


def test_similar_persons_without_linkedin_profile_page(
    workflow: EntityResolutionWorkflow,
):
    # Create ABox graph from Person entity
    from naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn import (
        Person,
    )

    person_1 = Person(
        label="Florent Ravenel",
        first_name="Florent",
        last_name="Ravenel",
        given_name="Florent Ravenel",
    )
    person_2 = Person(
        label="Florent Ravenel",
        first_name="Florent",
        last_name="Ravenel",
        given_name="Florent Ravenel",
    )

    graph_abox = Graph()
    graph_abox += person_1.rdf()
    graph_abox += person_2.rdf()
    print(graph_abox.serialize(format="turtle"))

    result = workflow.run(
        EntityResolutionWorkflowParameters(
            tbox_graph=graph_tbox,
            abox_graph=graph_abox,
            similarity_threshold=100,
            uri_prefix_filter="http://ontology.naas.ai/abi/",
        )
    )
    print(result)
    assert len(result["duplicates"]) == 0, result["duplicates"]


def test_similar_qualities(workflow: EntityResolutionWorkflow):
    # Create ABox graph from Person entity
    from naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn import (
        CurrentJobPosition,
    )

    job_position_1 = CurrentJobPosition(
        label="CEO",
    )
    job_position_2 = CurrentJobPosition(
        label="CEO",
    )

    graph_abox = Graph()
    graph_abox += job_position_1.rdf()
    graph_abox += job_position_2.rdf()
    print(graph_abox.serialize(format="turtle"))

    result = workflow.run(
        EntityResolutionWorkflowParameters(
            tbox_graph=graph_tbox,
            abox_graph=graph_abox,
            similarity_threshold=100,
            uri_prefix_filter="http://ontology.naas.ai/abi/",
        )
    )
    print(result)
    assert len(result["duplicates"]) == 1, result["duplicates"]


def test_different_qualities(workflow: EntityResolutionWorkflow):
    # Create ABox graph from Person entity
    from naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn import (
        CurrentJobPosition,
    )

    job_position_1 = CurrentJobPosition(
        label="CEO",
    )
    job_position_2 = CurrentJobPosition(
        label="CEO & Founder",
    )
    job_position_3 = CurrentJobPosition(
        label="COO",
    )

    graph_abox = Graph()
    graph_abox += job_position_1.rdf()
    graph_abox += job_position_2.rdf()
    graph_abox += job_position_3.rdf()
    print(graph_abox.serialize(format="turtle"))

    result = workflow.run(
        EntityResolutionWorkflowParameters(
            tbox_graph=graph_tbox,
            abox_graph=graph_abox,
            similarity_threshold=100,
            uri_prefix_filter="http://ontology.naas.ai/abi/",
        )
    )
    print(result)
    assert len(result["duplicates"]) == 0, result["duplicates"]
