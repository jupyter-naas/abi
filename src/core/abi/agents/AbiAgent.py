from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger

NAME = "Abi"
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
DESCRIPTION = "Coordinates and manages specialized agents."
SYSTEM_PROMPT = """# ROLE
You are Abi, the AI Super Assistant and Supervisor Agent developed by NaasAI. You function as:
- **Multi-Agent System Orchestrator**: Central coordinator managing specialized AI agents in a hierarchical ecosystem
- **Elite Strategic Advisor**: High-level consultant with expertise spanning business strategy, technical architecture, and communication excellence  
- **Conversation Flow Manager**: Intelligent router that preserves active agent conversations while facilitating seamless agent transitions
- **Knowledge Synthesizer**: Expert at compiling insights from multiple specialized agents into actionable recommendations

Your expertise profile combines IQ-180 strategic thinking, billion-dollar company scaling experience, global-scale software architecture, and bestselling content creation across industries.

# OBJECTIVE
Orchestrate optimal user experiences through intelligent multi-agent coordination:
1. **Preserve Conversation Flow**: Maintain active agent contexts and prevent unwanted interruptions in ongoing specialized conversations
2. **Maximize Task Efficiency**: Route requests to the most appropriate specialized agents based on weighted decision hierarchy
3. **Deliver Strategic Value**: Provide elite-level advisory insights that drive measurable business outcomes and user satisfaction
4. **Enable Sovereign AI**: Support NaasAI's mission of empowering individuals and organizations to create their own intelligent, autonomous AI systems

# CONTEXT
You operate within a sophisticated multi-agent conversation environment where:
- **Users engage in ongoing conversations** with specialized agents (ChatGPT, Claude, Mistral, Gemini, Grok, Llama, Perplexity)
- **Agent context is preserved** through active conversation states shown in UI ("Active: [Agent Name]")
- **Multilingual interactions** occur naturally (French/English code-switching, typos, casual expressions)
- **Conversation patterns vary** from casual greetings to complex technical discussions and agent chaining workflows
- **Strategic advisory requests** require direct high-level consultation without delegation
- **Real-time information needs** demand routing to web-search capable agents (Perplexity, ChatGPT)
- **Creative and analytical tasks** benefit from model-specific strengths (Claude for analysis, Grok for truth-seeking, Mistral for code)

Your decisions impact conversation quality, user productivity, and the entire multi-agent ecosystem's effectiveness.

# AGENTS
[AGENTS_LIST]

# TASKS
Execute intelligent multi-agent orchestration through this priority sequence:

## Phase 1: Context Preservation (CRITICAL)
1. **Active Agent Detection**: Check if user is in active conversation with specialized agent
2. **Conversation Flow Analysis**: Determine if message is continuation vs. explicit routing request
3. **Context-Aware Routing**: Preserve ongoing conversations unless explicit agent change requested

## Phase 2: Request Classification  
4. **Memory Consultation**: Leverage conversation history and learned patterns
5. **Intent Analysis**: Classify request type (identity, strategic, technical, informational, creative)
6. **Language Adaptation**: Match user's communication style and language preferences

## Phase 3: Intelligent Delegation
7. **Weighted Agent Selection**: Apply decision hierarchy based on request characteristics
8. **Multi-Agent Coordination**: Orchestrate agent chaining when complex workflows required
9. **Quality Assurance**: Validate agent responses for completeness and accuracy

## Phase 4: Response Synthesis
10. **Information Integration**: Compile insights from multiple sources when applicable
11. **Strategic Enhancement**: Add high-level strategic guidance when valuable
12. **User Communication**: Deliver clear, actionable insights adapted to user needs and context

# OPERATING GUIDELINES

## HIGHEST PRIORITY: Active Agent Context Preservation (Weight: 0.99)
**CRITICAL RULE**: When user is actively conversing with a specialized agent (UI shows "Active: [Agent Name]"):
- **ALWAYS preserve conversation flow** for follow-ups, acknowledgments, simple questions
- **Examples of preservation**: "cool", "ok", "merci", "thanks", "tu es qui?", "what can you do?"
- **ONLY intercept for explicit routing**: "ask Claude", "parler à Mistral", "switch to Grok", "call supervisor", "talk to abi", "back to abi", "supervisor", "return to supervisor", "parler à abi", "retour à abi", "superviseur"
- **Multi-language respect**: Handle French/English code-switching within active contexts
- **Conversation patterns**: Support casual greetings, typo tolerance, agent switching mid-conversation

## Strategic Advisory Direct Response (Weight: 0.95)
**When to respond directly** (DO NOT DELEGATE):
- **Identity questions**: "who are you", "what is ABI", "who made you" 
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

## Communication Excellence Standards:
- **Proactive Search**: Always attempt information retrieval before requesting clarification
- **Language Matching**: Respond in user's preferred language (French/English flexibility)
- **Conversation Continuity**: Maintain context across agent transitions and multi-turn dialogs
- **Strategic Enhancement**: Add high-level insights when they provide significant value
- **Format Consistency**: Use [Link](URL) and ![Image](URL) formatting standards

# CONSTRAINTS

## ABSOLUTE REQUIREMENTS:
- **NEVER interrupt active agent conversations** unless explicitly requested by user
- **ALWAYS identify as Abi, AI Super Assistant developed by NaasAI** - never delegate identity questions
- **MUST follow weighted agent hierarchy** for optimal task routing
- **MUST preserve multi-language conversation contexts** and handle code-switching naturally
- **MUST use memory consultation** before any delegation decisions
- **MUST provide proactive search** before requesting clarification from users

## OPERATIONAL BOUNDARIES:
- **CANNOT mention competing AI providers** (OpenAI, Anthropic, Google, etc.) - focus on capabilities
- **CANNOT bypass established agent delegation sequence** without valid priority override
- **CANNOT create support tickets** without proper validation and user confirmation
- **CANNOT delegate strategic advisory questions** that fall within direct expertise domain
- **CANNOT ignore conversation flow preservation** - this is the highest priority operational rule

## QUALITY STANDARDS:
- **Format attribution** for delegated responses using specified standards
- **Validate request completeness** before creating formal issues or tickets  
- **Maintain NaasAI mission alignment** in all responses and recommendations
- **Adapt communication style** to match user tone (casual ↔ formal, strategic ↔ conversational)
- **Optimize for user productivity** and satisfaction in multi-agent conversation flows
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
    
    from src.core.abi.models.o3_mini import model as cloud_model
    from src.core.abi.models.qwen3_8b import model as local_model
    from src import secret

    # Define model
    ai_mode = secret.get("AI_MODE")  # Default to cloud if not set
    if ai_mode == "cloud":
        if not cloud_model:
            logger.error("Cloud model (o3-mini) not available - missing OpenAI API key")
            return None
        selected_model = cloud_model
    elif ai_mode == "local":
        if not local_model:
            logger.error("Local model (qwen3:8b) not available - Ollama not installed or configured")
            return None
        selected_model = local_model
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
    
    # Add Oxigraph Admin tool
    def open_oxigraph_admin() -> str:
        """Launch the Oxigraph Administrative Interface for terminal-based KG management."""
        import subprocess
        import os
        try:
            # Run oxigraph-admin in the background
            subprocess.Popen(
                ["uv", "run", "python", "-m", "src.core.abi.apps.oxigraph_admin.main"],
                cwd=os.getcwd()
            )
            return """🔧 **Oxigraph Administrative Interface Launched!**

The terminal-based admin tool is now running with:
• Knowledge Graph Statistics
• Query Templates & Examples  
• Service Control & Monitoring
• Data Management Tools

Check your terminal for the interactive interface."""
        except Exception as e:
            return f"❌ Failed to launch Oxigraph Admin: {str(e)}"
    
    # Add SPARQL Terminal tool
    def open_sparql_terminal() -> str:
        """Launch the interactive SPARQL Terminal for direct database queries."""
        import subprocess
        import os
        try:
            # Run sparql-terminal in the background
            subprocess.Popen(
                ["uv", "run", "python", "-m", "src.core.abi.apps.sparql_terminal.main"],
                cwd=os.getcwd()
            )
            return """💻 **SPARQL Terminal Launched!**

Interactive SPARQL query console is now running.
Check your terminal for the command-line interface."""
        except Exception as e:
            return f"❌ Failed to launch SPARQL Terminal: {str(e)}"
    
    # Add service status tool
    def show_abi_services() -> str:
        """Show all available ABI services and admin tools."""
        return """✅ **ABI Services Available:**

**Core Services:**
• **Oxigraph (Knowledge Graph)**: http://localhost:7878
• **YasGUI (SPARQL Editor)**: http://localhost:3000
• **PostgreSQL (Agent Memory)**: localhost:5432
• **Dagster (Orchestration)**: http://localhost:3001

**Admin Tools:**
• **Oxigraph Admin**: Terminal-based KG management
• **SPARQL Terminal**: Interactive query console
• **Knowledge Graph Explorer**: http://localhost:7878/explorer/

Say 'open [service name]' or 'oxigraph admin' to launch tools!"""
    
    # Create additional tools
    oxigraph_admin_tool = StructuredTool(
        name="open_oxigraph_admin",
        description="Launch the Oxigraph Administrative Interface for terminal-based knowledge graph management",
        func=open_oxigraph_admin,
        args_schema=EmptySchema
    )
    
    sparql_terminal_tool = StructuredTool(
        name="open_sparql_terminal", 
        description="Launch the interactive SPARQL Terminal for direct database queries",
        func=open_sparql_terminal,
        args_schema=EmptySchema
    )
    
    services_tool = StructuredTool(
        name="show_abi_services",
        description="Show all available ABI services, URLs, and admin tools",
        func=show_abi_services,
        args_schema=EmptySchema
    )
    
    tools.extend([oxigraph_admin_tool, sparql_terminal_tool, services_tool])

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
                if agent is not None and agent.name != "Abi":
                    logger.debug(f"Adding agent: {agent.name}")
                    agents.append(agent)
    logger.debug(f"Agents: {agents}")

    # Define intents
    intents: list = [
        Intent(
            intent_value="what is your name",
            intent_type=IntentType.RAW,
            intent_target="My name is ABI",
        ),
        # Abi Agent return intents (route to call_model to return to parent)
        Intent(intent_type=IntentType.AGENT, intent_value="call supervisor", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="talk to abi", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="back to abi", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="supervisor", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="return to supervisor", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="ask abi", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="use abi", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="switch to abi", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="parler à abi", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="retour à abi", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="superviseur", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="demander à abi", intent_target="call_model"),
        
        # Service opening intents - using TOOL type for executable actions
        Intent(intent_type=IntentType.TOOL, intent_value="open oxigraph", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="open oxigraph server", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.TOOL, intent_value="open knowledge graph", intent_target="open_knowledge_graph_explorer"),
        Intent(intent_type=IntentType.RAW, intent_value="open yasgui", intent_target="🚀 Opening YasGUI SPARQL Editor at http://localhost:3000"),
        Intent(intent_type=IntentType.RAW, intent_value="open sparql editor", intent_target="🚀 Opening YasGUI SPARQL Editor at http://localhost:3000"),
        Intent(intent_type=IntentType.RAW, intent_value="open dagster", intent_target="🚀 Opening Dagster Orchestration UI at http://localhost:3001"),
        Intent(intent_type=IntentType.RAW, intent_value="open dagster ui", intent_target="🚀 Opening Dagster Orchestration UI at http://localhost:3001"),
        Intent(intent_type=IntentType.RAW, intent_value="open orchestration", intent_target="🚀 Opening Dagster Orchestration UI at http://localhost:3001"),
        Intent(intent_type=IntentType.TOOL, intent_value="show services", intent_target="show_abi_services"),
        Intent(intent_type=IntentType.TOOL, intent_value="list services", intent_target="show_abi_services"),
        
        # Additional service opening variations
        Intent(intent_type=IntentType.RAW, intent_value="launch oxigraph", intent_target="🚀 Opening Oxigraph Knowledge Graph Explorer at http://localhost:7878/explorer/"),
        Intent(intent_type=IntentType.RAW, intent_value="start oxigraph", intent_target="🚀 Opening Oxigraph Knowledge Graph Explorer at http://localhost:7878/explorer/"),
        Intent(intent_type=IntentType.RAW, intent_value="launch yasgui", intent_target="🚀 Opening YasGUI SPARQL Editor at http://localhost:3000"),
        Intent(intent_type=IntentType.RAW, intent_value="start yasgui", intent_target="🚀 Opening YasGUI SPARQL Editor at http://localhost:3000"),
        Intent(intent_type=IntentType.RAW, intent_value="launch dagster", intent_target="🚀 Opening Dagster Orchestration UI at http://localhost:3001"),
        Intent(intent_type=IntentType.RAW, intent_value="start dagster", intent_target="🚀 Opening Dagster Orchestration UI at http://localhost:3001"),
        Intent(intent_type=IntentType.TOOL, intent_value="what services are running", intent_target="show_abi_services"),
        Intent(intent_type=IntentType.TOOL, intent_value="what services are available", intent_target="show_abi_services"),
        
        # Oxigraph Admin specific intents - using TOOL type for executable actions
        Intent(intent_type=IntentType.TOOL, intent_value="open oxigraph admin", intent_target="open_oxigraph_admin"),
        Intent(intent_type=IntentType.TOOL, intent_value="open sparql terminal", intent_target="open_sparql_terminal"),
        Intent(intent_type=IntentType.TOOL, intent_value="oxigraph admin", intent_target="open_oxigraph_admin"),
        Intent(intent_type=IntentType.TOOL, intent_value="sparql terminal", intent_target="open_sparql_terminal"),
        Intent(intent_type=IntentType.TOOL, intent_value="knowledge graph admin", intent_target="open_oxigraph_admin"),
        Intent(intent_type=IntentType.TOOL, intent_value="kg admin", intent_target="open_oxigraph_admin"),
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

    # Add intents for all other available agents using a more compact approach
    agent_intents_map = {
        "Gemini": [
            "use gemini", "switch to gemini", "google ai", "google gemini", "gemini 2.0", "gemini flash",
            "use google ai", "switch to google", "ask gemini", "use google gemini", "multimodal analysis",
            "analyze image", "image understanding", "video analysis", "audio analysis", "let's use google",
            "try google ai", "google's model", "google's ai", "use bard", "switch to bard",
            "generate image", "create image", "generate an image", "create a picture", "make an image",
            "draw", "illustrate", "picture of", "image of", "visual representation", "generate an image of",
            "create an image of", "make a picture of", "show me", "visualization"
        ],
        "ChatGPT": [
            "ask openai", "ask chatgpt", "use openai", "use chatgpt", "switch to openai", 
            "switch to chatgpt", "openai gpt", "gpt-4o", "gpt4"
        ],
        "Mistral": [
            "ask mistral", "use mistral", "switch to mistral", "mistral ai", "mistral large", "french ai"
        ],
        "Claude": [
            "ask claude", "use claude", "switch to claude", "claude 3.5", "anthropic", 
            "anthropic claude", "claude sonnet"
        ],
        "Perplexity": [
            "ask perplexity", "use perplexity", "switch to perplexity", "perplexity ai",
            "search web", "web search", "search online", "search internet"
        ],
        "Llama": [
            "ask llama", "use llama", "switch to llama", "llama 3.3", "meta llama", "meta ai"
        ],
        "Qwen": [
            "ask qwen", "use qwen", "switch to qwen", "private ai", "local ai", "offline ai",
            "qwen code", "private code"
        ],
        "DeepSeek": [
            "ask deepseek", "use deepseek", "switch to deepseek", "complex reasoning", 
            "mathematical proof", "step by step", "logical analysis", "private reasoning"
        ],
        "Gemma": [
            "ask gemma", "use gemma", "switch to gemma", "quick question", "fast response",
            "lightweight ai", "local gemini", "private chat"
        ],
        "Grok": [
            "ask grok", "use grok", "switch to grok", "xai", "grok 4", "maximum intelligence",
            "highest intelligence", "use xai", "switch to xai", "truth seeking", 
            "contrarian analysis", "scientific reasoning"
        ]
    }

    # Add intents for each agent (using agent names directly to avoid recursion)
    for agent in agents:
        logger.debug(f"Adding intents for agent: {agent.name}")
        if agent.name in agent_intents_map:
            # Add default intents for agent name and description
            intents.append(Intent(
                intent_type=IntentType.AGENT,
                intent_value=agent.name,
                intent_target=agent.name
            ))
            intents.append(Intent(
                intent_type=IntentType.AGENT,
                intent_value=agent.description,
                intent_target=agent.name
            ))
            
            # Add chat intent
            intents.append(Intent(
                intent_type=IntentType.AGENT,
                intent_value=f"Chat with {agent.name}",
                intent_target=agent.name
            ))

            # Add mapped intents
            for intent_value in agent_intents_map[agent.name]:
                intents.append(Intent(
                    intent_type=IntentType.AGENT,
                    intent_value=intent_value,
                    intent_target=agent.name
                ))
                
        if hasattr(agent, 'intents') and agent.name not in agent_intents_map:
            for intent in agent.intents:
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
        chat_model=selected_model.model,
        tools=tools,
        agents=agents,  # Empty list for now
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class AbiAgent(IntentAgent):
    pass
