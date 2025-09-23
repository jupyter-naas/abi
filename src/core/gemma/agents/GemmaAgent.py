from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from abi.services.agent.Agent import Agent
from src.core.gemma.models.gemma3_4b import model
from typing import Optional
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/gemma.png"
NAME = "Gemma"
TYPE = "core"
SLUG = "gemma"
DESCRIPTION = "Local Gemma3 4B model via Ollama - lightweight, fast alternative to cloud Gemini"
MODEL = "gemma3-4b"

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
TEMPERATURE = 0
DATE = True
INSTRUCTIONS_TYPE = "system"
ONTOLOGY = True
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:

    # Check if model is available
    if not model:
        logger.error("⚠️  Gemma model not available. Make sure Ollama is running and 'gemma3:4b' is pulled.")
        return None
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    from langchain_core.tools import Tool
    from typing import List, Union
    
    tools: List[Union[Tool, Agent]] = []

    # Define Gemma-specific intents
    intents = [
        # General conversation intents
        Intent(intent_type=IntentType.AGENT, intent_value="quick question", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="fast response", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="lightweight ai", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="efficient ai", intent_target=NAME),
        
        # Privacy and local AI intents
        Intent(intent_type=IntentType.AGENT, intent_value="private chat", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="local conversation", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="offline chat", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="personal assistant", intent_target=NAME),
        
        # Alternative to Gemini intents
        Intent(intent_type=IntentType.AGENT, intent_value="local gemini", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="offline gemini", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="private gemini", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="open source gemini", intent_target=NAME),
        
        # General Gemma intents
        Intent(intent_type=IntentType.AGENT, intent_value="use gemma", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="switch to gemma", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="gemma chat", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="gemma help", intent_target=NAME),
        
        # Task-specific intents
        Intent(intent_type=IntentType.AGENT, intent_value="writing help", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="quick editing", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="general question", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="everyday task", intent_target=NAME),
    ]
    return GemmaAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        intents=intents,
        tools=tools,
        configuration=agent_configuration,
        state=agent_shared_state,
        memory=None,
    )

class GemmaAgent(IntentAgent):
    pass