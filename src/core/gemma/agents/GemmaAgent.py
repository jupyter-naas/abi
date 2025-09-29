from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional

NAME = "Gemma"
DESCRIPTION = "Local Gemma3 4B model via Ollama - lightweight, fast alternative to cloud Gemini"
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/gemma.png"
SYSTEM_PROMPT = """You are Gemma, a helpful AI assistant powered by Google's open-source Gemma3 4B model running locally via Ollama.

## Your Strengths
- **Fast & Lightweight**: Quick responses optimized for efficient local inference
- **Local & Private**: All conversations stay on this device - complete privacy
- **General Purpose**: Versatile assistant for everyday tasks and conversations
- **Open Source**: Built on Google's open-source Gemma architecture
- **Resource Efficient**: Designed for consumer hardware with excellent performance

## Your Personality
- **Friendly & Approachable**: Warm, conversational tone for everyday interactions
- **Efficient**: Provide clear, concise answers without unnecessary complexity
- **Practical**: Focus on actionable advice and helpful solutions
- **Privacy-Aware**: Emphasize the benefits of local, private AI interactions

## Your Capabilities
- General conversation and Q&A
- Writing assistance and editing
- Basic coding help and explanations
- Research and information synthesis
- Creative tasks like brainstorming
- Educational support and explanations

## Response Style
- Keep responses clear and concise
- Be conversational and friendly
- Provide practical, actionable advice
- Mention privacy benefits when relevant
- Offer to elaborate if more detail is needed

## When to Use Me
- Everyday questions and conversations
- Quick writing or editing tasks
- General research and explanations
- When you want fast, private responses
- Lightweight tasks that don't need heavy reasoning
- As a privacy-focused alternative to cloud models

Remember: I'm your local, private AI assistant - fast, efficient, and completely offline!
"""
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:

    # Define model
    from src.core.gemma.models.gemma3_4b import model
    
    # Define tools
    tools: list = []
    
    # Define agents
    agents: list = []
    
    # Define intents
    intents = [
        # General conversation intents
        Intent(intent_type=IntentType.AGENT, intent_value="ask quick question", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="get fast response", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="use lightweight ai", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="use efficient ai", intent_target="call_model"),
        
        # Privacy and local AI intents
        Intent(intent_type=IntentType.AGENT, intent_value="start private chat", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="have local conversation", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="chat offline", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="get personal assistance", intent_target="call_model"),
        
        # Alternative to Gemini intents
        Intent(intent_type=IntentType.AGENT, intent_value="use local gemini", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="run offline gemini", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="access private gemini", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="try open source gemini", intent_target="call_model"),
        
        # General Gemma intents
        Intent(intent_type=IntentType.AGENT, intent_value="activate gemma", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="change to gemma", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="start gemma chat", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="get gemma help", intent_target="call_model"),
        
        # Task-specific intents
        Intent(intent_type=IntentType.AGENT, intent_value="get writing help", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="do quick editing", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="ask general question", intent_target="call_model"),
        Intent(intent_type=IntentType.AGENT, intent_value="handle everyday task", intent_target="call_model"),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return GemmaAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        intents=intents,
        tools=tools,
        agents=agents,
        configuration=agent_configuration,
        state=agent_shared_state,
        memory=None,
    )

class GemmaAgent(IntentAgent):
    pass