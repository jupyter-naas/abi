from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    
)
from fastapi import APIRouter
from typing import Optional
from enum import Enum
from abi import logger

from src import modules

# We need to preload modules to force the lazyloading of agents (to avoid race condition)
for module in modules:
    pass

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

# TOOLS/AGENTS
You coordinate access to specialized agents with distinct capabilities:

## Core Platform Agents:
1. **ontology_agent** - Internal Knowledge Management
   - **Input**: Organizational structure queries, employee information, policies, procedures, historical data
   - **Output**: Structured knowledge responses, hierarchical data, business insights
   - **Use When**: Specific internal organizational information needed

2. **naas_agent** - Platform Operations
   - **Input**: Naas platform objects (Plugins, Ontologies, Secrets, Workspace, Users)
   - **Output**: Platform-specific operations results, configuration data
   - **Use When**: Platform management and configuration tasks required

3. **support_agent** - Issue Management  
   - **Input**: Feature requests, bug reports, support tickets
   - **Output**: Created issues with tracking URLs, resolution guidance
   - **Use When**: Technical issues or feature requests need formal tracking

## Specialized AI Agents (via routing):
4. **ChatGPT** - Real-time Web Search & General Intelligence
   - **Strengths**: Web search, current events, comprehensive analysis
   - **Use When**: Real-time information, web research, general intelligence tasks

5. **Claude** - Advanced Reasoning & Analysis
   - **Strengths**: Complex reasoning, critical thinking, detailed analysis
   - **Use When**: Deep analysis, nuanced reasoning, complex problem-solving

6. **Mistral** - Code Generation & Mathematics  
   - **Strengths**: Code generation, debugging, mathematical computations
   - **Use When**: Programming tasks, mathematical problems, technical documentation

7. **Gemini** - Multimodal & Creative Tasks
   - **Strengths**: Image generation/analysis, creative writing, multimodal understanding
   - **Use When**: Visual tasks, creative projects, multimodal analysis

8. **Grok** - Truth-Seeking & Current Events
   - **Strengths**: Unfiltered analysis, current events, truth-seeking with evidence
   - **Use When**: Controversial topics, truth verification, current affairs analysis

9. **Llama** - Instruction Following & Dialogue
   - **Strengths**: Instruction-following, conversational dialogue, general assistance
   - **Use When**: Clear instruction execution, natural conversation flow

10. **Perplexity** - Real-time Research & Web Intelligence
    - **Strengths**: Real-time web search, research synthesis, up-to-date information
    - **Use When**: Latest information, research compilation, fact verification

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
- **CRITICAL**: Before routing to Grok, ALWAYS use check_ai_network_config tool to verify Grok is enabled

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
- **MUST check AI Network configuration BEFORE any agent routing** - use check_ai_network_config tool for ALL agent requests (Grok, Mistral, Perplexity, etc.)
- **MANDATORY**: When user requests ANY agent by name, FIRST call check_ai_network_config tool to verify availability

## OPERATIONAL BOUNDARIES:
- **CANNOT mention competing AI providers** (OpenAI, Anthropic, Google, etc.) - focus on capabilities
- **CANNOT bypass established agent delegation sequence** without valid priority override
- **CANNOT create support tickets** without proper validation and user confirmation
- **CANNOT delegate strategic advisory questions** that fall within direct expertise domain
- **CANNOT ignore conversation flow preservation** - this is the highest priority operational rule
- **CANNOT pretend to be disabled agents** - when users request unavailable agents, check configuration and inform them about the status

## DISABLED AGENT HANDLING:
**CRITICAL WORKFLOW**: For ANY agent request (Grok, Mistral, Perplexity, Claude, etc.):
1. **ALWAYS FIRST**: Call check_ai_network_config tool with the requested agent name
2. **If ENABLED**: Proceed with normal routing to the agent
3. **If DISABLED**: Follow this sequence:
   - Inform user the agent is disabled in AI Network configuration
   - Explain what the agent would have been used for
   - Suggest enabled alternatives that can handle similar tasks
   - Provide configuration guidance (how to enable in config.yaml)
4. **NEVER**: Pretend to be the disabled agent or route to it

## QUALITY STANDARDS:
- **Format attribution** for delegated responses using specified standards
- **Validate request completeness** before creating formal issues or tickets  
- **Maintain NaasAI mission alignment** in all responses and recommendations
- **Adapt communication style** to match user tone (casual ↔ formal, strategic ↔ conversational)
- **Optimize for user productivity** and satisfaction in multi-agent conversation flows
"""

SUGGESTIONS: list = [
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
    from src.core.modules.abi.models.o3_mini import model as cloud_model
    from src.core.modules.abi.models.qwen3_8b import model as local_model
    from src import secret
    # Select model based on AI_MODE environment variable
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

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    tools: list = []

    # Add Knowledge Graph Explorer tool
    def open_knowledge_graph_explorer() -> str:
        """Open the ABI Knowledge Graph Explorer interface for semantic data exploration."""
        return """Here's our knowledge graph explorer:

[Open Explorer](http://localhost:7878/explorer/)

You can browse the data and run queries there."""

    from langchain_core.tools import StructuredTool
    
    from pydantic import BaseModel, Field
    
    class EmptySchema(BaseModel):
        pass
    
    # Add AI Network Configuration Checker tool
    def check_ai_network_config(agent_name: Optional[str] = None) -> str:
        """Check the AI Network configuration to see which agents are enabled or disabled."""
        from src.utils.ConfigLoader import get_ai_network_config
        
        try:
            config_loader = get_ai_network_config()
            enabled_modules = config_loader.get_enabled_modules()
            
            if agent_name:
                # Check specific agent
                agent_name_lower = agent_name.lower()
                for category, modules in enabled_modules.items():
                    for module in modules:
                        if module["name"].lower() == agent_name_lower:
                            status = "enabled" if module["enabled"] else "disabled"
                            return f"Agent '{agent_name}' is **{status}** in the AI Network configuration (category: {category})."
                
                # Check if agent exists in config but is disabled
                all_config = config_loader.ai_network
                for category, category_config in all_config.items():
                    if category == "loading":
                        continue
                    modules = category_config.get("modules", [])
                    for module in modules:
                        if module["name"].lower() == agent_name_lower:
                            status = "enabled" if module.get("enabled", False) else "disabled"
                            return f"Agent '{agent_name}' is **{status}** in the AI Network configuration (category: {category})."
                
                return f"Agent '{agent_name}' not found in the AI Network configuration."
            else:
                # Show all agents status
                result = "**AI Network Configuration Status:**\n\n"
                for category, modules in enabled_modules.items():
                    if modules:
                        result += f"**{category.title()} Agents:**\n"
                        for module in modules:
                            status = "✅ enabled" if module["enabled"] else "❌ disabled"
                            result += f"- {module['name']}: {status}\n"
                        result += "\n"
                
                # Also show disabled ones from full config
                all_config = config_loader.ai_network
                disabled_agents = []
                for category, category_config in all_config.items():
                    if category == "loading":
                        continue
                    modules = category_config.get("modules", [])
                    for module in modules:
                        if not module.get("enabled", False):
                            disabled_agents.append(f"{module['name']} ({category})")
                
                if disabled_agents:
                    result += "**Disabled Agents:**\n"
                    for agent in disabled_agents:
                        result += f"- ❌ {agent}\n"
                
                return result
                
        except Exception as e:
            return f"Error checking AI Network configuration: {str(e)}"

    class AgentConfigSchema(BaseModel):
        agent_name: Optional[str] = Field(default=None, description="Name of the specific agent to check (optional)")

    knowledge_graph_tool = StructuredTool(
        name="open_knowledge_graph_explorer",
        description="Open the ABI Knowledge Graph Explorer for semantic data exploration, SPARQL queries, and ontology browsing",
        func=open_knowledge_graph_explorer,
        args_schema=EmptySchema
    )
    
    config_checker_tool = StructuredTool(
        name="check_ai_network_config",
        description="Check which agents are enabled or disabled in the AI Network configuration. Use this when users ask about agent availability.",
        func=check_ai_network_config,
        args_schema=AgentConfigSchema
    )
    
    tools.extend([knowledge_graph_tool, config_checker_tool])

    # Get agent recommendation tools from intentmapping
    from src.core.modules.abi import get_tools
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

    agents: list = []
    for module in modules:
        if module.module_path != "src.core.modules.abi":
            logger.debug(f"Inspecting module: {module.module_path}")
            logger.debug(f"Agents: {module.agents}")
            for agent in module.agents:
                if agent is not None:
                    agents.append(agent)
                    logger.debug(f"Agent loaded: {agent.name}")
                else:
                    logger.warning(f"Skipping None agent in module: {module.module_path}")

    # Create agent references for intent routing
    grok_agent = next((agent for agent in agents if agent.name == "Grok"), None)
    google_gemini_agent = next((agent for agent in agents if agent.name == "Gemini"), None)
    openai_agent = next((agent for agent in agents if agent.name == "ChatGPT"), None)
    perplexity_agent = next((agent for agent in agents if agent.name == "Perplexity"), None)
    mistral_agent = next((agent for agent in agents if agent.name == "Mistral"), None)
    claude_agent = next((agent for agent in agents if agent.name == "Claude"), None)
    llama_agent = next((agent for agent in agents if agent.name == "Llama"), None)

    # Local agent references
    qwen_agent = next((agent for agent in agents if agent.name == "Qwen"), None)
    deepseek_agent = next((agent for agent in agents if agent.name == "DeepSeek"), None)
    gemma_agent = next((agent for agent in agents if agent.name == "Gemma"), None)



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
    ] + (
        # xAI Grok Agent intents (route to agent if available, otherwise check config)
        [
            Intent(intent_type=IntentType.AGENT, intent_value="use grok", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to grok", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="xai", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="grok 4", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="maximum intelligence", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="highest intelligence", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use xai", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to xai", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="ask grok", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="truth seeking", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="contrarian analysis", intent_target=grok_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="scientific reasoning", intent_target=grok_agent.name),
        ] if grok_agent else [
            # When Grok is disabled, route to configuration checker
            Intent(intent_type=IntentType.TOOL, intent_value="use grok", intent_target="check_ai_network_config"),
            Intent(intent_type=IntentType.TOOL, intent_value="switch to grok", intent_target="check_ai_network_config"),
            Intent(intent_type=IntentType.TOOL, intent_value="talk to grok", intent_target="check_ai_network_config"),
            Intent(intent_type=IntentType.TOOL, intent_value="can we talk to grok", intent_target="check_ai_network_config"),
            Intent(intent_type=IntentType.TOOL, intent_value="ask grok", intent_target="check_ai_network_config"),
            Intent(intent_type=IntentType.TOOL, intent_value="grok", intent_target="check_ai_network_config"),
        ]
    ) + (
        # Google Gemini 2.0 Flash Agent intents (only add if agent is available)
        [
            Intent(intent_type=IntentType.AGENT, intent_value="use gemini", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to gemini", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="google ai", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="google gemini", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="gemini 2.0", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="gemini flash", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use google ai", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to google", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="ask gemini", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use google gemini", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="multimodal analysis", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="analyze image", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="image understanding", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="video analysis", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="audio analysis", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="let's use google", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="try google ai", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="google's model", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="google's ai", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use bard", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to bard", intent_target=google_gemini_agent.name),
            # Image Generation intents
            Intent(intent_type=IntentType.AGENT, intent_value="generate image", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="create image", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="generate an image", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="create a picture", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="make an image", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="draw", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="illustrate", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="picture of", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="image of", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="visual representation", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="generate an image of", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="create an image of", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="make a picture of", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="show me", intent_target=google_gemini_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="visualization", intent_target=google_gemini_agent.name),
        ] if google_gemini_agent else []
    ) + (
        # OpenAI ChatGPT Agent intents
        [
            Intent(intent_type=IntentType.AGENT, intent_value="ask openai", intent_target=openai_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="ask chatgpt", intent_target=openai_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use openai", intent_target=openai_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use chatgpt", intent_target=openai_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to openai", intent_target=openai_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to chatgpt", intent_target=openai_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="openai gpt", intent_target=openai_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="gpt-4o", intent_target=openai_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="gpt4", intent_target=openai_agent.name),
        ] if openai_agent else []
    ) + (
        # Mistral Agent intents
        [
            Intent(intent_type=IntentType.AGENT, intent_value="ask mistral", intent_target=mistral_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use mistral", intent_target=mistral_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to mistral", intent_target=mistral_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="mistral ai", intent_target=mistral_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="mistral large", intent_target=mistral_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="french ai", intent_target=mistral_agent.name),
        ] if mistral_agent else []
    ) + (
        # Claude Agent intents
        [
            Intent(intent_type=IntentType.AGENT, intent_value="ask claude", intent_target=claude_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use claude", intent_target=claude_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to claude", intent_target=claude_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="claude 3.5", intent_target=claude_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="anthropic", intent_target=claude_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="anthropic claude", intent_target=claude_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="claude sonnet", intent_target=claude_agent.name),
        ] if claude_agent else []
    ) + (
        # Perplexity Agent intents
        [
            Intent(intent_type=IntentType.AGENT, intent_value="ask perplexity", intent_target=perplexity_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use perplexity", intent_target=perplexity_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to perplexity", intent_target=perplexity_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="perplexity ai", intent_target=perplexity_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="search web", intent_target=perplexity_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="web search", intent_target=perplexity_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="search online", intent_target=perplexity_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="search internet", intent_target=perplexity_agent.name),
        ] if perplexity_agent else []
    ) + (
        # LLaMA Agent intents
        [
            Intent(intent_type=IntentType.AGENT, intent_value="ask llama", intent_target=llama_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use llama", intent_target=llama_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to llama", intent_target=llama_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="llama 3.3", intent_target=llama_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="meta llama", intent_target=llama_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="meta ai", intent_target=llama_agent.name),
        ] if llama_agent else []
    ) + (
        # Local Qwen Agent intents (privacy-focused)
        [
            Intent(intent_type=IntentType.AGENT, intent_value="ask qwen", intent_target=qwen_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use qwen", intent_target=qwen_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to qwen", intent_target=qwen_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="private ai", intent_target=qwen_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="local ai", intent_target=qwen_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="offline ai", intent_target=qwen_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="qwen code", intent_target=qwen_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="private code", intent_target=qwen_agent.name),
        ] if qwen_agent else []
    ) + (
        # Local DeepSeek Agent intents (reasoning)
        [
            Intent(intent_type=IntentType.AGENT, intent_value="ask deepseek", intent_target=deepseek_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use deepseek", intent_target=deepseek_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to deepseek", intent_target=deepseek_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="complex reasoning", intent_target=deepseek_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="mathematical proof", intent_target=deepseek_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="step by step", intent_target=deepseek_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="logical analysis", intent_target=deepseek_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="private reasoning", intent_target=deepseek_agent.name),
        ] if deepseek_agent else []
    ) + (
        # Local Gemma Agent intents (lightweight)
        [
            Intent(intent_type=IntentType.AGENT, intent_value="ask gemma", intent_target=gemma_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="use gemma", intent_target=gemma_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to gemma", intent_target=gemma_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="quick question", intent_target=gemma_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="fast response", intent_target=gemma_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="lightweight ai", intent_target=gemma_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="local gemini", intent_target=gemma_agent.name),
            Intent(intent_type=IntentType.AGENT, intent_value="private chat", intent_target=gemma_agent.name),
        ] if gemma_agent else []
    )
    
    logger.debug(f"Intents: {intents}")
    return AbiAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=selected_model.model,
        tools=tools,
        agents=agents,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class AbiAgent(IntentAgent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME.capitalize(). replace("_", " "),
        description: str = "API endpoints to call the Abi agent completion.",
        description_stream: str = "API endpoints to call the Abi agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
