import pytest
from src.core.modules.abi.workflows.ExportGraphInstancesToExcelWorkflow import (
    ExportGraphInstancesToExcelWorkflow,
    ExportGraphInstancesToExcelWorkflowConfiguration,
    ExportGraphInstancesToExcelWorkflowParameters,
)
from src.marketplace.modules.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from src import services, secret

@pytest.fixture
def export_graph_to_excel() -> ExportGraphInstancesToExcelWorkflow:
    configuration = ExportGraphInstancesToExcelWorkflowConfiguration(
        triple_store=services.triple_store_service,
        naas_integration_config=NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))
    )
    return ExportGraphInstancesToExcelWorkflow(configuration)

def test_export_graph_instances_to_excel_workflow(
        export_graph_to_excel: ExportGraphInstancesToExcelWorkflow
    ):
    result = export_graph_to_excel.export_to_excel(ExportGraphInstancesToExcelWorkflowParameters())

    assert result is not None, result
    assert isinstance(result, str), result
    assert result.startswith("https://api.naas.ai/workspace/"), result
