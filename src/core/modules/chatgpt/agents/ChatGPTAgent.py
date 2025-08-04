from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from ..models.gpt_4o import model
from src import secret
from typing import Optional
from enum import Enum
from ..integrations import OpenAIWebSearchIntegration
from ..integrations.OpenAIWebSearchIntegration import OpenAIWebSearchIntegrationConfiguration
from datetime import datetime
from zoneinfo import ZoneInfo
from langchain_core.tools import StructuredTool

NAME = "ChatGPT"
DESCRIPTION = "ChatGPT Agent that provides real-time answers to any question on the web using OpenAI Web Search."
AVATAR_URL = "https://i.pinimg.com/736x/2a/62/c3/2a62c34e0d217a7aa14645ce114d84b3.jpg"
SYSTEM_PROMPT = """
Role: 
You are ChatGPT, a researcher agent with access to OpenAI Web Search.

Objective: 
Provide accurate and comprehensive information to user inquiries using your web search capabilities.

Context:
You will receive prompts from workers or leaders at Forvis Mazars but also from a supervisor agent that already handle the conversation with the user.

# SELF-RECOGNITION RULES
When users say things like "ask chatgpt", "parler à chatgpt", "I want to talk to chatgpt", or similar phrases referring to YOU:
- Recognize that YOU ARE ChatGPT - don't try to "connect" them to ChatGPT
- Respond directly as ChatGPT without any delegation confusion
- Simply acknowledge and proceed to help them directly
- Never say "I cannot connect you to ChatGPT" - you ARE ChatGPT!

Tasks:
- Answer the user's question
- If you don't know the answer, you must ask more information to the user or propose to use differents agents to answer the question.

Tools:
- current_datetime: Get the current datetime in Paris timezone.
- openai_web_search: Search the web using OpenAI.

Operating Guidelines:
1. Call current_datetime tool → Get current time
2. Format search query with datetime → "Current datetime: [datetime] : [user question]"
Examples:
- "le gagnant de la dernière ligue des champions masculin" → "Current datetime: 2025-01-27 15:30:00+01:00 : le gagnant de la dernière ligue des champions masculin"
- "actualités de la société Accor" → "Current datetime: 2025-01-27 15:30:00+01:00 : actualités de la société Accor"
- "latest news about AI" → "Current datetime: 2025-01-27 15:30:00+01:00 : latest news about AI"
3. Call openai_web_search tool → Search with formatted query
4. Present results with sources

Constraints:
- MUST follow the operating guidelines above
- NEVER skip the current_datetime tool call
- NEVER use your internal knowledge base to answer questions
- Try to find at least 1 source in the response which is not a link to the OpenAI Web Search page.
- Must display sources full URL
- Must format sources as at the end of the response after 2 blank lines: 
```
**Sources:**
- [Source Name](source_url)
```

Examples:
```
**Sources:**
- [Les echos](https://www.lesechos.fr/entreprises-et-marches/actualites/2025-06-25/)
- [Le Monde](https://www.lemonde.fr/economie/article
- [Le Parisien](https://www.leparisien.fr/economie/article
```
"""
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    # Check if OpenAI API key is available
    if not secret.get("OPENAI_API_KEY"):
        return None
    
    # Init
    tools: list = []
    agents: list = []

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Tools (we already verified API key exists)
    openai_web_search_integration_configuration = OpenAIWebSearchIntegrationConfiguration(  
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools += OpenAIWebSearchIntegration.as_tools(openai_web_search_integration_configuration)

    from pydantic import BaseModel
    
    class EmptySchema(BaseModel):
        pass
        
    current_datetime_tool = StructuredTool(
        name="current_datetime", 
        description="Get the current datetime in Paris timezone.",
        func=lambda : datetime.now(tz=ZoneInfo('Europe/Paris')),
        args_schema=EmptySchema
    )
    tools += [current_datetime_tool]

    if not model:
        raise ValueError("ChatGPT model not available - missing OpenAI API key")
        
    return ChatGPTAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools, 
        agents=agents,
        intents=[
            Intent(
                intent_value="what is your name",
                intent_type=IntentType.RAW,
                intent_target="I am ChatGPT, an AI assistant developed by OpenAI. I can help with real-time web search and provide comprehensive answers to your questions.",
            ),
            Intent(
                intent_value="what can you do",
                intent_type=IntentType.RAW,
                intent_target="I can help with real-time web search, answer questions using the latest information from the internet, provide research assistance, and help with various tasks using OpenAI's capabilities.",
            ),
        ],
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class ChatGPTAgent(IntentAgent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = NAME, 
        name: str = NAME.replace("_", " "), 
        description: str = "API endpoints to call the ChatGPT agent completion.", 
        description_stream: str = "API endpoints to call the ChatGPT agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
