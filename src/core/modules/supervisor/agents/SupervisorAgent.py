from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from langchain_openai import ChatOpenAI
from src import secret
from typing import Optional, Union
from enum import Enum
from pydantic import SecretStr
import importlib
import os

NAME = "Supervisor"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
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

### Advanced Reasoning (Weight: 0.75)
- **Route to Claude**: Complex analysis, critical thinking, nuanced reasoning  
- **Patterns**: "analyze deeply", "critical evaluation", "complex reasoning"

### Code & Mathematics (Weight: 0.70)
- **Route to Mistral**: Programming, debugging, mathematical computations
- **Patterns**: "code help", "debug", "mathematical", "programming"

### Internal Knowledge (Weight: 0.65)
- **Route to ontology_agent**: Organizational structure, internal policies, employee data
- **Patterns**: Specific company/internal information requests

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

SUGGESTIONS = [
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
    # Init
    tools: list = []
    agents: list = []

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Add support agents and LLM agents
    modules = [
        "src.core.modules.support.agents.SupportAgent",
        "src.core.modules.ontology.agents.OntologyAgent", 
        "src.core.modules.naas.agents.NaasAgent",
        # LLM Agents
        "src.core.modules.grok.agents.GrokAgent",
        "src.core.modules.gemini.agents.GeminiAgent",
        "src.core.modules.chatgpt.agents.ChatGPTAgent",
        "src.core.modules.perplexity.agents.PerplexityAgent",
        "src.core.modules.mistral.agents.MistralAgent",
        "src.core.modules.claude.agents.ClaudeAgent",
        "src.core.modules.llama.agents.LlamaAgent",
    ]
    # Create agent references for intent routing
    grok_agent = None
    google_gemini_agent = None
    openai_agent = None
    perplexity_agent = None
    mistral_agent = None
    claude_agent = None
    llama_agent = None
    for m in modules:
        try:
            module = importlib.import_module(m)
            agent = module.create_agent()
            # Only add valid agents (not None) and validate they have agent-like attributes
            if agent is not None:
                # Check if it has basic agent attributes instead of strict isinstance
                if hasattr(agent, 'name') and hasattr(agent, 'description') and hasattr(agent, 'chat_model'):
                    agents.append(agent)
                    # Store agent references for intents
                    if "grok" in m:
                        grok_agent = agent
                    elif "gemini" in m:
                        google_gemini_agent = agent
                    elif "chatgpt" in m:
                        openai_agent = agent
                    elif "perplexity" in m:
                        perplexity_agent = agent
                    elif "mistral" in m:
                        mistral_agent = agent
                    elif "claude" in m:
                        claude_agent = agent
                    elif "llama" in m:
                        llama_agent = agent
                    print(f"✅ Agent loaded: {agent.name}")
                else:
                    print(f"⚠️  Agent from {m} missing required attributes: {type(agent)}")
        except ImportError:
            pass
        except Exception as e:
            print(f"⚠️  Error loading agent from {m}: {e}")

        # Set model
    model: Union[ChatOpenAI, "ChatOllama"]
    ai_mode = os.getenv("AI_MODE", "cloud")  # Default to cloud if not set
    if ai_mode == "cloud":
        model = ChatOpenAI(
            model=MODEL, 
            temperature=TEMPERATURE, 
            api_key=SecretStr(secret.get("OPENAI_API_KEY"))
        )
    elif ai_mode == "local":
        from langchain_ollama import ChatOllama
        model = ChatOllama(model="qwen3:8b", temperature=0.7)
    else:
        raise ValueError("AI_MODE must be either 'cloud' or 'local'")

    # Use all loaded agents - the SupervisorAgent will handle validation internally
    return SupervisorAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        intents=[
            Intent(
                intent_value="what is your name",
                intent_type=IntentType.RAW,
                intent_target="My name is ABI",
            ),
            # Supervisor Agent return intents  
            Intent(intent_type=IntentType.AGENT, intent_value="call supervisor", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="talk to abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="back to abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="supervisor", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="return to supervisor", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="ask abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="use abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="switch to abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="parler à abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="retour à abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="superviseur", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="demander à abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="can i talk back to abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="go back to abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="return to abi", intent_target="Supervisor"),
            Intent(intent_type=IntentType.AGENT, intent_value="back to supervisor", intent_target="Supervisor"),
        ] + (
            # xAI Grok Agent intents (only add if agent is available)
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
            ] if grok_agent else []
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
        ),
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class SupervisorAgent(IntentAgent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME.capitalize(). replace("_", " "),
        description: str = "API endpoints to call the Supervisor agent completion.",
        description_stream: str = "API endpoints to call the Supervisor agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )

    def hello(self) -> str:
        return "Abi: Hello, World!"
