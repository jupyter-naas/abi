import pytest

from src.marketplace.modules.applications.google_search.integrations.GoogleSearchIntegration import (
    GoogleSearchIntegrationConfiguration,
    GoogleSearchIntegration
)
import re

@pytest.fixture
def google_search_integration() -> GoogleSearchIntegration:
    config = GoogleSearchIntegrationConfiguration()
    return GoogleSearchIntegration(config)

def test_search_linkedin_organization_url(google_search_integration: GoogleSearchIntegration):
    organization = "Marriott"
    urls = google_search_integration.search_linkedin_organization_url(organization)
    pattern = r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+"

    assert urls is not None
    assert len(urls) > 0, urls
    assert all(re.match(pattern, url) for url in urls), urls

def test_search_linkedin_profile_url(google_search_integration: GoogleSearchIntegration):
    profile = "Florent Ravenel"
    urls = google_search_integration.search_linkedin_profile_url(profile)
    pattern = r"https://.+\.linkedin\.com/in/[^?]+"

    assert urls is not None
    assert len(urls) > 0, urls
    assert all(re.match(pattern, url) for url in urls), urls