import pytest

from src.core.modules.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
    NaasIntegration
)
from src.core.modules.abi.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflowConfiguration,
)
from src.core.modules.abi.workflows.CreateIndividualOntologyYamlWorkflow import (
    CreateIndividualOntologyYamlWorkflow,
    CreateIndividualOntologyYamlWorkflowConfiguration,
    CreateIndividualOntologyYamlWorkflowParameters,
)
from src import services, secret

@pytest.fixture
def workflow() -> CreateIndividualOntologyYamlWorkflow:
    return CreateIndividualOntologyYamlWorkflow(
        CreateIndividualOntologyYamlWorkflowConfiguration(
            services.triple_store_service, ConvertOntologyGraphToYamlWorkflowConfiguration(
                NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))
            )
        )
    )

def test_create_individual_ontology_yaml_workflow(workflow: CreateIndividualOntologyYamlWorkflow):
    from src import services
    from rdflib import Graph, URIRef, RDFS, Literal, OWL, Namespace, RDF
    from uuid import uuid4
    from src.utils.SPARQL import get_subject_graph
    from abi import logger
    import time
    from src import config

    ABI = Namespace("http://ontology.naas.ai/abi/")

    graph = Graph()
    uri = ABI[str(uuid4())]
    graph.add((uri, RDF.type, URIRef("https://www.commoncoreontologies.org/ont00000443")))
    graph.add((uri, RDF.type, OWL.NamedIndividual))
    graph.add((uri, RDFS.label, Literal("Naas.ai")))
    graph.add((uri, ABI.logo, Literal("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ9gXMaBLQZ39W6Pk53PRuzFjUvv_6lLRWPoQ&s")))
    services.triple_store_service.insert(graph)
    time.sleep(3)

    # Run workflow
    ontology_id = workflow.graph_to_yaml(
        CreateIndividualOntologyYamlWorkflowParameters(
            individual_uri=str(uri), 
            depth=1
        )
    )

    # Check if ontology id is set
    graph = get_subject_graph(str(uri), 1)
    naas_ontology_id = list(graph.triples((None, URIRef("http://ontology.naas.ai/abi/naas_ontology_id"), None)))[0][2]
    assert str(ontology_id) == str(naas_ontology_id), ontology_id

    # Remove graph
    services.triple_store_service.remove(graph)

    # Remove ontology
    if ontology_id:
        naas_integration = NaasIntegration(
            NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))
        )
        result = naas_integration.delete_ontology(workspace_id=config.workspace_id, ontology_id=ontology_id)
        logger.info(f"Removed ontology: {result}")
        assert result is not None, result
