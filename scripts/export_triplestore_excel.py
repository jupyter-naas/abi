from naas_abi import secret, services
from naas_abi.workflows.ExportGraphInstancesToExcelWorkflow import (
    ExportGraphInstancesToExcelWorkflow,
    ExportGraphInstancesToExcelWorkflowConfiguration,
    ExportGraphInstancesToExcelWorkflowParameters,
)
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)

if __name__ == "__main__":
    data_store_path: str = "datastore/triplestore/export/excel"
    configuration = ExportGraphInstancesToExcelWorkflowConfiguration(
        triple_store=services.triple_store_service,
        naas_integration_config=NaasIntegrationConfiguration(
            api_key=secret.get("NAAS_API_KEY")
        ),
        data_store_path=data_store_path,
    )
    workflow = ExportGraphInstancesToExcelWorkflow(configuration)
    workflow.export_to_excel(ExportGraphInstancesToExcelWorkflowParameters())
