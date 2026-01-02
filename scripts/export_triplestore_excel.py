import os

from dotenv import load_dotenv
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from naas_abi_marketplace.applications.naas.workflows.ExportGraphInstancesToExcelWorkflow import (
    ExportGraphInstancesToExcelWorkflow,
    ExportGraphInstancesToExcelWorkflowConfiguration,
    ExportGraphInstancesToExcelWorkflowParameters,
)

load_dotenv()

if __name__ == "__main__":
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_core.utils.StorageUtils import StorageUtils

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.naas"])
    triple_store_service = engine.services.triple_store
    naas_integration_config = NaasIntegrationConfiguration(
        api_key=os.getenv("NAAS_API_KEY", ""),
    )
    storage_utils = StorageUtils(storage_service=engine.services.object_storage)

    data_store_path: str = "triplestore/export/excel"
    configuration = ExportGraphInstancesToExcelWorkflowConfiguration(
        triple_store=triple_store_service,
        naas_integration_config=naas_integration_config,
        data_store_path=data_store_path,
    )
    workflow = ExportGraphInstancesToExcelWorkflow(configuration)
    workflow.export_to_excel(ExportGraphInstancesToExcelWorkflowParameters())
