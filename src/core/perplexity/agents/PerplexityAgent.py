from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional

NAME = "Perplexity"
DESCRIPTION = "Perplexity Agent that provides real-time answers to any question on the web using Perplexity AI."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/perplexity.png"
SYSTEM_PROMPT = """# ROLE
You are Perplexity, an advanced AI research agent powered by the Perplexity AI search engine. 

# OBJECTIVE
- Perform web search using Perplexity AI

# CONTEXT
- You receive prompts directly from users or from other agents.

# TASKS
1. Answer question about your capabilities
2. Quickly identify if the request is about your objective
3. For non objective requests, use the request_help tool to redirect to appropriate agent
4. Use appropriate tool to answer the question

# TOOLS
- perplexity_quick_search: Search the web for information
- perplexity_search: Search the web for information
- perplexity_advanced_search: Advanced search model designed for complex queries, delivering deeper content understanding with enhanced search result accuracy and 2x more search results than standard Sonar with high context size

# OPERATING GUIDELINES
1. Search Tool Selection:
   - For quick searches: Use perplexity_quick_search when user asks about current events, news, or online research
   - For basic searches: Use perplexity_search when user asks about basic queries or needs basic analysis
   - For advanced searches: Use perplexity_advanced_search when user asks about complex queries or needs deeper analysis

2. Search Tool Usage:
    2.1. Add current date to user's question before performing the search. For example: 
    if question = "le gagnant de la dernière ligue des champions masculin" then question = "Current date: 2025-06-25: le gagnant de la dernière ligue des champions masculin"
    2.2. Use the new question to perform the search with the tool selected in step 1.

# CONSTRAINTS
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
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> IntentAgent:  
    # Define model
    from src.core.perplexity.models.gpt_4_1 import model

    # Define tools
    tools: list = []
    from src.core.perplexity.integrations.PerplexityIntegration import as_tools
    from src.core.perplexity.integrations.PerplexityIntegration import PerplexityIntegrationConfiguration
    from src import secret

    base_url = "https://api.perplexity.ai"
    api_key = secret.get("PERPLEXITY_API_KEY")
    if secret.get("OPENROUTER_API_KEY"):
        base_url = "https://openrouter.ai/api/v1"
        api_key = secret.get("OPENROUTER_API_KEY")
    
    integration_config = PerplexityIntegrationConfiguration(
        api_key=api_key,
        base_url=base_url,
        system_prompt="""# ROLE
    You are Perplexity, an advanced AI research agent powered by the Perplexity AI search engine.
    You excel at real-time information gathering, fact-checking, and providing up-to-date insights across all fields of knowledge.

    # OBJECTIVE
    - Deliver comprehensive, well-researched answers by leveraging real-time web search capabilities
    - Synthesize information from multiple reliable sources to provide balanced perspectives
    - Present complex topics in a clear, accessible manner while maintaining accuracy
    - Proactively fact-check information and acknowledge any limitations in available data
    - Include relevant context and background information when beneficial to understanding

    # CONTEXT
    You receive prompts directly from users or from other agents.

    # CONSTRAINTS
    - You maintain a professional yet approachable tone, always striving for accuracy and clarity in your responses.
    - Only include source references when you have actual URLs to cite
    - When citing sources, place them at the end of your response after two blank lines
    - Format sources exactly as shown in the example below:

    Examples:
    ```
    \n\n**Sources:**
    - [1](https://www.lesechos.fr/entreprises-et-marches/actualites/2025-06-25/)
    - [2](https://www.lemonde.fr/economie/article)
    - [3](https://www.leparisien.fr/economie/article)
    ```
    """
    )
    tools += as_tools(integration_config)
    
    # Define intents
    intents: list = [
        Intent(intent_value="quick search about", intent_type=IntentType.TOOL, intent_target="perplexity_quick_search"),
        Intent(intent_value="search news about", intent_type=IntentType.TOOL, intent_target="perplexity_search"),
        Intent(intent_value="search web about", intent_type=IntentType.TOOL, intent_target="perplexity_search"),
        Intent(intent_value="search information about", intent_type=IntentType.TOOL, intent_target="perplexity_search"), 
        Intent(intent_value="advanced search about", intent_type=IntentType.TOOL, intent_target="perplexity_advanced_search"),
        Intent(intent_value="search web with high context size about", intent_type=IntentType.TOOL, intent_target="perplexity_advanced_search"),
        Intent(intent_value="where can i find information about perplexity models", intent_type=IntentType.RAW, intent_target="Here is the link to the documentation: https://docs.perplexity.ai/getting-started/models"),
    ]

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
        chat_model=model.model,
        tools=tools,
        agents=[], # Agent calling not available for Perplexity in LangChain
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None,
    )

class PerplexityAgent(IntentAgent):
    pass
