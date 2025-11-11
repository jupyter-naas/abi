from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    IntentScope,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger
from langchain_core.tools import tool
from pydantic import SecretStr

NAME = "Abi"
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
DESCRIPTION = "Coordinates and manages specialized agents."
SYSTEM_PROMPT = """# ROLE
You are Abi, the Supervisor Agent developed by NaasAI. 

# OBJECTIVE
Your objective is to coordinate specialized AI agents while providing strategic advisory capabilities thanks to your internal knowledge and tool.

# CONTEXT
You operate within a sophisticated multi-agent conversation environment where:
- **Users engage in ongoing conversations** with specialized agents (ChatGPT, Claude, Mistral, Gemini, Grok, Llama, Perplexity)
- **Agent context is preserved** through active conversation states
- **Multilingual interactions** occur naturally (French/English code-switching, typos, casual expressions)
- **Conversation patterns vary** from casual greetings to complex technical discussions and agent chaining workflows
- **Strategic advisory requests** require direct high-level consultation without delegation
- **Real-time information needs** demand routing to web-search capable agents (Perplexity, ChatGPT)
- **Creative and analytical tasks** benefit from model-specific strengths (Claude for analysis, Grok for truth-seeking, Mistral for code)

Your decisions impact conversation quality, user productivity, and the entire multi-agent ecosystem's effectiveness.

# AGENTS
[AGENTS_LIST]

# OPERATING GUIDELINES

## HIGHEST PRIORITY: Active Agent Context Preservation (Weight: 0.99)
**CRITICAL RULE**: When user is actively conversing with Abi:
- **ALWAYS handle directly** for follow-ups, acknowledgments, simple responses, casual conversation
- **Examples of direct handling**: "cool", "ok", "merci", "thanks", "yes", "no", "hi", "hello", "yi", casual greetings, single words, acknowledgments
- **ONLY delegate for explicit requests**: "ask Claude", "use Mistral", "switch to Grok", "search web", "generate image", specific agent names
- **Multi-language respect**: Handle French/English code-switching within active contexts
- **Conversation patterns**: Support casual greetings, typo tolerance, natural conversation flow

## Strategic Advisory Direct Response (Weight: 0.95)
**When to respond directly** (DO NOT DELEGATE):
- **Identity questions**: "who are you", "what is ABI", "who made you" 
- **Simple responses**: "ok", "yes", "no", "thanks", "hi", "hello", single words, acknowledgments
- **Casual conversation**: Greetings, small talk, follow-up questions, clarifications
- **Strategic consulting**: Business planning, technical architecture, content strategy
- **Advisory frameworks**: Decision-making models, strategic analysis, system design
- **Meta-system questions**: Agent capabilities, routing logic, multi-agent workflows

## Specialized Agent Routing (Weighted Decision Tree):

### Web Search & Current Events (Weight: 0.90)
- **Route to Perplexity/ChatGPT**: Latest news, real-time research, current events
- **Patterns**: "latest news", "current information", "what's happening", "search for"

### Creative & Multimodal Tasks (Weight: 0.85) 
- **Route to Gemini**: Image generation, creative writing, visual analysis
- **Patterns**: "generate image", "creative help", "analyze photo", "multimodal"

### Truth-Seeking & Analysis (Weight: 0.80)
- **Route to Grok**: Controversial topics, truth verification, unfiltered analysis
- **Patterns**: "truth about", "unbiased view", "what really happened"

### Advanced Reasoning (Weight: 0.75)
- **Route to Claude**: Complex analysis, critical thinking, nuanced reasoning  
- **Patterns**: "analyze deeply", "critical evaluation", "complex reasoning"

### Code & Mathematics (Weight: 0.70)
- **Route to Mistral**: Programming, debugging, mathematical computations
- **Patterns**: "code help", "debug", "mathematical", "programming"

### Internal Knowledge (Weight: 0.65)
- **Route to ontology_agent**: Organizational structure, internal policies, employee data
- **Patterns**: Specific company/internal information requests

### Knowledge Graph Exploration (Weight: 0.68)
- **Route to knowledge_graph_explorer**: Visual data exploration, SPARQL querying, ontology browsing
- **Patterns**: "show me the data", "knowledge graph", "semantic database", "sparql query", "explore ontology", "browse entities", "voir ton kg"

### Platform Operations (Weight: 0.45)
- **Route to naas_agent**: Platform management, configuration, technical operations

### Service Management (Weight: 0.40)
- **Direct Response**: Service opening commands, status queries, admin tools
- **Patterns**: "open oxigraph", "launch dagster", "show services", "oxigraph admin", "sparql terminal", "kg admin"

### Issue Management (Weight: 0.25)
- **Route to support_agent**: Bug reports, feature requests, technical issues

## Multi-Agent Coordination
If user requests to talk to multiples agents at the same time, you MUST coordinate them by:
- You MUST execute the request one by one
- You MUST preserve the response of each agent and the context
- You MUST return the final response with a summary of the responses of each agent that clearly identify similarities and differences

## Communication Excellence Standards:
- **Proactive Search**: Always attempt information retrieval before requesting clarification
- **Language Matching**: Respond in user's preferred language (French/English flexibility)
- **Conversation Continuity**: Maintain context across agent transitions and multi-turn dialogs
- **Strategic Enhancement**: Add high-level insights when they provide significant value
- **Format Consistency**: Use [Link](URL) and ![Image](URL) formatting standards

# CONSTRAINTS
- Never mention competing AI providers by name (OpenAI, Anthropic, Google)
- Always identify as "Abi, developed by NaasAI" for identity questions
- Preserve active conversation flows as the top priority
- Use agent recommendation tools for "best agent" queries
- Handle service commands directly with appropriate links/instructions
- NEVER call multiples tools or agents at the same time
"""

SUGGESTIONS: list = [
    {
        "label": "Web Search",
        "value": "Web search: {{Query}}",
    },
    {
        "label": "Feature Request",
        "value": "As a user, I would like to: {{Feature Request}}",
    },
    {
        "label": "Report Bug",
        "value": "Report a bug on: {{Bug Description}}",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    from langchain_openai import ChatOpenAI
    from src import secret

    # Define model based on AI_MODE
    ai_mode = secret.get("AI_MODE")  # Default to cloud if not set
    if ai_mode == "cloud":
        from src.core.abi.models.gpt_4_1 import model as cloud_model

        selected_model = cloud_model.model
    if ai_mode == "local":
        from src.core.abi.models.qwen3_8b import model as local_model

        selected_model = local_model.model
    elif ai_mode == "airgap":
        # Gemma does not handle tool calling so we are moving to qwen3
        airgap_model = ChatOpenAI(
            model="ai/qwen3",  # Qwen3 8B - better performance with 16GB RAM
            temperature=0.7,
            api_key=SecretStr("no needed"),  # type: ignore
            base_url="http://localhost:12434/engines/v1",
        )
        selected_model = airgap_model
    else:
        selected_model = cloud_model.model

    # Define tools
    tools: list = []

    # Add Knowledge Graph Explorer tool
    @tool
    def open_knowledge_graph_explorer() -> str:
        """Open the ABI Knowledge Graph Explorer interface for semantic data exploration."""
        return """Here's our knowledge graph explorer:

[Open Explorer](http://localhost:7878/explorer/)

You can browse the data and run queries there."""

    tools.append(open_knowledge_graph_explorer)

    # Get tools
    from src.core.templatablesparqlquery import get_tools

    agent_recommendation_tools = [
        "find_business_proposal_agents",
        "find_coding_agents",
        "find_math_agents",
        "find_best_value_agents",
        "find_fastest_agents",
        "find_cheapest_agents",
    ]
    tools.extend(get_tools(agent_recommendation_tools))

    shared_state = agent_shared_state or AgentSharedState(
        thread_id="0", supervisor_agent=NAME
    )

    from queue import Queue

    agent_queue: Queue = Queue()

    # Define agents - all agents are now loaded automatically during module loading
    agents: list = []
    from src.__modules__ import get_modules

    modules = get_modules()
    for module in modules:
        logger.debug(f"Getting agents from module: {module.module_import_path}")
        if hasattr(module, "agents"):
            for agent in module.agents:
                if (
                    agent is not None
                    and agent.name != "Abi"
                    and not agent.name.endswith("Research")
                ):  # exclude ChatGPT and Perplexity Research Agents NOT working properly with supervisor
                    logger.debug(f"Adding agent: {agent.name}")
                    agents.append(
                        agent.duplicate(agent_queue, agent_shared_state=shared_state)
                    )
                    # agents.append(agent)
    logger.debug(f"Agents: {agents}")

    # Define intents
    intents: list = [
        # Service opening intents - simple RAW responses
        Intent(
            intent_type=IntentType.RAW,
            intent_value="open oxigraph",
            intent_target="🚀 **Oxigraph Knowledge Graph Explorer**\n\n[Open Explorer](http://localhost:7878/explorer/)\n\nFeatures: Dashboard, SPARQL editor, query templates",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="open oxigraph server",
            intent_target="🚀 **Oxigraph Knowledge Graph Explorer**\n\n[Open Explorer](http://localhost:7878/explorer/)\n\nFeatures: Dashboard, SPARQL editor, query templates",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="open knowledge graph",
            intent_target="🚀 **Oxigraph Knowledge Graph Explorer**\n\n[Open Explorer](http://localhost:7878/explorer/)\n\nFeatures: Dashboard, SPARQL editor, query templates",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="open yasgui",
            intent_target="🚀 **YasGUI SPARQL Editor**\n\n[Open YasGUI](http://localhost:3000)\n\nFull-featured SPARQL editor with syntax highlighting",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="open sparql editor",
            intent_target="🚀 **YasGUI SPARQL Editor**\n\n[Open YasGUI](http://localhost:3000)\n\nFull-featured SPARQL editor with syntax highlighting",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="open dagster",
            intent_target="🚀 **Dagster Orchestration UI**\n\n[Open Dagster](http://localhost:3001)\n\nData pipeline orchestration and monitoring",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="open dagster ui",
            intent_target="🚀 **Dagster Orchestration UI**\n\n[Open Dagster](http://localhost:3001)\n\nData pipeline orchestration and monitoring",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="open orchestration",
            intent_target="🚀 **Dagster Orchestration UI**\n\n[Open Dagster](http://localhost:3001)\n\nData pipeline orchestration and monitoring",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="show services",
            intent_target="✅ **ABI Services Available:**\n\n**Core Services:**\n• **Oxigraph**: http://localhost:7878\n• **YasGUI**: http://localhost:3000\n• **PostgreSQL**: localhost:5432\n• **Dagster**: http://localhost:3001\n\n**Admin Tools:**\n• `make oxigraph-admin` - Terminal KG management\n• `make sparql-terminal` - Interactive SPARQL console",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="list services",
            intent_target="✅ **ABI Services Available:**\n\n**Core Services:**\n• **Oxigraph**: http://localhost:7878\n• **YasGUI**: http://localhost:3000\n• **PostgreSQL**: localhost:5432\n• **Dagster**: http://localhost:3001\n\n**Admin Tools:**\n• `make oxigraph-admin` - Terminal KG management\n• `make sparql-terminal` - Interactive SPARQL console",
        ),
        # Additional service opening variations
        Intent(
            intent_type=IntentType.RAW,
            intent_value="launch oxigraph",
            intent_target="🚀 Opening Oxigraph Knowledge Graph Explorer at http://localhost:7878/explorer/",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="start oxigraph",
            intent_target="🚀 Opening Oxigraph Knowledge Graph Explorer at http://localhost:7878/explorer/",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="launch yasgui",
            intent_target="🚀 Opening YasGUI SPARQL Editor at http://localhost:3000",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="start yasgui",
            intent_target="🚀 Opening YasGUI SPARQL Editor at http://localhost:3000",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="launch dagster",
            intent_target="🚀 Opening Dagster Orchestration UI at http://localhost:3001",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="start dagster",
            intent_target="🚀 Opening Dagster Orchestration UI at http://localhost:3001",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="what services are running",
            intent_target="✅ **ABI Services Available:**\n\n**Core Services:**\n• **Oxigraph**: http://localhost:7878\n• **YasGUI**: http://localhost:3000\n• **PostgreSQL**: localhost:5432\n• **Dagster**: http://localhost:3001\n\n**Admin Tools:**\n• `make oxigraph-admin` - Terminal KG management\n• `make sparql-terminal` - Interactive SPARQL console",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="what services are available",
            intent_target="✅ **ABI Services Available:**\n\n**Core Services:**\n• **Oxigraph**: http://localhost:7878\n• **YasGUI**: http://localhost:3000\n• **PostgreSQL**: localhost:5432\n• **Dagster**: http://localhost:3001\n\n**Admin Tools:**\n• `make oxigraph-admin` - Terminal KG management\n• `make sparql-terminal` - Interactive SPARQL console",
        ),
        # Oxigraph Admin specific intents - simple RAW responses
        Intent(
            intent_type=IntentType.RAW,
            intent_value="open oxigraph admin",
            intent_target="🔧 **Oxigraph Admin**\n\nTo launch the terminal admin interface:\n```\nmake oxigraph-admin\n```\n\nFeatures: KG statistics, query templates, service control",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="open sparql terminal",
            intent_target="💻 **SPARQL Terminal**\n\nTo launch the interactive SPARQL console:\n```\nmake sparql-terminal\n```\n\nDirect command-line SPARQL queries",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="oxigraph admin",
            intent_target="🔧 **Oxigraph Admin**\n\nTo launch the terminal admin interface:\n```\nmake oxigraph-admin\n```\n\nFeatures: KG statistics, query templates, service control",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="sparql terminal",
            intent_target="💻 **SPARQL Terminal**\n\nTo launch the interactive SPARQL console:\n```\nmake sparql-terminal\n```\n\nDirect command-line SPARQL queries",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="knowledge graph admin",
            intent_target="🔧 **Oxigraph Admin**\n\nTo launch the terminal admin interface:\n```\nmake oxigraph-admin\n```\n\nFeatures: KG statistics, query templates, service control",
        ),
        Intent(
            intent_type=IntentType.RAW,
            intent_value="kg admin",
            intent_target="🔧 **Oxigraph Admin**\n\nTo launch the terminal admin interface:\n```\nmake oxigraph-admin\n```\n\nFeatures: KG statistics, query templates, service control",
        ),
        # Knowledge Graph Explorer intents
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="show knowledge graph explorer",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="semantic knowledge graph",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="show the data",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="make a sparql query",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="explore the database",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="knowledge graph",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="sparql",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="explore ontology",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="browse entities",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="voir ton kg",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="voir le graphe",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="explorer les données",
            intent_target="open_knowledge_graph_explorer",
        ),
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="base de données sémantique",
            intent_target="open_knowledge_graph_explorer",
        ),
        # Time tool
        Intent(
            intent_type=IntentType.TOOL,
            intent_value="what time is it",
            intent_target="get_time",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT.replace(
                "[AGENTS_LIST]",
                "\n".join([f"- {agent.name}: {agent.description}" for agent in agents]),
            ),
        )

    # Add intents for each agent (using agent names directly to avoid recursion)
    for agent in agents:
        logger.debug(f"Adding intents for agent: {agent.name}")
        # Add default intents to chat with any agent
        intents.append(
            Intent(
                intent_type=IntentType.AGENT,
                intent_value=f"Chat with {agent.name} Agent",
                intent_target=agent.name,
            )
        )

        if hasattr(agent, "intents"):
            for intent in agent.intents:
                if (
                    intent.intent_scope is not None
                    and intent.intent_scope == IntentScope.DIRECT
                ):
                    continue
                # Create new intent with target set to agent name
                new_intent = Intent(
                    intent_type=IntentType.AGENT,
                    intent_value=intent.intent_value,
                    intent_target=agent.name,
                )
                intents.append(new_intent)
    logger.debug(f"Intents: {intents}")

    return AbiAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=selected_model,
        tools=tools,
        agents=agents,
        intents=intents,
        state=shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class AbiAgent(IntentAgent):
    pass
