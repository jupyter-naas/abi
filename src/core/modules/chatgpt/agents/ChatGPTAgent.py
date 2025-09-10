from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    
)
from fastapi import APIRouter
from src.core.modules.chatgpt.models.gpt_4o import model
from src import secret
from typing import Optional
from enum import Enum

from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/chatgpt.jpg"
NAME = "ChatGPT"
TYPE = "core"
SLUG = "chatgpt"
DESCRIPTION = "ChatGPT Agent that provides real-time answers to any question on the web using OpenAI Web Search."
MODEL = "gpt-4o"
SYSTEM_PROMPT = """
Role: 
You are ChatGPT, a researcher agent with access to OpenAI Web Search.

Objective: 
Provide accurate and comprehensive information to user inquiries using your web search capabilities.

Context:
You will receive prompts from users but also from a supervisor agent named 'abi' that already handle the conversation with the user.
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
TEMPERATURE = 0
DATE = True
INSTRUCTIONS_TYPE = "system"
ONTOLOGY = True
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    # Define model
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr
    from src import secret

    model = ChatOpenAI(
        model="gpt-4.1-mini", 
        output_version="responses/v1",
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )
    
    # Define tools
    tools: list = [{"type": "web_search_preview"}, {"type": "image_generation"}]

    # Define intents
    intents: list = []

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return ChatGPTAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        # tools=tools, 
        agents=[],
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    ) 

class ChatGPTAgent(IntentAgent):
    pass