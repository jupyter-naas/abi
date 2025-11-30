import pytest
from naas_abi import secret, services
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from naas_abi_marketplace.applications.naas.pipelines.ImageURLtoAssetPipeline import (
    ImageURLtoAssetPipeline,
    ImageURLtoAssetPipelineConfiguration,
    ImageURLtoAssetPipelineParameters,
)


@pytest.fixture
def image_url_to_asset_pipeline() -> ImageURLtoAssetPipeline:
    # Configuration
    api_key = secret.get("NAAS_API_KEY")
    naas_integration_config = NaasIntegrationConfiguration(api_key=api_key)
    pipeline_config = ImageURLtoAssetPipelineConfiguration(
        naas_integration_config=naas_integration_config,
        triple_store=services.triple_store_service,
    )
    pipeline = ImageURLtoAssetPipeline(pipeline_config)
    return pipeline


def test_image_url_to_asset_pipeline(
    image_url_to_asset_pipeline: ImageURLtoAssetPipeline,
):
    from uuid import uuid4

    from naas_abi_core.utils.Graph import ABI, TEST
    from rdflib import OWL, RDFS, Graph, Literal, URIRef

    # Parameters
    image_url = "https://media.licdn.com/dms/image/v2/C560BAQEOzG0TtTclXw/company-logo_200_200/company-logo_200_200/0/1630669062399?e=1755129600&v=beta&t=bgJLEuDIm89RlXA_QCd7tBVzZCQufZiDY5_SzZJABDw"

    node_id = str(uuid4())
    subject_uri = TEST[node_id]
    graph = Graph()
    graph.bind("test", TEST)
    graph.bind("owl", OWL)
    graph.bind("rdfs", RDFS)
    graph.bind("abi", ABI)
    graph.add(
        (
            subject_uri,
            URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
            URIRef("https://www.commoncoreontologies.org/ont00000443"),
        )
    )
    graph.add(
        (
            subject_uri,
            URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
            OWL.NamedIndividual,
        )
    )
    graph.add((subject_uri, RDFS.label, Literal(node_id)))
    services.triple_store_service.insert(graph)

    predicate_uri = "http://ontology.naas.ai/abi/logo"
    parameters = ImageURLtoAssetPipelineParameters(
        image_url=image_url, subject_uri=subject_uri, predicate_uri=predicate_uri
    )

    # Execute
    result = image_url_to_asset_pipeline.run(parameters)
    check_result = list(
        result.triples((URIRef(subject_uri), URIRef(predicate_uri), None))
    )

    assert isinstance(result, Graph), result.serialize(format="turtle")
    assert len(check_result) == 1, result.serialize(format="turtle")
    assert str(check_result[0][2]).startswith("https://api.naas.ai/workspace/"), (
        result.serialize(format="turtle")
    )

    # Remove graph
    services.triple_store_service.remove(result)
