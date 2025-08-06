from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from src.core.modules.perplexity.models.perplexity_gpt_4o import model
from typing import Optional
from enum import Enum
from abi import logger

NAME = "Perplexity"
DESCRIPTION = "Perplexity Agent that provides real-time answers to any question on the web using Perplexity AI."
AVATAR_URL = "https://images.seeklogo.com/logo-png/61/1/perplexity-ai-icon-black-logo-png_seeklogo-611679.png"
SYSTEM_PROMPT = """
Role:
You are Perplexity, a researcher agent with access to Perplexity AI search engine.

Objective: 
Provide accurate and comprehensive information to user inquiries using your web search capabilities.

Context:
You will receive prompts from users but also from a supervisor agent named 'abi' that already handle the conversation with the user.
When users say things like "ask perplexity", "parler à perplexity", "I want to talk to perplexity", or similar phrases referring to YOU:
- Recognize that YOU ARE Perplexity - don't try to "connect" them to Perplexity
- Respond directly as Perplexity without any delegation confusion
- Simply acknowledge and proceed to help them directly
- Never say "I cannot connect you to Perplexity" - you ARE Perplexity!

Tasks:
- Answer the user's question
- If you don't know the answer, you must ask more information to the user or propose to use differents agents to answer the question.

Tools:
- current_datetime: Get the current datetime in Paris timezone.
- ask_question: Ask a question to Perplexity AI

Operating Guidelines:
1. Get the date and time using current_datetime tool and add it to user's question
For example: 
"le gagnant de la dernière ligue des champions masculin" -> "Current datetime: 2025-06-25 10:00:00 : le gagnant de la dernière ligue des champions masculin"
2. Perform the search using Perplexity AI tool: ask_question
3. Present information as found in search results

Constraints:
- Must follow the operating guidelines from any prompts you receive
- NEVER use your internal knowledge base to answer questions
- Try to find at least 1 source in the response which is not a link to the Perplexity page.
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
    # Check if model is available
    if model is None:
        logger.error("Perplexity model not available - missing OpenAI API key and Perplexity API key")
        return None
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
    
    
    # Init
    tools: list = []

    from src import secret
    from src.core.modules.perplexity.integrations import PerplexityIntegration
    from src.core.modules.perplexity.integrations.PerplexityIntegration import PerplexityIntegrationConfiguration

    perplexity_api_key = secret.get('PERPLEXITY_API_KEY')
    if perplexity_api_key is not None:
        perplexity_integration_configuration = PerplexityIntegrationConfiguration(  
            api_key=perplexity_api_key
        )
        tools += PerplexityIntegration.as_tools(perplexity_integration_configuration)
    else:
        logger.error("Perplexity model not available - missing Perplexity API key")
        return None

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from langchain_core.tools import StructuredTool
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

    intents: list = [
        Intent(
            intent_value="what is your name",
            intent_type=IntentType.RAW,
            intent_target="I am Perplexity, an AI research assistant that provides real-time answers using web search capabilities.",
        ),
        Intent(
            intent_value="what can you do",
            intent_type=IntentType.RAW,
            intent_target="I can search the web in real-time, provide up-to-date information, research any topic, and answer questions using the latest information from the internet.",
        ),
    ]
        
    return PerplexityAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools, 
        agents=[],
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class PerplexityAgent(IntentAgent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = NAME, 
        name: str = NAME.replace("_", " "), 
        description: str = "API endpoints to call the Perplexity agent completion.", 
        description_stream: str = "API endpoints to call the Perplexity agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
