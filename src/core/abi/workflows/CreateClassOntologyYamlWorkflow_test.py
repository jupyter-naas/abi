import pytest

from src.marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from src.core.abi.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflowConfiguration,
)
from src.core.abi.workflows.CreateClassOntologyYamlWorkflow import (
    CreateClassOntologyYamlWorkflow,
    CreateClassOntologyYamlWorkflowConfiguration,
    CreateClassOntologyYamlWorkflowParameters,
)
from src import services, secret

@pytest.fixture
def workflow() -> CreateClassOntologyYamlWorkflow:
    return CreateClassOntologyYamlWorkflow(
        CreateClassOntologyYamlWorkflowConfiguration(
            services.triple_store_service, ConvertOntologyGraphToYamlWorkflowConfiguration(
                NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))
            )
        )
    )

def test_create_class_ontology_yaml_workflow(workflow: CreateClassOntologyYamlWorkflow):
    from src import services
    from rdflib import Graph, Namespace, URIRef, RDF, OWL, RDFS, Literal
    from uuid import uuid4
    import time

    ABI = Namespace("http://ontology.naas.ai/abi/")

    graph = Graph()
    uri = ABI[str(uuid4())]
    graph.add((uri, RDF.type, URIRef("https://www.commoncoreontologies.org/ont00000443")))
    graph.add((uri, RDF.type, OWL.NamedIndividual))
    graph.add((uri, RDFS.label, Literal("Naas.ai")))
    graph.add((uri, ABI.logo, Literal("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ9gXMaBLQZ39W6Pk53PRuzFjUvv_6lLRWPoQ&s")))
    services.triple_store_service.insert(graph)
    time.sleep(3)

    # Parameters
    class_uri="https://www.commoncoreontologies.org/ont00001262"

    # Run workflow
    ontology_id = workflow.graph_to_yaml(
        CreateClassOntologyYamlWorkflowParameters(class_uri=class_uri)
    )
    assert ontology_id is not None, ontology_id
    assert ontology_id != "", ontology_id
    assert isinstance(ontology_id, str), ontology_id
