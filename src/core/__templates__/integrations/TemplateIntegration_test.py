import pytest

from src.core.__templates__.integrations.TemplateIntegration import (
    YourIntegration, 
    YourIntegrationConfiguration,
)

@pytest.fixture
def integration() -> YourIntegration:
    return YourIntegration(YourIntegrationConfiguration())

def test_integration_name(integration):
    result = integration.example_method("value1")

    assert result is not None, result
    assert "value1" in result, result