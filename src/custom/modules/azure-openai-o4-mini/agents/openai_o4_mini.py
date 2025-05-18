from ..models.openai_o4_mini import model
from lib.abi.services.agent.Agent import Agent, AgentConfiguration

def create_agent():
    class AzureOpenAIO4MiniAgent(Agent): pass
    
    return AzureOpenAIO4MiniAgent(
        id=model.id,
        name=model.name,
        description=model.description,
        chat_model=model.model,
        configuration=AgentConfiguration(
            system_prompt="You are a helpful assistant that can answer questions and help with tasks."
        )
    )