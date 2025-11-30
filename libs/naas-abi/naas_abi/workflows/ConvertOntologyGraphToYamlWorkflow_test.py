import pytest
from naas_abi import secret
from naas_abi.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflow,
    ConvertOntologyGraphToYamlWorkflowConfiguration,
    ConvertOntologyGraphToYamlWorkflowParameters,
)
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)


@pytest.fixture
def workflow() -> ConvertOntologyGraphToYamlWorkflow:
    return ConvertOntologyGraphToYamlWorkflow(
        ConvertOntologyGraphToYamlWorkflowConfiguration(
            NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))
        )
    )


def test_convert_ontology_graph_to_yaml_workflow(
    workflow: ConvertOntologyGraphToYamlWorkflow,
):
    import time
    from uuid import uuid4

    from naas_abi import config, logger, services
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
            class_colors_mapping={},
        )
    )

    # Remove graph
    services.triple_store_service.remove(graph)

    # Remove ontology
    naas_integration = NaasIntegration(
        NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))
    )
    result = naas_integration.delete_ontology(
        workspace_id=config.workspace_id, ontology_id=ontology_id
    )
    logger.info(f"Removed ontology: {result}")
    assert result is not None, result
