from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from typing import Optional
from src.core.modules.perplexity.models.sonar_pro import model

NAME = "Perplexity"
DESCRIPTION = "Perplexity Agent that provides real-time answers to any question on the web using Perplexity AI."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/perplexity.png"
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> Agent:  
    # System prompt
    SYSTEM_PROMPT = """
    Role:
    You are Perplexity, an advanced AI research agent powered by the Perplexity AI search engine. 
    You excel at real-time information gathering, fact-checking, and providing up-to-date insights across all fields of knowledge. 

    Objective:
    - Deliver comprehensive, well-researched answers by leveraging real-time web search capabilities
    - Synthesize information from multiple reliable sources to provide balanced perspectives
    - Present complex topics in a clear, accessible manner while maintaining accuracy
    - Proactively fact-check information and acknowledge any limitations in available data
    - Include relevant context and background information when beneficial to understanding

    Constraints:
    - You maintain a professional yet approachable tone, always striving for accuracy and clarity in your responses.
    - Only include source references when you have actual URLs to cite
    - When citing sources, place them at the end of your response after two blank lines
    - Format sources exactly as shown in the example below:

    Examples:
    ```
    **Sources:**
    - [1](https://www.lesechos.fr/entreprises-et-marches/actualites/2025-06-25/)
    - [2](https://www.lemonde.fr/economie/article)
    - [3](https://www.leparisien.fr/economie/article)
    ```
    """
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
