from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from langchain_core.messages import ToolMessage, ChatMessage

NAME = "Perplexity_Research"
DESCRIPTION = "Perplexity Research Agent that provides real-time answers to any question on the web using Perplexity AI."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/perplexity.png"
SYSTEM_PROMPT = """# ROLE
You are Perplexity, an advanced AI research agent powered by the Perplexity AI search engine. 
You excel at real-time information gathering, fact-checking, and providing up-to-date insights across all fields of knowledge.

# OBJECTIVE
- Deliver comprehensive, well-researched answers by leveraging real-time web search capabilities
- Synthesize information from multiple reliable sources to provide balanced perspectives
- Present complex topics in a clear, accessible manner while maintaining accuracy
- Proactively fact-check information and acknowledge any limitations in available data
- Include relevant context and background information when beneficial to understanding

# CONTEXT
You receive prompts directly from users.

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
) -> Agent:  
    # Define model
    from src.core.perplexity.models.sonar_pro import model

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
        
    return PerplexityResearchAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=[], # Tool calling not available for Perplexity in LangChain
        agents=[], # Agent calling not available for Perplexity in LangChain
        state=agent_shared_state,
        configuration=agent_configuration, 
        memory=None,
    ) 

class PerplexityResearchAgent(Agent):
    
    # This is required because langchain_perplexity does not handle ToolMessage properly.
    # If we don't do this, the langchain_perplexity code will raise an error as it does not expect a ToolMessage.
    # But they do have a ChatMessage check, so instead we convert the ToolMessage to a ChatMessage.
    # And it seems to work fine :D 
    def call_model(self, state):
        _messages_without_tool_message: list = []
        
        for message in state["messages"]:
            message = message.copy()
            if isinstance(message, ToolMessage):
                message = ChatMessage(content=message.content, role="tool", id=message.tool_call_id[:40])
            
            _messages_without_tool_message.append(message)
                
        state["messages"] = _messages_without_tool_message
        
        return super().call_model(state)
