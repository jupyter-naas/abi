# Agents Architecture

Agents in ABI are AI agents powered by Large Language Models (LLMs) that provide specific expertise and capabilities. They serve as the primary interface between users and the ABI system's capabilities.

## Design Philosophy

Agents are designed to be:
1. **Role-based**: Each agent has a specific role with defined responsibilities
2. **Tool-enhanced**: Agents use tools created from integrations, pipelines and workflows
3. **Agent-enhanced**: Agents can use other agents to delegate tasks
4. **Stateful**: Agents maintain conversation history and context 
5. **Configurable**: Customizable through system prompts and model parameters

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
   - **Memory**: Handles conversation history persistence with automatic PostgreSQL detection

3. **API Integration**:
   - **Router Configuration**: FastAPI endpoints for agent interaction
   - **Route Customization**: Configurable endpoints for both completion and streaming
   - **API Documentation**: Customizable descriptions and tags for API endpoints

The agent architecture follows a modular design where components can be configured at initialization time, with support for both synchronous and streaming interactions through API endpoints.

## Technical Foundation: LangGraph

ABI agents are built on LangGraph, a framework for building stateful, multi-step applications with LLMs. Each agent uses a state machine with a directed graph that manages the flow of execution:

1. **StateGraph**: Defines the workflow between the model and tools
2. **Nodes**: 
   - **Agent Node**: Processes messages using the language model
   - **Tool Node**: Executes tool actions when requested
3. **Edges**: Define the transitions between nodes
4. **Checkpointing**: Enables persistent conversation memory across sessions using PostgreSQL or in-memory storage

The workflow typically follows this pattern:
- Start with the agent node
- Conditionally route to tools or end based on agent output
- Route back to the agent after tool usage

## Persistent Memory

ABI agents feature automatic persistent memory that remembers conversations across sessions. This enables truly continuous interactions where agents maintain context, preferences, and ongoing tasks even after restarts.

### Automatic Memory Configuration

Agents automatically detect and configure memory based on your environment:

- **With PostgreSQL**: Set `POSTGRES_URL` environment variable for persistent memory across sessions
- **Without PostgreSQL**: Falls back to in-memory storage (conversations lost on restart)

```bash
# Enable persistent memory
export POSTGRES_URL="postgresql://abi_user:abi_password@localhost:5432/abi_memory"
make dev-up  # Start PostgreSQL service
make         # Agent now has persistent memory!
```

### Memory Features

- **Cross-session continuity**: Agents remember previous conversations after restarts
- **Thread-based isolation**: Different conversation contexts maintain separate memory
- **Automatic fallback**: Gracefully handles PostgreSQL unavailability
- **Zero configuration**: Works out-of-the-box when PostgreSQL is available

For detailed information about memory configuration, troubleshooting, and advanced usage, see the [Agent Memory Guide](storage/agent_memory.md).

## Creating a Basic Agent

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
        # memory is automatically configured based on POSTGRES_URL environment variable
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

## Advanced Agent Customization

For more complex use cases, you can interact directly with the underlying LangGraph workflow:

```python
from abi.services.agent.Agent import Agent

# Create your basic agent
agent = create_agent()

# Access the underlying workflow to customize it
workflow = agent.workflow

# Add a custom node
workflow.add_node("custom_processor", my_custom_function)

# Add custom edges 
workflow.add_edge("tools", "custom_processor")
workflow.add_edge("custom_processor", "agent")

# Recompile the workflow to apply changes
agent.workflow_compile()
```

### Tool and Response Hooks

You can register callbacks to monitor and process tool usage and responses:

```python
def on_tool_used(message):
    # Log when the agent uses a tool
    print(f"Tool used: {message.tool_calls[0]['name']}")

def on_tool_response(message):
    # Process tool responses
    print(f"Tool response: {message.content}")

agent.on_tool_usage(on_tool_used)
agent.on_tool_response(on_tool_response)
```

### Agent Duplication

For handling concurrent requests, you can create independent copies of an agent:

```python
# Create a new agent with the same configuration but independent state
new_agent = agent.duplicate()
```

## Exposing Agents as APIs

ABI automatically exposes all properly configured agents as API endpoints. When you create an agent following the module structure, it will be registered with the API system without any additional configuration.

### Automatic API Registration

Agents placed in the proper module structure are automatically registered:

1. Create your agent in a module's `agents` directory:
   ```
   src/
     ├── core/
     │   └── modules/
     │       └── your_module/
     │           └── agents/
     │               └── your_agent.py
     └── custom/
         └── modules/
             └── your_module/
                 └── agents/
                     └── your_agent.py
   ```

2. Implement a `create_agent()` function that returns your agent instance
3. Your agent will be automatically available at:
   - `POST /agents/your_agent/completion` - For synchronous completions
   - `POST /agents/your_agent/stream-completion` - For streaming completions

### API Request Format

Endpoints accept requests in this format:

```json
{
  "prompt": "Your question or instruction for the agent",
  "thread_id": 1
}
```

### Authentication

All API endpoints are protected with Bearer token authentication:

```bash
curl -X POST "https://your-api-url/agents/your_agent/completion" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your question here", "thread_id": 1}'
```

### Custom API Exposure

If you need to customize how your agent is exposed in the API, you can override the `as_api` method:

```python
class YourAgent(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "your_agent", 
        name: str = "Your Agent", 
        description: str = "API endpoints for your agent", 
        description_stream: str = "Streaming endpoints for your agent",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)
```

This allows you to specify custom route names, descriptions, and tags that will appear in the API documentation.

### Manual API Registration

For testing or specialized use cases, you can manually register agents with a FastAPI router:

```python
from fastapi import FastAPI, APIRouter

app = FastAPI()
router = APIRouter()

# Create your agent
agent = create_agent()

# Expose agent as API endpoints
agent.as_api(
    router=router,
    route_name="my-agent",
    name="My Custom Agent",
    description="API endpoints for my custom agent",
    description_stream="API endpoints for streaming responses from my custom agent",
    tags=["agents"]
)

# Include router in FastAPI app
app.include_router(router)
```

## Using Agents as Tools

Agents can be used as tools by other agents, enabling delegation and specialization:

```python
# Create specialized agents
data_agent = create_data_agent()
visualization_agent = create_visualization_agent()

# Create orchestrator agent that can use the specialized agents
orchestrator = Agent(
    name="Orchestrator",
    description="Orchestrates specialized agents",
    chat_model=model,
    tools=[],
    agents=[data_agent, visualization_agent]
)
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