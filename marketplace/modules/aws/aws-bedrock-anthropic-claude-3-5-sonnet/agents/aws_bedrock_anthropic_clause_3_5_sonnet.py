from lib.abi.services.agent.Agent import Agent, AgentConfiguration
from ..models.aws_bedrock_anthropic_clause_3_5_sonnet import model

def create_agent():
    class AWSBedrockAnthropicClause35SonnetAgent(Agent):
        pass

    return AWSBedrockAnthropicClause35SonnetAgent(
        name=model.name,
        description=model.description,
        chat_model=model.model,
        configuration=AgentConfiguration(
            system_prompt="You are a helpful assistant that can answer questions and help with tasks."
        )
    )
