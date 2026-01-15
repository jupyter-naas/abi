import pytest
from naas_abi_marketplace.applications.google_search import ABIModule
from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegrationConfiguration,
)
from naas_abi_marketplace.applications.google_search.workflows.SearchLinkedInProfilePageWorkflow import (
    SearchLinkedInProfilePageWorkflow,
    SearchLinkedInProfilePageWorkflowConfiguration,
    SearchLinkedInProfilePageWorkflowParameters,
)

module = ABIModule.get_instance()
google_custom_search_api_key = module.configuration.google_custom_search_api_key
google_custom_search_engine_id = module.configuration.google_custom_search_engine_id


@pytest.fixture
def workflow() -> SearchLinkedInProfilePageWorkflow:
    integration_configuration = GoogleProgrammableSearchEngineIntegrationConfiguration(
        api_key=google_custom_search_api_key,
        search_engine_id=google_custom_search_engine_id,
    )
    workflow_configuration = SearchLinkedInProfilePageWorkflowConfiguration(
        integration_config=integration_configuration
    )
    return SearchLinkedInProfilePageWorkflow(workflow_configuration)


def test_workflow_search_linkedin_profile_page(
    workflow: SearchLinkedInProfilePageWorkflow,
):
    result = workflow.search_linkedin_profile_page(
        SearchLinkedInProfilePageWorkflowParameters(profile_name="Florent Ravenel")
    )
    assert result is not None, result
    assert len(result) > 0, result
    assert result[0]["title"] is not None, result[0]
    assert result[0]["link"] is not None, result[0]
    assert result[0]["description"] is not None, result[0]
    assert result[0]["cse_image"] is not None, result[0]


def test_workflow_search_linkedin_profile_page_with_organization(
    workflow: SearchLinkedInProfilePageWorkflow,
):
    result = workflow.search_linkedin_profile_page(
        SearchLinkedInProfilePageWorkflowParameters(
            profile_name="Florent Ravenel", organization_name="Naas.ai"
        )
    )
    assert result is not None, result
    assert len(result) > 0, result
    assert result[0]["title"] is not None, result[0]
    assert result[0]["link"] is not None, result[0]
    assert result[0]["description"] is not None, result[0]
    assert result[0]["cse_image"] is not None, result[0]
