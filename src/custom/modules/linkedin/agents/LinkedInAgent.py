from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from typing import Optional
from pydantic import SecretStr
from enum import Enum

NAME = "LinkedIn Agent"
DESCRIPTION = "Access LinkedIn through your account."
MODEL = "gpt-4o"
TEMPERATURE = 0
AVATAR_URL = "https://content.linkedin.com/content/dam/me/business/en-us/amp/brand-site/v2/bg/LI-Bug.svg.original.svg"
SYSTEM_PROMPT = """You are a LinkedIn Agent with access to LinkedIn.
If you don't have access to any tool, ask the user to set their access cookies li_at and JSESSIONID in .env file.
Always be clear and professional in your communication while helping users interact with LinkedIn services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.
"""
SUGGESTIONS: list[str] = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Init
    tools: list = []
    agents: list = []

    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get('OPENAI_API_KEY'))
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    # Set model
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
    
    return LinkedInAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class LinkedInAgent(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = NAME, 
        name: str = NAME.capitalize().replace("_", " "), 
        description: str = "API endpoints to call the LinkedIn agent completion.", 
        description_stream: str = "API endpoints to call the LinkedIn agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
