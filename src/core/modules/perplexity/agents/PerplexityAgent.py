from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from typing import Optional

NAME = "Perplexity"
MODEL = "sonar-pro"
TEMPERATURE = 0
DESCRIPTION = "Perplexity Agent that provides real-time answers to any question on the web using Perplexity AI."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/perplexity.png"
SYSTEM_PROMPT = """
Role:
You are Perplexity, a researcher agent with access to Perplexity AI search engine.

Objective: 
Provide accurate and comprehensive information to user inquiries using your web search capabilities.

Constraints:
- Must format sources as at the end of the response after 2 blank lines using the same reference as it is in the content: 

Examples:
```
**Sources:**
- [1](https://www.lesechos.fr/entreprises-et-marches/actualites/2025-06-25/)
- [2](https://www.lemonde.fr/economie/article)
- [3](https://www.leparisien.fr/economie/article)
```
"""
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> Agent:
    from src import secret
    from pydantic import SecretStr
    from langchain_perplexity import ChatPerplexity

    model = ChatPerplexity(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get('PERPLEXITY_API_KEY'))
    )
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
        
    return PerplexityAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=[],
        agents=[],
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class PerplexityAgent(Agent):
    pass
