import pytest

import pydash as _
from src.marketplace.applications.linkedin.integrations.LinkedInIntegration import (
    LinkedInIntegration, 
    LinkedInIntegrationConfiguration
)

DEFAULT_COMPANY_URL = 'https://www.linkedin.com/company/naas-ai/'
DEFAULT_PROFILE_URL = 'https://www.linkedin.com/in/jeremyravenel/'
DEFAULT_POST_URL = 'https://www.linkedin.com/posts/jeremyravenel_do-you-know-that-one-of-the-most-impactful-activity-7244092056774610944-_5eh?utm_source=share&utm_medium=member_desktop&rcm=ACoAABCNSioBW3YZHc2lBHVG0E_TXYWitQkmwog'
DEFAULT_MUTUAL_CONNECTIONS_PROFILE_ID = "ACoAAAJHE7sB5OxuKHuzguZ9L6lfDHqw--cdnJg"

@pytest.fixture
def integration() -> LinkedInIntegration:
    from src import secret
    li_at: str = secret.get('li_at')
    JSESSIONID: str = secret.get('JSESSIONID')
    configuration = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
    return LinkedInIntegration(configuration)

# Tests ordered exactly as methods appear in LinkedInIntegration class

def test_init(integration: LinkedInIntegration):
    """Test LinkedInIntegration initialization."""
    assert integration.cookies["li_at"] is not None
    assert integration.cookies["JSESSIONID"] is not None
    assert "x-li-lan" in integration.headers
    assert "accept" in integration.headers
    assert "csrf-token" in integration.headers

def test_flatten_dict(integration: LinkedInIntegration):
    """Test the _flatten_dict helper method."""
    nested_dict = {
        "level1": {
            "level2": {
                "value": "test"
            }
        },
        "simple": "value"
    }
    result = integration._flatten_dict(nested_dict)
    assert result["level1_level2_value"] == "test", result
    assert result["simple"] == "value", result

def test_clean_dict(integration: LinkedInIntegration):
    """Test the _clean_dict helper method."""
    dirty_dict = {
        "valid_key": "value",
        "*invalid_key": "value",
        "urn_key": "value",
        "nested": {
            "*nested_invalid": "value",
            "valid_nested": "value"
        }
    }
    result = integration._clean_dict(dirty_dict)
    assert "valid_key" in result
    assert "*invalid_key" not in result
    assert "urn_key" not in result
    assert "valid_nested" in result["nested"]
    assert "*nested_invalid" not in result["nested"]

def test_parse_clean(integration: LinkedInIntegration):
    """Test the _parse_clean helper method."""
    mock_data = {
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.search.EntityResultViewModel",
                "title": {"text": "Test Title"},
                "trackingId": "should_be_removed"
            },
            {
                "$type": "com.linkedin.voyager.dash.search.EntityResultViewModel",
                "title": {"text": "Test Title 2"}
            }
        ]
    }
    result = integration._parse_clean(mock_data)
    assert "com.linkedin.voyager.dash.search.EntityResultViewModel" in result
    assert len(result["com.linkedin.voyager.dash.search.EntityResultViewModel"]) == 2
    assert "trackingId" not in result["com.linkedin.voyager.dash.search.EntityResultViewModel"][0]

def test_clean_json(integration: LinkedInIntegration):
    """Test the clean_json method."""
    mock_data = {
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.search.EntityResultViewModel",
                "title": {"text": "Test Title"},
                "*invalid": "should_be_removed"
            }
        ]
    }
    result = integration.clean_json("test_prefix", "test_file", mock_data)
    assert result is not None
    assert isinstance(result, dict)

def test_get_images(integration: LinkedInIntegration):
    """Test the __get_images helper method."""
    mock_data = {
        "entityUrn": "test_urn",
        "logo": {
            "rootUrl": "https://example.com/",
            "artifacts": [
                {"fileIdentifyingUrlPathSegment": "image1.png"},
                {"fileIdentifyingUrlPathSegment": "image2.png"}
            ]
        }
    }
    result = integration._LinkedInIntegration__get_images(mock_data, "logo")
    assert isinstance(result, list)
    assert len(result) == 2
    assert "https://example.com/image1.png" in result
    assert "https://example.com/image2.png" in result

def test_get_organization_public_id(integration: LinkedInIntegration):
    """Test extracting organization public ID from LinkedIn URL."""
    # Test company URL
    result = integration.get_organization_public_id(DEFAULT_COMPANY_URL)
    assert result == "naas-ai", result

def test_get_organization_id(integration: LinkedInIntegration):
    """Test getting organization ID from LinkedIn URL."""
    result = integration.get_organization_id(DEFAULT_COMPANY_URL)
    assert result is not None, result
    assert isinstance(result, str), result
    assert len(result) > 0, result

def test_get_organization_info(integration: LinkedInIntegration):
    """Test getting organization information."""
    result = integration.get_organization_info(DEFAULT_COMPANY_URL)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result
    assert result.get('data', {}).get('entityUrn') is not None, result

def test_get_profile_public_id(integration: LinkedInIntegration):
    """Test extracting profile public ID from LinkedIn URL."""
    result = integration.get_profile_public_id(DEFAULT_PROFILE_URL)
    assert result == "jeremyravenel", result
    
    # Test URL without /in/ prefix
    url = "https://www.linkedin.com/jeremyravenel/"
    result = integration.get_profile_public_id(url)
    assert result == "", result

def test_get_profile_id(integration: LinkedInIntegration):
    """Test getting profile ID from LinkedIn URL."""
    result = integration.get_profile_id(DEFAULT_PROFILE_URL)
    assert result is not None, result
    assert isinstance(result, str), result
    assert len(result) > 0, result

def test_get_profile_top_card(integration: LinkedInIntegration):
    """Test getting profile top card information."""
    result = integration.get_profile_top_card(DEFAULT_PROFILE_URL)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result

def test_get_profile_data(integration: LinkedInIntegration):
    """Test getting profile data for different types."""
    # Test skills
    result = integration.get_profile_data(DEFAULT_PROFILE_URL, profile_type="skills")
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result
    
    # Test experience
    result = integration.get_profile_data(DEFAULT_PROFILE_URL, profile_type="experience")
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result
    
    # Test education
    result = integration.get_profile_data(DEFAULT_PROFILE_URL, profile_type="education")
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result

def test_get_profile_skills(integration: LinkedInIntegration):
    """Test getting profile skills."""
    result = integration.get_profile_skills(DEFAULT_PROFILE_URL)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result

def test_get_profile_experience(integration: LinkedInIntegration):
    """Test getting profile experience."""
    result = integration.get_profile_experience(DEFAULT_PROFILE_URL)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result

def test_get_profile_education(integration: LinkedInIntegration):
    """Test getting profile education."""
    result = integration.get_profile_education(DEFAULT_PROFILE_URL)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result

# def test_get_date_from_token(integration: LinkedInIntegration):
#     """Test the get_date_from_token method."""
#     # This would need a valid token to test properly
#     # For now, we'll test that it doesn't crash
#     try:
#         result = integration.get_date_from_token("invalid_token")
#         # Should handle invalid tokens gracefully
#     except Exception:
#         # Expected for invalid tokens
#         pass

def test_get_profile_posts_feed(integration: LinkedInIntegration):
    """Test getting profile posts feed."""
    result = integration.get_profile_posts_feed(DEFAULT_PROFILE_URL)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result

def test_get_activity_id_from_url(integration: LinkedInIntegration):
    """Test extracting activity ID from LinkedIn URL."""
    result = integration.get_activity_id_from_url(DEFAULT_POST_URL)
    assert result == "7244092056774610944", result
    
    # Test URL with :activity:
    url = "https://www.linkedin.com/posts/jeremyravenel_test:activity:1234567890/"
    result = integration.get_activity_id_from_url(url)
    assert result == "1234567890", result
    
    # Test invalid URL
    result = integration.get_activity_id_from_url("https://invalid-url.com")
    assert result == "", result

def test_get_post_stats(integration: LinkedInIntegration):
    """Test getting post stats."""
    result = integration.get_post_stats(DEFAULT_POST_URL)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result

def test_get_post_reactions(integration: LinkedInIntegration):
    """Test getting post reactions."""
    result = integration.get_post_reactions(DEFAULT_POST_URL)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result

def test_get_post_comments(integration: LinkedInIntegration):
    """Test getting post comments."""
    result = integration.get_post_comments(DEFAULT_POST_URL)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result

def test_get_post_reposts(integration: LinkedInIntegration):
    """Test getting post reposts."""
    result = integration.get_post_reposts(DEFAULT_POST_URL)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result

def test_get_mutual_connexions(integration: LinkedInIntegration):
    """Test getting mutual connections."""
    result = integration.get_mutual_connexions(DEFAULT_MUTUAL_CONNECTIONS_PROFILE_ID)
    assert result is not None, result
    assert result.get('data') is not None, result
    assert result.get('included') is not None, result
    total_results = _.get(result, 'data.data.searchDashClustersByAll.metadata.totalResultCount', 0)
    assert total_results > 0, f"Expected total results to be greater than 0, got {total_results}"