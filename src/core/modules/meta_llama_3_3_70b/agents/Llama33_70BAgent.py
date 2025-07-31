from lib.abi.services.agent.Agent import Agent, AgentConfiguration
from ..models.llama_3_3_70b import model


def create_agent():
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