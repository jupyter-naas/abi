import pytest
from naas_abi.workflows.GetObjectPropertiesFromClassWorkflow import (
    GetObjectPropertiesFromClassWorkflow,
    GetObjectPropertiesFromClassWorkflowConfiguration,
    GetObjectPropertiesFromClassWorkflowParameters,
)
from naas_abi_core import logger, services


@pytest.fixture
def workflow() -> GetObjectPropertiesFromClassWorkflow:
    return GetObjectPropertiesFromClassWorkflow(
        GetObjectPropertiesFromClassWorkflowConfiguration(
            triple_store=services.triple_store_service
        )
    )


def test_get_object_properties_from_bfo_core(
    workflow: GetObjectPropertiesFromClassWorkflow,
):
    class_uri = "http://purl.obolibrary.org/obo/BFO_0000015"

    result = workflow.get_object_properties_from_class(
        GetObjectPropertiesFromClassWorkflowParameters(class_uri=class_uri)
    )

    logger.info(result)
    assert result is not None, result
    assert len(result.get("object_properties", [])) > 0, result
    assert result.get("class_uri") == class_uri, result


def test_get_object_properties_from_cco(workflow: GetObjectPropertiesFromClassWorkflow):
    class_uri = "https://www.commoncoreontologies.org/ont00000443"

    result = workflow.get_object_properties_from_class(
        GetObjectPropertiesFromClassWorkflowParameters(class_uri=class_uri)
    )

    logger.info(result)
    assert result is not None, result
    assert len(result.get("object_properties", [])) == 0, result
    assert result.get("class_uri") == class_uri, result


def test_get_object_properties_from_abi(workflow: GetObjectPropertiesFromClassWorkflow):
    class_uri = "http://ontology.naas.ai/abi/Website"

    result = workflow.get_object_properties_from_class(
        GetObjectPropertiesFromClassWorkflowParameters(class_uri=class_uri)
    )

    logger.info(result)
    assert result is not None, result
    assert len(result.get("object_properties", [])) > 0, result
    assert result.get("class_uri") == class_uri, result
