from lib.abi.services.agent.Agent import Agent, AgentConfiguration
from ..models.llama_3_3_70b import model
from src import secret


def create_agent():
    # Check if OpenAI API key is available (used for Llama via OpenAI-compatible endpoint)
    if not secret.get("OPENAI_API_KEY"):
        return None
        
    class Llama33_70BAgent(Agent):
        pass

    return Llama33_70BAgent(
        name=model.name,
        description="Meta's latest Llama model with 70B parameters, optimized for instruction-following and conversational dialogue.",
        chat_model=model.model,
        configuration=AgentConfiguration(
            system_prompt="You are Llama, a helpful AI assistant created by Meta. You excel at following instructions, engaging in conversation, and assisting with a wide variety of tasks."
        ),
    ) 