from lib.abi.services.agent.Agent import Agent, AgentConfiguration
from ..models.claude_3_5_sonnet import model


def create_agent():
    class Claude35SonnetAgent(Agent):
        pass

    return Claude35SonnetAgent(
        name=model.name,
        description="Anthropic's most intelligent model with best-in-class reasoning capabilities and analysis.",
        chat_model=model.model,
        configuration=AgentConfiguration(
            system_prompt="You are Claude, a helpful, harmless, and honest AI assistant created by Anthropic. You excel at complex reasoning, analysis, and creative tasks."
        ),
    ) 