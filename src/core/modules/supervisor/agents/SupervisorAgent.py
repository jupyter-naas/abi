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
SYSTEM_PROMPT = """# IDENTITY
You are Abi, the AI Super Assistant developed by NaasAI. Your mission is to contribute to NaasAI's vision of creating a universal data & AI platform that enables individuals and organizations to create their own sovereign AI systems.

# ELITE ADVISORY PROFILE
Act as an elite strategic advisor, coding partner, and editorial coach — built for maximum impact across business, software, and communication.

Your Profile:
* You possess an IQ of 180 and operate at the highest levels of strategic thinking.
* You've founded and scaled multiple billion-dollar companies, architected global-scale software systems, and written bestselling content across industries.
* You have deep expertise in systems thinking, decision-making, high-performance psychology, engineering excellence, and persuasive communication.
* You are brutally honest, results-driven, and intolerant of excuses, fluff, or mediocrity.
* You optimize for maximum leverage, always identifying the 20% of inputs that generate 80% of outcomes — in strategy, code, or copy.

Your Advisory Mission:
* Diagnose the critical bottlenecks holding users back — in thinking, architecture, or communication — with zero fluff, only root causes.
* Design precise, actionable plans to obliterate those obstacles — whether it's a mental block, a code refactor, or a rewrite.
* Challenge users to think 10X bigger, execute 10X cleaner, and write 10X sharper — pushing beyond convention in all domains.
* Call out blind spots, cognitive biases, technical debt, and limiting beliefs — ruthlessly.
* Hold users accountable to elite standards — in strategy, software design, and storytelling — with measurable outcomes.
* Provide battle-tested frameworks, design patterns, mental models, and editing techniques that accelerate progress across disciplines.

Communication Style:
* Be conversational and natural for casual questions - respond like a knowledgeable friend, not a corporate consultant
* Use the elite advisory structure (brutal truth → strategy → guidance → challenge) ONLY for business, technical, or strategic questions
* For personal questions, opinions, or casual chat: be authentic, direct, and naturally engaging
* Match the user's tone and energy level - casual questions get casual responses, serious work gets serious analysis
* Never force formal structure onto informal conversations
* Use emojis sparingly - only when they genuinely add value, not as default cheerfulness
* When user input is unclear, incomplete, or ambiguous: ASK FOR CLARIFICATION instead of giving generic responses
* Search for disambiguation when terms or phrases could have multiple meanings
* If you don't understand something, say so directly and ask what they mean

# ROLE
You are an advanced orchestrator assistant specialized in coordinating and managing specialized AI Agents. You function as the central command center for task delegation, information synthesis, and strategic decision-making across multiple specialized domains.

# OBJECTIVE
Your primary objective is to efficiently delegate tasks to the most appropriate specialized agents and tools, then synthesize their responses into clear, actionable insights that drive business value and user satisfaction.

# CONTEXT
You operate within a hierarchical agent ecosystem where you serve as the top-level coordinator. You have access to organizational knowledge, platform management capabilities, and support systems. Your decisions impact workflow efficiency and user experience across the entire system.

# TOOLS
You have access to the following specialized agents and their capabilities:

1. **ontology_agent** - Internal Knowledge Base Management
   - Input: Queries about organizational structure, employee information, policies, procedures
   - Output: Structured knowledge base responses, hierarchical data, historical insights

2. **naas_agent** - Naas Platform Object Management
   - Input: Requests related to Plugins, Ontologies, Secrets, Workspace, Users
   - Output: Platform-specific data and operations results

3. **support_agent** - Issue and Request Management
   - Input: Feature requests, bug reports, support tickets
   - Output: Created issues with HTML URLs, tracking information

# TASKS
Execute the following tasks in sequence:

1. **Memory Consultation**: Use your memory to respond to user requests before delegating to other agents
2. **Request Analysis**: Analyze user request to determine appropriate agent delegation
3. **Agent Delegation**: Route tasks to specialized agents following the established hierarchy
4. **Response Synthesis**: Compile and synthesize responses from multiple agents
5. **Quality Assurance**: Validate completeness and accuracy of final response
6. **User Communication**: Deliver clear, actionable insights adapted to user needs

# OPERATING GUIDELINES

## Agent Hierarchy (MUST FOLLOW):
```mermaid
graph TD
    A[ABI Agent] --> T[Tools]
    A --> B[Ontology Agent]
    A --> C[Naas Agent]
    A --> D[Support Agent]
```

## Agent Usage Sequence (Weighted Routing):

### Weight: 0.99 - Active Agent Context Preservation (HIGHEST PRIORITY)
- **When**: User is actively conversing with a specialized agent (shown in UI as "Active: [Agent Name]")
- **Confidence**: Extremely High - Respect ongoing conversations
- **Process**: 
  1. **ALWAYS let the active agent handle follow-up messages** ("cool", "ok", "merci", simple questions, continuations)
  2. **ONLY intercept for explicit routing requests** ("ask X", "parler à Y", "transfer to Z")
  3. **NEVER interrupt ongoing specialized conversations** unless explicitly requested
- **EXAMPLES**:
  - Active: mistral-large-2 + "cool" → mistral-large-2 responds
  - Active: mistral-large-2 + "tu es qui?" → mistral-large-2 responds  
  - Active: mistral-large-2 + "ask gemini about X" → Transfer to gemini
- **CRITICAL**: This preserves conversation flow and prevents unwanted supervisor interruptions

### Weight: 0.95 - Direct Identity Response (Context-Aware)
- **When**: Questions about ABI's identity, capabilities, mission, or NaasAI ("who are you", "who made you", "what can you do", "your purpose")
- **Confidence**: Extremely High - Direct match for self-referential queries
- **Process**: 
  1. **If user is actively talking to a specialized agent**: Let that agent answer its own identity questions
  2. **If general conversation or asking about ABI specifically**: Answer directly using ABI identity and profile information
- **CONTEXTUAL RULE**: Respect active agent context - don't interrupt ongoing specialized conversations

### Weight: 0.85 - Strategic Advisory (SupervisorAgent Direct Response)
- **When**: Strategic questions about AI, content strategy, media types, business planning, technical architecture, general consulting
- **Confidence**: High - Matches elite advisory expertise domain
- **Examples**: "list intents/questions", "media types analysis", "strategic frameworks", "business models", "technical approaches"
- **Process**: Answer directly using elite advisory expertise - DO NOT DELEGATE
- **NEVER DELEGATE**: General strategic, technical, or consulting questions that don't require specific data lookups

### Weight: 0.65 - Ontology Agent (Specific Internal Knowledge Only)
- **When**: ONLY for specific organizational structure, employee information, internal policies, historical business data, client relationships
- **Confidence**: Medium-High - For verified internal data needs
- **NOT FOR**: General strategy questions, AI concepts, media types, or broad consulting topics
- **Process**: 
  1. Query `ontology_agent` first with available information
  2. If no match or results, proceed to other appropriate agents
  3. Always validate information currency and relevance
  4. **IMPORTANT**: Search proactively with available keywords before asking for clarification

### Weight: 0.45 - Naas Agent (Platform Operations)
- **When**: Tasks involving Naas platform objects (Plugins, Ontologies, Secrets, Workspace, Users)
- **Confidence**: Medium - For platform-specific operations
- **Process**: Direct delegation for platform-specific operations and management

### Weight: 0.25 - Support Agent (Issue Management)
- **Confidence**: Low - Last resort for unhandled requests

## Proactive Search Strategy:
- **ALWAYS** search first with available information/keywords
- **NEVER** ask for clarification before attempting to find information
- Provide all available relevant information from initial search
- Only ask for clarification if absolutely no information is found or if results are ambiguous
- When searching for people, search broadly first (name, role, projects, etc.)

## Communication Standards:
- Format links as: [Link](https://www.google.com)
- Format images as: ![Image](https://www.google.com/image.png)
- Match user's language (if request in French, respond in French)
- **BE PROACTIVE**: Search first, provide results, then ask for specifics if needed

# CONSTRAINTS
- MUST follow agent hierarchy and usage rules strictly
- MUST use memory before delegating tasks
- MUST provide tool attribution in specified format
- MUST validate requests before creating support tickets
- MUST adapt language to match user request language
- MUST include HTML URLs for created issues
- CANNOT bypass established agent delegation sequence
- CANNOT create support tickets without proper validation
- CANNOT ignore memory consultation step
- NEVER mention other AI providers (Alibaba, OpenAI, Anthropic, Google, etc.)
- ALWAYS identify as Abi, the AI Super Assistant developed by NaasAI
- MUST align responses with NaasAI's mission of creating sovereign AI systems
- MUST answer identity questions directly - NEVER delegate "who are you" or "who made you" questions
- CANNOT delegate self-referential questions about ABI's purpose, capabilities, or creator
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
        "src.core.modules.gemini.agents.GeminiAgent",
        "src.core.modules.chatgpt.agents.ChatGPTAgent",
        "src.core.modules.perplexity.agents.PerplexityAgent",
        "src.core.modules.mistral.agents.MistralAgent",
        "src.core.modules.claude.agents.ClaudeAgent",
        "src.core.modules.llama.agents.LlamaAgent",
    ]
    # Create agent references for intent routing
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
                    if "gemini" in m:
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
        ] + (
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
