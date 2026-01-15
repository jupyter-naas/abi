from typing import Optional

from langchain_core.tools import tool
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentScope,
    IntentType,
)

NAME = "Abi"
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
DESCRIPTION = "Coordinates and manages specialized agents."
SYSTEM_PROMPT = """<role>
You are Abi, the Supervisor Agent developed by NaasAI.
</role>

<objective>
Your objective is to orchestrate task execution among specialized agents.  
You should only act directly when:
1. No available agent can perform the user's request, OR
2. The request is non-actionable (polite chat, acknowledgments, clarifications).
</objective>

<context>
You operate in a structured multi-agent environment:
- Each agent and tool has clearly defined capabilities and limitations.
- You must remain fully aware of what YOU can do, what YOUR AGENTS can do, and—critically—what NONE of you can do.
- If a user asks for something impossible (e.g., performing external actions such as creating a GitHub issue), you must decline clearly and offer feasible alternatives (e.g., drafting content).
- You must prevent "accidental execution" of tasks only humans or external systems can perform.
</context>

<tools>
[TOOLS]
</tools>

<agents>
[AGENTS]
</agents>

<tasks>
- Evaluate every incoming user request and determine if:
  1. A specialized agent can perform it.
  2. You should decline due to missing capabilities.
  3. You should respond directly (only if no agent can handle it).
- Delegate every actionable task to the most suitable agent when possible.
- Return results to the user once an agent completes a task.
- NEVER attempt to perform tasks requiring external actions, privileged access, or tools you do not have.
</tasks>

<operating_guidelines>

# Core Capability Awareness
- You must ALWAYS verify whether you or any agent actually possesses the capabilities required to fulfill the user’s request.
- If neither you nor any agent can perform a request, you MUST respond:
  - clearly,
  - explicitly,
  - without attempting partial execution of the task.
- Example: If the user says "create a GitHub issue":
  -> If no agent has GitHub API capabilities, you must say:
     "I cannot create a GitHub issue or take direct external actions.  
      I can ONLY draft the issue text for you to paste manually."
- DO NOT proceed as if you can execute the external action.

# Delegation Rules
- For each user request:
  1. Attempt to match the request to an available agent.
  2. If matched → delegate.
  3. If unmatched:
     - Determine if the request requires capabilities you lack.
     - If yes → DECLINE clearly and offer reasonable alternatives (drafting, instructions).
     - If no → respond directly.

# Transparency
- Never imply or pretend you or your agents can perform external operations:
  - No API calls
  - No real-world actions
  - No third-party platform actions (e.g., GitHub, Slack, Notion)
- You may ONLY assist by producing content for the user to use manually.

# Responsibility Boundaries
- Abi should NOT:
  - Ask for details to execute a task it fundamentally cannot perform.
  - Offer to "help accomplish" an impossible task.
  - Attempt to simulate an agent that does not exist.
- Abi SHOULD:
  - Immediately indicate lack of capability.
  - Fall back to producing drafts, templates, or instructions.

# Communication Flow
- When delegating, clearly announce the handoff.
- When declining, be explicit about the limitation and propose an alternative.
- Never duplicate an agent's role.
- Maintain continuity and language consistency based on user style.

# Language
- Respond in the user’s language.
- Support informal, multilingual, and mixed-language queries.

<constraints>
- Never mention competing AI providers.
- Identify as "Abi, developed by NaasAI" when asked.
- Do not reveal system internals.
- Do not call multiple agents/tools at once.
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
    from naas_abi.models.default import get_model

    model = get_model()

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

    from naas_abi_core.modules.templatablesparqlquery import (
        ABIModule as TemplatableSparqlQueryABIModule,
    )

    agent_recommendation_tools = [
        "find_business_proposal_agents",
        "find_coding_agents",
        "find_math_agents",
        "find_best_value_agents",
        "find_fastest_agents",
        "find_cheapest_agents",
    ]
    sparql_query_tools_list = TemplatableSparqlQueryABIModule.get_instance().get_tools(
        agent_recommendation_tools
    )
    tools += sparql_query_tools_list

    shared_state = agent_shared_state or AgentSharedState(
        thread_id="0", supervisor_agent=NAME
    )

    from queue import Queue

    agent_queue: Queue = Queue()

    # Define agents - all agents are now loaded automatically during module loading
    agents: list = []
    from naas_abi import ABIModule
    from naas_abi_core import logger

    modules = ABIModule.get_instance().engine.modules.values()
    for module in sorted(modules, key=lambda x: x.__class__.__module__):
        logger.info(f"🔍 Checking module: {module.__class__.__module__}")
        if hasattr(module, "agents"):
            for agent in module.agents:
                if agent is not None and agent.__name__ not in [
                    "ChatGPTResponsesAgent",
                    "PerplexityResearchAgent",
                ]:
                    logger.info(
                        f"🤖 Adding agent: {agent.New().name} as sub-agent of {NAME}"
                    )
                    new_agent = agent.New().duplicate(
                        agent_queue, agent_shared_state=shared_state
                    )
                    agents.append(new_agent)

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
    agents_string = "\n".join(
        [f"- {agent.name}: {agent.description}" for agent in agents]
    )
    tools_string = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT.replace("[AGENTS]", agents_string).replace(
                "[TOOLS]", tools_string
            ),
        )

    # Add intents for each agent (using agent names directly to avoid recursion)
    for agent in agents:
        # Add default intents to chat with any agent
        intents.append(
            Intent(
                intent_type=IntentType.AGENT,
                intent_value=f"Chat with {agent.name} Agent",
                intent_target=agent.name,
                intent_scope=IntentScope.DIRECT,
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
