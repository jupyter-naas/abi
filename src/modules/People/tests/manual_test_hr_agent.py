"""
Manual test script for HR Agent functionality.

This script can be run manually to test the HR agent when the environment is properly set up.
"""

from src.custom.People.agent.HRAssistant import create_hr_agent

def test_hr_agent():
    """Test that the HR agent can be created and used successfully."""
    try:
        print("Creating HR agent...")
        agent = create_hr_agent()
        print(f"HR agent created successfully with name: {agent.name}")
        
        # Test with a simple query
        print("\nTesting agent with a simple query...")
        response = agent.invoke({"message": "I need to find someone with Python skills"})
        print(f"Agent response: {response}")
        
        return True
    except Exception as e:
        print(f"Error testing HR agent: {str(e)}")
        return False

if __name__ == "__main__":
    print("Starting manual test of HR agent...")
    success = test_hr_agent()
    print(f"\nTest {'succeeded' if success else 'failed'}.") 