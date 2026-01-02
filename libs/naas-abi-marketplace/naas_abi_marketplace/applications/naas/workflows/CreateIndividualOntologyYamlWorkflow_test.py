import pytest
from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_marketplace.applications.naas import ABIModule as NaasABIModule
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from naas_abi_marketplace.applications.naas.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflowConfiguration,
)
from naas_abi_marketplace.applications.naas.workflows.CreateIndividualOntologyYamlWorkflow import (
    CreateIndividualOntologyYamlWorkflow,
    CreateIndividualOntologyYamlWorkflowConfiguration,
    CreateIndividualOntologyYamlWorkflowParameters,
)

naas_module = NaasABIModule.get_instance()
naas_api_key = naas_module.configuration.naas_api_key

triple_store_service = NaasABIModule.get_instance().engine.services.triple_store
sparql_utils = SPARQLUtils(triple_store_service)


@pytest.fixture
def workflow() -> CreateIndividualOntologyYamlWorkflow:
    return CreateIndividualOntologyYamlWorkflow(
        CreateIndividualOntologyYamlWorkflowConfiguration(
            triple_store_service,
            ConvertOntologyGraphToYamlWorkflowConfiguration(
                NaasIntegrationConfiguration(api_key=naas_api_key)
            ),
        )
    )


def test_create_individual_ontology_yaml_workflow(
    workflow: CreateIndividualOntologyYamlWorkflow,
):
    import time
    from uuid import uuid4

    from naas_abi_core import logger
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

    # Run workflow
    ontology_id = workflow.graph_to_yaml(
        CreateIndividualOntologyYamlWorkflowParameters(individual_uri=str(uri), depth=1)
    )

    # Check if ontology id is set
    graph = sparql_utils.get_subject_graph(str(uri), 1)
    naas_ontology_id = list(
        graph.triples(
            (None, URIRef("http://ontology.naas.ai/abi/naas_ontology_id"), None)
        )
    )[0][2]
    assert str(ontology_id) == str(naas_ontology_id), ontology_id

    # Remove graph
    triple_store_service.remove(graph)

    # Remove ontology
    if ontology_id:
        naas_integration = NaasIntegration(
            NaasIntegrationConfiguration(api_key=naas_api_key)
        )
        result = naas_integration.delete_ontology(
            workspace_id=naas_module.configuration.workspace_id, ontology_id=ontology_id
        )
        logger.info(f"Removed ontology: {result}")
        assert result is not None, result
