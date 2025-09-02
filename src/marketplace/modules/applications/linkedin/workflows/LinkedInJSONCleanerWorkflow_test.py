import pytest
import json

from src.marketplace.modules.applications.linkedin.workflows.LinkedInJSONCleanerWorkflow import (
    LinkedInJSONCleanerWorkflow, LinkedInJSONCleanerWorkflowConfiguration, LinkedInJSONCleanerWorkflowParameters
)

@pytest.fixture
def workflow() -> LinkedInJSONCleanerWorkflow:
    from src.marketplace.modules.applications.linkedin.integrations.LinkedInIntegration import (
        LinkedInIntegrationConfiguration
    )

    integration_configuration = LinkedInIntegrationConfiguration(
        li_at="test_li_at",
        JSESSIONID="test_jsessionid"
    )

    workflow_configuration = LinkedInJSONCleanerWorkflowConfiguration(
        integration_config=integration_configuration
    )

    return LinkedInJSONCleanerWorkflow(workflow_configuration)

def test_workflow_json_cleaning(workflow: LinkedInJSONCleanerWorkflow):
    # Sample LinkedIn-like JSON data
    test_data = {
        "data": {
            "profile": "test"
        },
        "included": [
            {
                "$type": "com.linkedin.voyager.identity.profile.Profile",
                "entityUrn": "urn:li:fsd_profile:test",
                "trackingId": "should_be_removed",
                "firstName": "John",
                "lastName": "Doe",
                "picture": {
                    "rootUrl": "https://media.licdn.com/",
                    "artifacts": [
                        {"fileIdentifyingUrlPathSegment": "test.jpg"}
                    ]
                }
            }
        ]
    }
    
    json_string = json.dumps(test_data)
    
    result = workflow.run_workflow(LinkedInJSONCleanerWorkflowParameters(
        json_data=json_string,
        flatten_result=True,
        include_images=True
    ))

    assert result is not None, result
    assert result["status"] == "success", result
    assert "cleaned_data" in result, result
    assert "com.linkedin.voyager.identity.profile.Profile" in result["cleaned_data"], result

def test_workflow_invalid_json(workflow: LinkedInJSONCleanerWorkflow):
    result = workflow.run_workflow(LinkedInJSONCleanerWorkflowParameters(
        json_data="invalid json",
        flatten_result=True,
        include_images=True
    ))

    assert result is not None, result
    assert result["status"] == "error", result
    assert "Invalid JSON data" in result["error"], result