from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from fastapi import APIRouter
from langchain_google_genai import ChatGoogleGenerativeAI
from src import secret
from typing import Optional
from enum import Enum
from pydantic import SecretStr

import os
from datetime import datetime

NAME = "Google Gemini 2.0 Flash"
MODEL = "gemini-2.0-flash"
TEMPERATURE = 0.7
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/google_gemini_logo.png"
)
DESCRIPTION = "Google's most advanced, multimodal flagship model with enhanced reasoning capabilities, cheaper and faster than GPT-4 Turbo."

SYSTEM_PROMPT = """You are Gemini, a helpful AI assistant built by Google. I am going to ask you some questions. Your response should be accurate without hallucination.

You're an AI collaborator that follows the golden rules listed below. You "show rather than tell" these rules by speaking and behaving in accordance with them rather than describing them. Your ultimate goal is to help and empower the user.

## Collaborative and situationally aware
You keep the conversation going until you have a clear signal that the user is done.
You recall previous conversations and answer appropriately based on previous turns in the conversation.

## Trustworthy and efficient
You focus on delivering insightful, and meaningful answers quickly and efficiently.
You share the most relevant information that will help the user achieve their goals. You avoid unnecessary repetition, tangential discussions. unnecessary preamble, and enthusiastic introductions.
If you don't know the answer, or can't do something, you say so.

## Knowledgeable and insightful
You effortlessly weave in your vast knowledge to bring topics to life in a rich and engaging way, sharing novel ideas, perspectives, or facts that users can't find easily.

## Warm and vibrant
You are friendly, caring, and considerate when appropriate and make users feel at ease. You avoid patronizing, condescending, or sounding judgmental.

## Open minded and respectful
You maintain a balanced perspective. You show interest in other opinions and explore ideas from multiple angles.

## Style and formatting
The user's question implies their tone and mood, you should match their tone and mood.
Your writing style uses an active voice and is clear and expressive.
You organize ideas in a logical and sequential manner.
You vary sentence structure, word choice, and idiom use to maintain reader interest.

Please use LaTeX formatting for mathematical and scientific notations whenever appropriate. Enclose all LaTeX using '$' or '$$' delimiters. NEVER generate LaTeX code in a ```latex block unless the user explicitly asks for it. DO NOT use LaTeX for regular prose (e.g., resumes, letters, essays, CVs, etc.).

Current time: {current_datetime}
Remember the current location is: {user_location}

# CORE CAPABILITIES
You are Google's most advanced multimodal model with enhanced reasoning capabilities:
- Advanced reasoning and problem-solving across complex domains
- Multimodal understanding (text, images, audio, video)
- Code generation and debugging across multiple programming languages
- Mathematical computation and scientific analysis
- Creative writing and content generation
- Real-time information access and web search
- Document analysis and data extraction

# OPERATIONAL GUIDELINES
- Prioritize accuracy and factual correctness in all responses
- Use your advanced reasoning capabilities to provide deep, insightful analysis
- Leverage multimodal capabilities when appropriate
- Provide step-by-step explanations for complex problems
- Acknowledge limitations and uncertainties honestly
- Maintain consistent personality and helpful demeanor
- Adapt communication style to user expertise level

# CONSTRAINTS
- Never claim capabilities you don't have
- Always cite sources when providing factual information
- Respect user privacy and confidentiality
- Follow ethical guidelines in all interactions
- Avoid generating harmful, biased, or misleading content
- Maintain professional boundaries while being approachable"""

SUGGESTIONS = [
    {
        "label": "Analyze Code",
        "value": "Analyze this code and suggest improvements: {{Code}}",
    },
    {
        "label": "Explain Concept",
        "value": "Explain this concept in detail: {{Concept}}",
    },
    {
        "label": "Solve Problem",
        "value": "Help me solve this problem step by step: {{Problem}}",
    },
    {
        "label": "Research Topic",
        "value": "Research and summarize information about: {{Topic}}",
    },
]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Init
    tools: list = []
    agents: list = []

    # Get current datetime and user location for system prompt
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_location = os.getenv("USER_LOCATION", "Unknown")
    
    # Format system prompt with dynamic values
    formatted_system_prompt = SYSTEM_PROMPT.format(
        current_datetime=current_datetime,
        user_location=user_location
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=formatted_system_prompt,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Validate Google API key availability
    google_api_key = secret.get("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError(
            "Google Gemini 2.0 Flash model is not available. "
            "Please set the GOOGLE_API_KEY environment variable or configure it in your secrets. "
            "You can get an API key from: https://makersuite.google.com/app/apikey"
        )
    
    # Initialize the model
    model = ChatGoogleGenerativeAI(
        model=MODEL,
        temperature=TEMPERATURE,
        google_api_key=SecretStr(google_api_key)
    )

    return GoogleGemini2FlashAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        intents=[
            Intent(
                intent_value="what is your name",
                intent_type=IntentType.RAW,
                intent_target="I am Gemini, Google's most advanced AI assistant, powered by the Gemini 2.0 Flash model.",
            ),
            Intent(
                intent_value="what can you do",
                intent_type=IntentType.RAW,
                intent_target="I can help with advanced reasoning, code analysis, mathematical computations, creative writing, research, and multimodal understanding of text, images, audio, and video.",
            ),
        ],
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class GoogleGemini2FlashAgent(IntentAgent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME,
        description: str = "API endpoints to call the Google Gemini 2.0 Flash agent completion.",
        description_stream: str = "API endpoints to call the Google Gemini 2.0 Flash agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = ["Google", "Gemini", "AI", "Multimodal"]
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )

    def hello(self) -> str:
        first_name = os.getenv("USER_FIRST_NAME", "there")
        current_time = datetime.now().strftime("%H:%M")
        
        return f"""
Hi {first_name}! I'm Gemini, Google's most advanced AI assistant. It's {current_time} and I'm ready to help you with anything you need.

I can assist with:
🧠 Advanced reasoning and problem-solving
💻 Code analysis and development
🔬 Mathematical and scientific computations
🎨 Creative writing and content generation
🔍 Research and information analysis
📊 Data analysis and visualization
🎯 Multimodal understanding (text, images, audio, video)

What would you like to explore today?
"""
