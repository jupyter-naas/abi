from src.core.assistants.expert.integrations.PowerPointAssistant import create_powerpoint_agent
from src import secret, config

def test_powerpoint_assistant():
    """Test the PowerPoint Assistant with a sample request."""
    
    # Create the PowerPoint Assistant
    assistant = create_powerpoint_agent()
    
    # Test parameters
    test_input = {
        "client_name": "Nexem",
        "project_name": "IA Project",
        "brief_path": "/Users/jrvmac/abi-forvismazars.com/storage/onedrive/Forvis Mazars/FRA-DATA SERVICES - ABI/Opportunities/Nexem/note de cadrage et cdc IA-Nexem v 17 02 25.pdf",
        "output_path": "nexem_offer.pptx"
    }
    
    # Use the create_offer_presentation tool
    response = assistant.run(
        "Create a presentation for Nexem IA Project using the brief at "
        f"{test_input['brief_path']} and save it to {test_input['output_path']}"
    )
    
    print("Assistant Response:", response)

if __name__ == "__main__":
    test_powerpoint_assistant() 