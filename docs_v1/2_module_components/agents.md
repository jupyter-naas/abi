# Agents Architecture

Agents in ABI are AI agents powered by Large Language Models (LLMs) that provide specific expertise and capabilities. They serve as the primary interface between users and the ABI system's capabilities.

## Design Philosophy

Agents are designed to be:
1. **Role-based**: Each agent has a specific role with defined responsibilities
2. **Tool-enhanced**: Agents use tools created from integrations, pipelines and workflows.
3. **Agent-enhanced**: Agents can use other agents to delegate tasks.
3. **Stateful**: Agents maintain conversation history and context 
4. **Configurable**: Customizable through system prompts and model parameters

## Agent Structure

1. **Agent Configuration**: Core settings that define the agent's behavior:
   - **Name**: A unique identifier for the agent (e.g., "Naas Agent")
   - **Description**: A brief explanation of the agent's purpose
   - **Model Configuration**: LLM settings including model name and temperature
   - **System Prompt**: Instructions that define the agent's role and behavior
   - **Avatar URL**: Optional visual representation of the agent
   - **Suggestions**: Predefined conversation starters or commands

2. **Agent Components**:
   - **Tools**: External capabilities the agent can access (e.g., NaasIntegration tools)
   - **Other Agents**: References to other agents that can be called for specific tasks
   - **Shared State**: Maintains conversation thread IDs and other shared information
   - **Memory**: Handles conversation history persistence (via MemorySaver)

3. **API Integration**:
   - **Router Configuration**: FastAPI endpoints for agent interaction
   - **Route Customization**: Configurable endpoints for both completion and streaming
   - **API Documentation**: Customizable descriptions and tags for API endpoints

The agent architecture follows a modular design where components can be configured at initialization time, with support for both synchronous and streaming interactions through API endpoints.

## Implementation Pattern

ABI agents follow a standardized implementation pattern:

```python
from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.core.modules.naas.integrations import NaasIntegration
from src.core.modules.naas.integrations.NaasIntegration import NaasIntegrationConfiguration

NAME = "Naas Agent"
MODEL = "o3-mini"
TEMPERATURE = 1
DESCRIPTION = "A Naas Agent with access to Naas Integration tools."
AVATAR_URL = "https://raw.githubusercontent.com/jupyter-naas/awesome-notebooks/refs/heads/master/.github/assets/logos/Naas.png"
SYSTEM_PROMPT = f"""
You are a Naas Agent with access to NaasIntegration tools to perform actions on Naas workspaces.
If you don't have access to any tool, ask the user to set their access token in .env file.
Always be clear and professional in your communication while helping users interact with Naas services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.
"""
SUGGESTIONS = []

def create_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
    
    # Add tools
    if secret.get('NAAS_API_KEY'):    
        naas_integration_config = NaasIntegrationConfiguration(api_key=secret.get('NAAS_API_KEY'))
        tools += NaasIntegration.as_tools(naas_integration_config)

    return NaasAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,  
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver()
    )

class NaasAgent(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "naas", 
        name: str = "Naas Agent", 
        description: str = "API endpoints to call the Naas agent completion.", 
        description_stream: str = "API endpoints to call the Naas agent stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)
```

## LLM Models

Agents can use various LLM models through LangChain:
- OpenAI models (GPT-4, GPT-3.5) via langchain_openai
- Anthropic models (Claude) via langchain_anthropic  
- Google models (PaLM) via langchain_google_genai
- Azure OpenAI models via langchain_openai
- Hugging Face models via langchain_community
- Local models via langchain_community (e.g. LlamaCpp)

The choice of model depends on the specific requirements of the assistant's role and the available API keys.