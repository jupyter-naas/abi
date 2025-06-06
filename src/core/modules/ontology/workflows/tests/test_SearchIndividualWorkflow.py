from src.core.modules.ontology.workflows.SearchIndividualWorkflow import (
    SearchIndividualWorkflow,
    SearchIndividualWorkflowConfiguration,
    SearchIndividualWorkflowParameters,
)
from src import services

# Configurations
search_individual_workflow_configuration = SearchIndividualWorkflowConfiguration(
    triple_store=services.triple_store_service
)

# Workflow
search_individual_workflow = SearchIndividualWorkflow(
    configuration=search_individual_workflow_configuration
)

# Test
result = search_individual_workflow.search_individual(
    SearchIndividualWorkflowParameters(
        search_label="Naas.ai",
        class_uri="https://www.commoncoreontologies.org/ont00000443",
        limit=10,
        query=None
    )
)
print(result)