import pytest

from src.core.modules.abi.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflow,
    ConvertOntologyGraphToYamlWorkflowConfiguration,
    ConvertOntologyGraphToYamlWorkflowParameters,
)
from src.marketplace.modules.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
    NaasIntegration
)
from src import secret

@pytest.fixture
def workflow() -> ConvertOntologyGraphToYamlWorkflow:
    return ConvertOntologyGraphToYamlWorkflow(
        ConvertOntologyGraphToYamlWorkflowConfiguration(
            NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))
        )
    )

def test_convert_ontology_graph_to_yaml_workflow(workflow: ConvertOntologyGraphToYamlWorkflow):
    from src import services
    from rdflib import Graph, Namespace, URIRef, RDF, OWL, RDFS, Literal
    from uuid import uuid4
    import time
    from abi import logger
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
        ConvertOntologyGraphToYamlWorkflowParameters(
            graph=graph.serialize(format="turtle"),
            ontology_id=None,
            label="Naas.ai",
            description="Naas.ai Ontology",
            logo_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ9gXMaBLQZ39W6Pk53PRuzFjUvv_6lLRWPoQ&s",
            level="USE_CASE",
            display_relations_names=True,
            class_colors_mapping={}
        )
    )

    # Remove graph
    services.triple_store_service.remove(graph)

    # Remove ontology
    naas_integration = NaasIntegration(
        NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))
    )
    result = naas_integration.delete_ontology(workspace_id=config.workspace_id, ontology_id=ontology_id)
    logger.info(f"Removed ontology: {result}")
    assert result is not None, result