import pytest

from src.marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegrationConfiguration
)
from src.marketplace.applications.google_search.workflows.SearchLinkedInOrganizationPageWorkflow import (
    SearchLinkedInOrganizationPageWorkflow, 
    SearchLinkedInOrganizationPageWorkflowConfiguration, 
    SearchLinkedInOrganizationPageWorkflowParameters
)
from src import secret

@pytest.fixture
def workflow() -> SearchLinkedInOrganizationPageWorkflow:
    integration_configuration = GoogleProgrammableSearchEngineIntegrationConfiguration(
        api_key=secret.get("GOOGLE_CUSTOM_SEARCH_API_KEY"),
        search_engine_id=secret.get("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
    )
    workflow_configuration = SearchLinkedInOrganizationPageWorkflowConfiguration(
        integration_config=integration_configuration
    )
    return SearchLinkedInOrganizationPageWorkflow(workflow_configuration)

def test_workflow_search_linkedin_organization_page(workflow: SearchLinkedInOrganizationPageWorkflow):
    result = workflow.search_linkedin_organization_page(SearchLinkedInOrganizationPageWorkflowParameters(organization_name="Naas.ai"))
    assert result is not None, result
    assert len(result) > 0, result
    assert result[0]["title"] is not None, result[0]
    assert result[0]["link"] is not None, result[0]
    assert result[0]["description"] is not None, result[0]
    assert result[0]["cse_image"] is not None, result[0]