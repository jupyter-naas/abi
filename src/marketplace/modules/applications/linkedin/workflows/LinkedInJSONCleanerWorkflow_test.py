import pytest
import json

from src.marketplace.modules.applications.linkedin.workflows.LinkedInJSONCleanerWorkflow import (
    LinkedInJSONCleanerWorkflow, LinkedInJSONCleanerWorkflowConfiguration, LinkedInJSONCleanerWorkflowParameters
)

@pytest.fixture
def workflow() -> LinkedInJSONCleanerWorkflow:
    workflow_configuration = LinkedInJSONCleanerWorkflowConfiguration(
        flatten_result=True,
        include_images=True
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
    
    result = workflow.clean_json(LinkedInJSONCleanerWorkflowParameters(
        json_data=json_string,
    ))

    assert result is not None, result
    assert result["status"] == "success", result
    assert "cleaned_data" in result, result
    assert "com.linkedin.voyager.identity.profile.Profile" in result["cleaned_data"], result

def test_workflow_invalid_json(workflow: LinkedInJSONCleanerWorkflow):
    result = workflow.clean_json(LinkedInJSONCleanerWorkflowParameters(
        json_data="invalid json"
    ))

    assert result is not None, result
    assert result["status"] == "error", result
    assert "Invalid JSON data" in result["error"], result