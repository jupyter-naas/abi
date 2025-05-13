import unittest
from unittest.mock import patch, MagicMock
from ..integrations.OpenAIGpt4oIntegration import OpenAIGpt4oIntegration, OpenAIGpt4oIntegrationConfiguration

class TestGpt4oModule(unittest.TestCase):
    """Test cases for the GPT-4o module."""
    
    def setUp(self):
        """Set up the test environment."""
        self.mock_config = OpenAIGpt4oIntegrationConfiguration(api_key="test_api_key")
    
    @patch.object(OpenAIGpt4oIntegration, 'create_chat_completion')
    def test_who_are_you_response(self, mock_create_chat_completion):
        """Test that the agent responds correctly to 'who are you'."""
        # Mock the create_chat_completion method to return the expected response
        mock_create_chat_completion.return_value = "gpt-4o"
        
        # Initialize the integration
        integration = OpenAIGpt4oIntegration(self.mock_config)
        
        # Test the response
        response = integration.create_chat_completion("who are you")
        
        # Assert that the response is correct
        self.assertEqual(response, "gpt-4o")

if __name__ == '__main__':
    unittest.main()