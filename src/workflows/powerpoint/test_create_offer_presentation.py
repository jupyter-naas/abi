import unittest
from pathlib import Path
from src.workflows.powerpoint.CreateOfferPresentationWorkflow import (
    CreateOfferPresentationWorkflow,
    CreateOfferPresentationWorkflowConfiguration,
    CreateOfferPresentationParameters
)
from src.core.integrations.PowerPointIntegration import PowerPointIntegrationConfiguration

class TestCreateOfferPresentationWorkflow(unittest.TestCase):
    def setUp(self):
        """Set up test cases."""
        self.workflow = CreateOfferPresentationWorkflow(
            CreateOfferPresentationWorkflowConfiguration(
                powerpoint_integration_config=PowerPointIntegrationConfiguration()
            )
        )
        
        # Test parameters
        self.test_params = CreateOfferPresentationParameters(
            client_name="Nexem",
            project_name="IA Project",
            brief_path="/Users/jrvmac/abi-forvismazars.com/storage/onedrive/Forvis Mazars/FRA-DATA SERVICES - ABI/Opportunities/Nexem/note de cadrage et cdc IA-Nexem v 17 02 25.pdf",
            output_path="test_output.pptx"
        )

    def test_workflow_creation(self):
        """Test if workflow can be created successfully."""
        self.assertIsNotNone(self.workflow)
        
    def test_run_workflow(self):
        """Test running the workflow."""
        try:
            result = self.workflow.run(self.test_params)
            self.assertTrue(Path(self.test_params.output_path).exists())
            self.assertIsInstance(result, str)
            self.assertIn("Presentation saved at", result)
        finally:
            # Cleanup
            if Path(self.test_params.output_path).exists():
                Path(self.test_params.output_path).unlink()

    def test_tools_creation(self):
        """Test if tools are created correctly."""
        tools = self.workflow.as_tools()
        self.assertIsInstance(tools, list)
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "create_offer_presentation")

if __name__ == '__main__':
    unittest.main() 