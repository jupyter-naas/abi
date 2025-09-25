from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional


NAME = "ChatGPT_Research"
DESCRIPTION = "ChatGPT Research Agent provides real-time answers to any question on the web using responses v1 OpenAI api."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/chatgpt.jpg"
MODEL = "gpt-5-mini"
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> Agent:
    # Define model
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr
    from src import secret

    model = ChatOpenAI(
        model=MODEL, 
        output_version="responses/v1",
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )
    
    native_tools: list = [
        {"type": "web_search_preview"}
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration()
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return ChatGPTResponsesAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        native_tools=native_tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    ) 

class ChatGPTResponsesAgent(Agent):
    pass