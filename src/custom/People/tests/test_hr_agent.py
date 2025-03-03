"""
Test file for HR Agent functionality.
"""

import unittest
from src.custom.People.agent.HRAssistant import create_hr_agent

class TestHRAgent(unittest.TestCase):
    def test_agent_creation(self):
        """Test that the HR agent can be created successfully."""
        try:
            agent = create_hr_agent()
            self.assertIsNotNone(agent)
            self.assertEqual(agent.name, "hr_assistant")
            print("HR Agent created successfully")
        except Exception as e:
            self.fail(f"Failed to create HR agent: {str(e)}")

if __name__ == "__main__":
    unittest.main() 