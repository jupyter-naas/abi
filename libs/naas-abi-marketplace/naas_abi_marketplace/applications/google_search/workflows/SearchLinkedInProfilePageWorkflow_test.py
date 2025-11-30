import pytest
from naas_abi import secret
from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegrationConfiguration,
)
from naas_abi_marketplace.applications.google_search.workflows.SearchLinkedInProfilePageWorkflow import (
    SearchLinkedInProfilePageWorkflow,
    SearchLinkedInProfilePageWorkflowConfiguration,
    SearchLinkedInProfilePageWorkflowParameters,
)


@pytest.fixture
def workflow() -> SearchLinkedInProfilePageWorkflow:
    integration_configuration = GoogleProgrammableSearchEngineIntegrationConfiguration(
        api_key=secret.get("GOOGLE_CUSTOM_SEARCH_API_KEY"),
        search_engine_id=secret.get("GOOGLE_CUSTOM_SEARCH_ENGINE_ID"),
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
