import unittest
import os
from unittest.mock import patch, MagicMock
from ..integrations.OpenAIGpt4oIntegration import OpenAIGpt4oIntegration, OpenAIGpt4oIntegrationConfiguration
from ..pipelines.TextTransformationPipeline import TextTransformationPipeline

class TestGpt4oModule(unittest.TestCase):
    """Test cases for the GPT-4o module."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a mock OpenAI client configuration
        self.mock_config = OpenAIGpt4oIntegrationConfiguration(api_key="test_api_key")
    
    @patch('openai.OpenAI')
    def test_integration_initialization(self, mock_openai):
        """Test that the integration initializes correctly."""
        # Create a mock OpenAI client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Initialize the integration
        integration = OpenAIGpt4oIntegration(self.mock_config)
        
        # Assert that OpenAI client was initialized with the correct API key
        mock_openai.assert_called_once_with(api_key="test_api_key")
    
    @patch.object(OpenAIGpt4oIntegration, 'create_chat_completion')
    def test_text_transformation_pipeline(self, mock_create_chat_completion):
        """Test the text transformation pipeline."""
        # Mock the create_chat_completion method
        mock_create_chat_completion.return_value = "This is a summary of the text."
        
        # Create the pipeline
        pipeline = TextTransformationPipeline()
        
        # Replace the integration with our mocked version
        pipeline.integration = OpenAIGpt4oIntegration(self.mock_config)
        
        # Process some text
        result = pipeline.process(
            input_text="This is a long text that needs to be summarized.",
            transformation_type="summarize"
        )
        
        # Assert that the create_chat_completion method was called
        mock_create_chat_completion.assert_called_once()
        
        # Assert that the result contains the expected keys
        self.assertIn("original_text", result)
        self.assertIn("transformed_text", result)
        self.assertIn("transformation_type", result)
        self.assertIn("options", result)
        
        # Assert that the transformation_type is correct
        self.assertEqual(result["transformation_type"], "summarize")
        
        # Assert that the transformed_text is what we expected
        self.assertEqual(result["transformed_text"], "This is a summary of the text.")

if __name__ == '__main__':
    unittest.main() 