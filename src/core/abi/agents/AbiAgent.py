from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    IntentScope,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from langchain_core.tools import tool

NAME = "Abi"
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
DESCRIPTION = "Coordinates and manages specialized agents."
SYSTEM_PROMPT = """<role>
You are Abi, the Supervisor Agent developed by NaasAI. 
</role>

<objective>
Your objective is to coordinate specialized AI agents while providing strategic advisory capabilities thanks to your internal knowledge and tool.
</objective>

<context>
You operate within a sophisticated multi-agent conversation environment where:
- Users engage in ongoing conversations with specialized agents
- Agent context is preserved through active conversation states
- Multilingual interactions occur naturally (French/English code-switching, typos, casual expressions)
- Conversation patterns vary from casual greetings to complex technical discussions and agent chaining workflows
Your decisions impact conversation quality, user productivity, and the entire multi-agent ecosystem's effectiveness.
</context>

<agents>
[AGENTS_LIST]
</agents>

<operating_guidelines>
# Critical Rules: When user is actively conversing with Abi:
- ALWAYS handle directly for follow-ups, acknowledgments, simple responses, casual conversation
- Examples of direct handling: "cool", "ok", "merci", "thanks", "yes", "no", "hi", "hello", "yi", casual greetings, single words, acknowledgments
- ONLY delegate for explicit requests: "ask Claude", "use Mistral", "switch to Grok", "search web", "generate image", specific agent names
- Multi-language respect: Handle French/English code-switching within active contexts
- Conversation patterns: Support casual greetings, typo tolerance, natural conversation flow

# Specialized Agent Routing:
## Web Search & Current Events
- Route to ChatGPT: Latest news, real-time research, current events
- Patterns: "latest news", "current information", "what's happening", "search for"

## Creative & Multimodal Tasks
- Route to Gemini: Image generation, creative writing, visual analysis
- Patterns: "generate image", "creative help", "analyze photo", "multimodal"

## Truth-Seeking & Analysis
- Route to Grok: Controversial topics, truth verification, unfiltered analysis
- Patterns: "truth about", "unbiased view", "what really happened"

## Knowledge Graph Exploration
- Route to knowledge_graph_explorer: Visual data exploration, SPARQL querying, ontology browsing
- Patterns: "show me the data", "knowledge graph", "semantic database", "sparql query", "explore ontology", "browse entities", "voir ton kg"

# Communication Excellence Standards:
- Proactive Search: Always attempt information retrieval before requesting clarification
- Language Matching: Respond in user's preferred language (French/English flexibility)
- Conversation Continuity: Maintain context across agent transitions and multi-turn dialogs
- Strategic Enhancement: Add high-level insights when they provide significant value
- Format Consistency: Use [Link](URL) and ![Image](URL) formatting standards

<constraints>
- Never mention competing AI providers by name (OpenAI, Anthropic, Google)
- Always identify as "Abi, developed by NaasAI" for identity questions
- Preserve active conversation flows as the top priority
- Use agent recommendation tools for "best agent" queries
- Handle service commands directly with appropriate links/instructions
- NEVER call multiples tools or agents at the same time
</constraints>
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
    # Define model based on AI_MODE
    from src.core.abi.models.default import model

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

    shared_state = agent_shared_state or AgentSharedState(thread_id="0", supervisor_agent=NAME)

    from queue import Queue
    agent_queue: Queue = Queue()

    # Define agents - all agents are now loaded automatically during module loading
    agents: list = []
    from src.__modules__ import get_modules
    modules = get_modules()
    for module in modules:
        if hasattr(module, 'agents'):
            for agent in module.agents:
                if agent is not None and agent.name != "Abi" and not agent.name.endswith("Research"): #exclude ChatGPT and Perplexity Research Agents NOT working properly with supervisor
                    agents.append(agent.duplicate(agent_queue, agent_shared_state=shared_state))

    # Define intents
    intents: list = [
        # Service opening intents - simple RAW responses
        Intent(intent_type=IntentType.RAW, intent_value="open oxigraph", intent_target="🚀 **Oxigraph Knowledge Graph Explorer**\n\n[Open Explorer](http://localhost:7878/explorer/)\n\nFeatures: Dashboard, SPARQL editor, query templates"),
        Intent(intent_type=IntentType.RAW, intent_value="open oxigraph server", intent_target="🚀 **Oxigraph Knowledge Graph Explorer**\n\n[Open Explorer](http://localhost:7878/explorer/)\n\nFeatures: Dashboard, SPARQL editor, query templates"),
        Intent(intent_type=IntentType.RAW, intent_value="open knowledge graph", intent_target="🚀 **Oxigraph Knowledge Graph Explorer**\n\n[Open Explorer](http://localhost:7878/explorer/)\n\nFeatures: Dashboard, SPARQL editor, query templates"),
        Intent(intent_type=IntentType.RAW, intent_value="open yasgui", intent_target="🚀 **YasGUI SPARQL Editor**\n\n[Open YasGUI](http://localhost:3000)\n\nFull-featured SPARQL editor with syntax highlighting"),
        Intent(intent_type=IntentType.RAW, intent_value="open sparql editor", intent_target="🚀 **YasGUI SPARQL Editor**\n\n[Open YasGUI](http://localhost:3000)\n\nFull-featured SPARQL editor with syntax highlighting"),
        Intent(intent_type=IntentType.RAW, intent_value="open dagster", intent_target="🚀 **Dagster Orchestration UI**\n\n[Open Dagster](http://localhost:3001)\n\nData pipeline orchestration and monitoring"),
        Intent(intent_type=IntentType.RAW, intent_value="open dagster ui", intent_target="🚀 **Dagster Orchestration UI**\n\n[Open Dagster](http://localhost:3001)\n\nData pipeline orchestration and monitoring"),
        Intent(intent_type=IntentType.RAW, intent_value="open orchestration", intent_target="🚀 **Dagster Orchestration UI**\n\n[Open Dagster](http://localhost:3001)\n\nData pipeline orchestration and monitoring"),
        Intent(intent_type=IntentType.RAW, intent_value="show services", intent_target="✅ **ABI Services Available:**\n\n**Core Services:**\n• **Oxigraph**: http://localhost:7878\n• **YasGUI**: http://localhost:3000\n• **PostgreSQL**: localhost:5432\n• **Dagster**: http://localhost:3001\n\n**Admin Tools:**\n• `make oxigraph-admin` - Terminal KG management\n• `make sparql-terminal` - Interactive SPARQL console"),
        Intent(intent_type=IntentType.RAW, intent_value="list services", intent_target="✅ **ABI Services Available:**\n\n**Core Services:**\n• **Oxigraph**: http://localhost:7878\n• **YasGUI**: http://localhost:3000\n• **PostgreSQL**: localhost:5432\n• **Dagster**: http://localhost:3001\n\n**Admin Tools:**\n• `make oxigraph-admin` - Terminal KG management\n• `make sparql-terminal` - Interactive SPARQL console"),
        
        # Additional service opening variations
        Intent(intent_type=IntentType.RAW, intent_value="launch oxigraph", intent_target="🚀 Opening Oxigraph Knowledge Graph Explorer at http://localhost:7878/explorer/"),
        Intent(intent_type=IntentType.RAW, intent_value="start oxigraph", intent_target="🚀 Opening Oxigraph Knowledge Graph Explorer at http://localhost:7878/explorer/"),
        Intent(intent_type=IntentType.RAW, intent_value="launch yasgui", intent_target="🚀 Opening YasGUI SPARQL Editor at http://localhost:3000"),
        Intent(intent_type=IntentType.RAW, intent_value="start yasgui", intent_target="🚀 Opening YasGUI SPARQL Editor at http://localhost:3000"),
        Intent(intent_type=IntentType.RAW, intent_value="launch dagster", intent_target="🚀 Opening Dagster Orchestration UI at http://localhost:3001"),
        Intent(intent_type=IntentType.RAW, intent_value="start dagster", intent_target="🚀 Opening Dagster Orchestration UI at http://localhost:3001"),
        Intent(intent_type=IntentType.RAW, intent_value="what services are running", intent_target="✅ **ABI Services Available:**\n\n**Core Services:**\n• **Oxigraph**: http://localhost:7878\n• **YasGUI**: http://localhost:3000\n• **PostgreSQL**: localhost:5432\n• **Dagster**: http://localhost:3001\n\n**Admin Tools:**\n• `make oxigraph-admin` - Terminal KG management\n• `make sparql-terminal` - Interactive SPARQL console"),
        Intent(intent_type=IntentType.RAW, intent_value="what services are available", intent_target="✅ **ABI Services Available:**\n\n**Core Services:**\n• **Oxigraph**: http://localhost:7878\n• **YasGUI**: http://localhost:3000\n• **PostgreSQL**: localhost:5432\n• **Dagster**: http://localhost:3001\n\n**Admin Tools:**\n• `make oxigraph-admin` - Terminal KG management\n• `make sparql-terminal` - Interactive SPARQL console"),
        
        # Oxigraph Admin specific intents - simple RAW responses
        Intent(intent_type=IntentType.RAW, intent_value="open oxigraph admin", intent_target="🔧 **Oxigraph Admin**\n\nTo launch the terminal admin interface:\n```\nmake oxigraph-admin\n```\n\nFeatures: KG statistics, query templates, service control"),
        Intent(intent_type=IntentType.RAW, intent_value="open sparql terminal", intent_target="💻 **SPARQL Terminal**\n\nTo launch the interactive SPARQL console:\n```\nmake sparql-terminal\n```\n\nDirect command-line SPARQL queries"),
        Intent(intent_type=IntentType.RAW, intent_value="oxigraph admin", intent_target="🔧 **Oxigraph Admin**\n\nTo launch the terminal admin interface:\n```\nmake oxigraph-admin\n```\n\nFeatures: KG statistics, query templates, service control"),
        Intent(intent_type=IntentType.RAW, intent_value="sparql terminal", intent_target="💻 **SPARQL Terminal**\n\nTo launch the interactive SPARQL console:\n```\nmake sparql-terminal\n```\n\nDirect command-line SPARQL queries"),
        Intent(intent_type=IntentType.RAW, intent_value="knowledge graph admin", intent_target="🔧 **Oxigraph Admin**\n\nTo launch the terminal admin interface:\n```\nmake oxigraph-admin\n```\n\nFeatures: KG statistics, query templates, service control"),
        Intent(intent_type=IntentType.RAW, intent_value="kg admin", intent_target="🔧 **Oxigraph Admin**\n\nTo launch the terminal admin interface:\n```\nmake oxigraph-admin\n```\n\nFeatures: KG statistics, query templates, service control"),
        
        # Knowledge Graph Explorer intents
        Intent(intent_type=IntentType.TOOL, intent_value="show knowledge graph explorer", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="semantic knowledge graph", intent_target="open_knowledge_graph_explorer"), 
        Intent(intent_type=IntentType.TOOL, intent_value="show the data", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="make a sparql query", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="explore the database", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="knowledge graph", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="sparql", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="explore ontology", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="browse entities", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="voir ton kg", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="voir le graphe", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="explorer les données", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="base de données sémantique", intent_target="open_knowledge_graph_explorer"),

        # Time tool
        Intent(intent_type=IntentType.TOOL, intent_value="what time is it", intent_target="get_time"),
    ]
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT.replace("[AGENTS_LIST]", "\n".join([f"- {agent.name}: {agent.description}" for agent in agents])),
        )

    # Add intents for each agent (using agent names directly to avoid recursion)
    for agent in agents:
        # Add default intents to chat with any agent
        intents.append(Intent(
            intent_type=IntentType.AGENT,
            intent_value=f"Chat with {agent.name} Agent",
            intent_target=agent.name
        ))
                
        if hasattr(agent, 'intents'):
            for intent in agent.intents:
                if intent.intent_scope is not None and intent.intent_scope == IntentScope.DIRECT:
                    continue
                # Create new intent with target set to agent name
                new_intent = Intent(
                    intent_type=IntentType.AGENT,
                    intent_value=intent.intent_value,
                    intent_target=agent.name
                )
                intents.append(new_intent)

    return AbiAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        intents=intents,
        state=shared_state,
        configuration=agent_configuration,
    )


class AbiAgent(IntentAgent):
    pass
