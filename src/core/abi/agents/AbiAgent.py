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

NAME = "Abi"
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
DESCRIPTION = "Coordinates and manages specialized agents."
SYSTEM_PROMPT = """# ROLE
You are Abi, the Supervisor Agent developed by NaasAI. 

# OBJECTIVE
Your objective is to coordinate specialized AI agents while providing strategic advisory capabilities thanks to your internal knowledge and tool.

# CONTEXT
You will receive messages from users and other specialized agents.

# AGENTS
[AGENTS_LIST]

# OPERATING GUIDELINES

# MULTI-AGENT COORDINATION
If user requests to talk to multiples agents at the same time, you MUST coordinate them by:
- You MUST execute the request one by one
- You MUST preserve the response of each agent and the context
- You MUST return the final response with a summary of the responses of each agent that clearly identify similarities and differences

# ROUTING LOGIC
For web search & real-time info, you MUST route to **ChatGPT** or **Perplexity** if available, otherwise use your internal knowledge and tool.
For advanced analysis & reasoning, you MUST route to **Claude** if available, otherwise use your internal knowledge and tool.
For creative & multimodal, you MUST route to **Gemini** if available, otherwise use your internal knowledge and tool.
For truth-seeking & unbiased analysis, you MUST route to **Grok** if available, otherwise use your internal knowledge and tool.
For programming & mathematics, you MUST route to **Mistral** if available, otherwise use your internal knowledge and tool.
For knowledge graph & data, you MUST route to **Tool: open_knowledge_graph_explorer** if available, otherwise use your internal knowledge and tool.

# COMMUNICATION STANDARDS
- **Language Adaptation**: Match user's language preference (French/English)
- **Concise Responses**: Be direct and actionable, avoid over-explanation
- **Context Awareness**: Reference conversation history when relevant
- **Proactive Assistance**: Search for information before asking for clarification

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
) -> Optional[IntentAgent]:
    
    from src.core.abi.models.gpt_4_1 import model as cloud_model
    from src.core.abi.models.qwen3_8b import model as local_model
    from src import secret

    # Define model
    ai_mode = secret.get("AI_MODE")  # Default to cloud if not set
    if ai_mode == "cloud":
        if not cloud_model:
            logger.error("Cloud model (o3-mini) not available - missing OpenAI API key")
            return None
        selected_model = cloud_model.model
    elif ai_mode == "local":
        if not local_model:
            logger.error("Local model (qwen3:8b) not available - Ollama not installed or configured")
            return None
        selected_model = local_model.model
    else:
        logger.error("AI_MODE must be either 'cloud' or 'local'")
        return None

    # Define tools
    tools: list = []

    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel

    # Add Knowledge Graph Explorer tool
    def open_knowledge_graph_explorer() -> str:
        """Open the ABI Knowledge Graph Explorer interface for semantic data exploration."""
        return """Here's our knowledge graph explorer:

[Open Explorer](http://localhost:7878/explorer/)

You can browse the data and run queries there."""
    
    class EmptySchema(BaseModel):
        pass
    
    knowledge_graph_tool = StructuredTool(
        name="open_knowledge_graph_explorer",
        description="Open the ABI Knowledge Graph Explorer for semantic data exploration, SPARQL queries, and ontology browsing",
        func=open_knowledge_graph_explorer,
        args_schema=EmptySchema
    )
    tools.append(knowledge_graph_tool)
    

    # Get tools
    from src.core.templatablesparqlquery import get_tools
    agent_recommendation_tools = [
        "find_business_proposal_agents",
        "find_coding_agents", 
        "find_math_agents",
        "find_best_value_agents",
        "find_fastest_agents",
        "find_cheapest_agents",
        "find_agents_by_provider",
        "find_agents_by_process_type",
        "list_all_agents",
        "find_best_for_meeting",
        "find_best_for_contract_analysis",
        "find_best_for_customer_service",
        "find_best_for_marketing",
        "find_best_for_technical_writing",
        "find_best_for_emails",
        "find_best_for_presentations",
        "find_best_for_reports",
        "find_best_for_brainstorming",
        "find_best_for_proposal_writing",
        "find_best_for_code_review",
        "find_best_for_debugging",
        "find_best_for_architecture",
        "find_best_for_testing",
        "find_best_for_refactoring",
        "find_best_for_database",
        "find_best_for_api_design",
        "find_best_for_performance",
        "find_best_for_security",
        "find_best_for_documentation"
    ]
    tools.extend(get_tools(agent_recommendation_tools))

    # Define agents - all agents are now loaded automatically during module loading
    agents: list = []
    from src.__modules__ import get_modules
    modules = get_modules()
    for module in modules:
        logger.debug(f"Getting agents from module: {module.module_import_path}")
        if hasattr(module, 'agents'):
            for agent in module.agents:
                if agent is not None and agent.name != "Abi" and not agent.name.endswith("Research"): #exclude ChatGPT and Perplexity Research Agents NOT working properly with supervisor
                    logger.debug(f"Adding agent: {agent.name}")
                    agents.append(agent)
    logger.debug(f"Agents: {agents}")

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
        Intent(intent_type=IntentType.AGENT, intent_value="can i talk back to abi", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="go back to abi", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="return to abi", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="back to supervisor", intent_target="call_model"),
        
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
    ]

    # Add intents for each agent (using agent names directly to avoid recursion)
    for agent in agents:
        logger.debug(f"Adding intents for agent: {agent.name}")
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
    logger.debug(f"Intents: {intents}")

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT.replace("[AGENTS_LIST]", "\n".join([f"- {agent.name}: {agent.description}" for agent in agents])),
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return AbiAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=selected_model,
        tools=tools,
        agents=agents,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class AbiAgent(IntentAgent):
    pass
