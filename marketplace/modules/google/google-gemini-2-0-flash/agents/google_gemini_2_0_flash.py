from lib.abi.services.agent.Agent import Agent, AgentConfiguration
from ..models.google_gemini_2_0_flash import model

def create_agent():
    
    class GoogleGemini2FlashAgent(Agent):
        pass
    
    return GoogleGemini2FlashAgent(
        name=model.name,
        description="Google's most advanced, multimodal flagship model that's cheaper and faster than GPT-4 Turbo.",
        chat_model=model.model,
        configuration=AgentConfiguration(
            system_prompt="You are Gemini, a helpful assistant that can answer questions and help with tasks."
        )
    )
