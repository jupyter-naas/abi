from lib.abi.services.agent.Agent import Agent, AgentConfiguration
from ..models.mistral_large_2 import model
from src import secret


def create_agent():
    # Check if Mistral API key is available
    if not secret.get("MISTRAL_API_KEY"):
        return None
        
    class MistralLarge2Agent(Agent):
        pass

    return MistralLarge2Agent(
        name=model.name,
        description="Mistral's flagship model with enhanced code generation, mathematics, and reasoning capabilities.",
        chat_model=model.model,
        configuration=AgentConfiguration(
            system_prompt="You are Mistral, a powerful AI assistant with exceptional capabilities in code generation, mathematics, and logical reasoning. You provide accurate and helpful responses."
        ),
    ) 