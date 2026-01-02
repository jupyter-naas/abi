import pytest
from naas_abi import ABIModule
from naas_abi.workflows.ExportGraphInstancesToExcelWorkflow import (
    ExportGraphInstancesToExcelWorkflow,
    ExportGraphInstancesToExcelWorkflowConfiguration,
    ExportGraphInstancesToExcelWorkflowParameters,
)
from naas_abi_marketplace.applications.naas import ABIModule as NaasABIModule
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)

naas_module = NaasABIModule.get_instance()
naas_api_key = naas_module.configuration.naas_api_key

triple_store_service = ABIModule.get_instance().engine.services.triple_store
naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)


@pytest.fixture
def export_graph_to_excel() -> ExportGraphInstancesToExcelWorkflow:
    configuration = ExportGraphInstancesToExcelWorkflowConfiguration(
        triple_store=triple_store_service,
        naas_integration_config=naas_integration_config,
    )
    return ExportGraphInstancesToExcelWorkflow(configuration)


def test_export_graph_instances_to_excel_workflow(
    export_graph_to_excel: ExportGraphInstancesToExcelWorkflow,
):
    result = export_graph_to_excel.export_to_excel(
        ExportGraphInstancesToExcelWorkflowParameters()
    )

    assert result is not None, result
    assert isinstance(result, str), result
    assert result.startswith("https://api.naas.ai/workspace/"), result
