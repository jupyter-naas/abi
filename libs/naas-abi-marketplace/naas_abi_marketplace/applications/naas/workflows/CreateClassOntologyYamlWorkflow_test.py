import pytest
from naas_abi_marketplace.applications.naas import ABIModule as NaasABIModule
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from naas_abi_marketplace.applications.naas.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflowConfiguration,
)
from naas_abi_marketplace.applications.naas.workflows.CreateClassOntologyYamlWorkflow import (
    CreateClassOntologyYamlWorkflow,
    CreateClassOntologyYamlWorkflowConfiguration,
    CreateClassOntologyYamlWorkflowParameters,
)

naas_module = NaasABIModule.get_instance()
naas_api_key = naas_module.configuration.naas_api_key

triple_store_service = NaasABIModule.get_instance().engine.services.triple_store


@pytest.fixture
def workflow() -> CreateClassOntologyYamlWorkflow:
    return CreateClassOntologyYamlWorkflow(
        CreateClassOntologyYamlWorkflowConfiguration(
            triple_store_service,
            ConvertOntologyGraphToYamlWorkflowConfiguration(
                NaasIntegrationConfiguration(api_key=naas_api_key)
            ),
        )
    )


def test_create_class_ontology_yaml_workflow(workflow: CreateClassOntologyYamlWorkflow):
    import time
    from uuid import uuid4

    from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef

    ABI = Namespace("http://ontology.naas.ai/abi/")

    graph = Graph()
    uri = ABI[str(uuid4())]
    graph.add(
        (uri, RDF.type, URIRef("https://www.commoncoreontologies.org/ont00000443"))
    )
    graph.add((uri, RDF.type, OWL.NamedIndividual))
    graph.add((uri, RDFS.label, Literal("Naas.ai")))
    graph.add(
        (
            uri,
            ABI.logo,
            Literal(
                "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ9gXMaBLQZ39W6Pk53PRuzFjUvv_6lLRWPoQ&s"
            ),
        )
    )
    triple_store_service.insert(graph)
    time.sleep(3)

    # Parameters
    class_uri = "https://www.commoncoreontologies.org/ont00001262"

    # Run workflow
    ontology_id = workflow.graph_to_yaml(
        CreateClassOntologyYamlWorkflowParameters(class_uri=class_uri)
    )
    assert ontology_id is not None, ontology_id
    assert ontology_id != "", ontology_id
    assert isinstance(ontology_id, str), ontology_id
