from src.core.modules.naas.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.core.modules.ontology.workflows.ExportGraphInstancesToExcelWorkflow import (
    ExportGraphInstancesToExcelWorkflow, 
    ExportGraphInstancesToExcelWorkflowConfiguration,
    ExportGraphInstancesToExcelWorkflowParameters
)
from src import services, secret
from abi import logger

if __name__ == "__main__":
    data_store_path: str = "storage/datastore/triplestore/export/excel"
    configuration = ExportGraphInstancesToExcelWorkflowConfiguration(
        triple_store=services.triple_store_service,
        naas_integration_config=NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY")),
        data_store_path=data_store_path
    )
    workflow = ExportGraphInstancesToExcelWorkflow(configuration)
    workflow.export_to_excel(ExportGraphInstancesToExcelWorkflowParameters())