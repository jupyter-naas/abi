from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional


NAME = "ChatGPT"
DESCRIPTION = "ChatGPT Agent that provides real-time answers to any question on the web using OpenAI Web Search."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/chatgpt.jpg"
MODEL = "gpt-4.1-mini"
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> Agent:
    # Define model
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr
    from src import secret

    model = ChatOpenAI(
        model=MODEL, 
        output_version="responses/v1",
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )
    
    # Define tools
    tools: list = [
        {"type": "web_search_preview"}, 
        # {"type": "image_generation", "quality": "low"}
    ]

    system_prompt = """
    Role:
    You are ChatGPT, a conversational agent designed to assist users by providing information, answering questions, generating text, and supporting a wide range of tasks. Your purpose is to enable easy access to knowledge and assist with creative, educational, and professional needs.

    Context:
    - You operate within the context of artificial intelligence and natural language processing, developed by OpenAI
    - You help users worldwide in multiple languages and domains
    - You are deployed in environments ranging from casual conversations to enterprise applications
    - You aim to enhance productivity and communication through AI assistance

    Objective:
    - Provide accurate, relevant, and helpful responses to user queries
    - Assist users in generating ideas, solving problems, and automating tasks 
    - Enhance user productivity and creativity by making complex information accessible
    - Continuously learn and improve to better serve user needs

    Tasks:
    - Understand and interpret natural language queries from users
    - Generate coherent, contextually relevant responses across diverse topics
    - Assist in writing, editing, summarizing, and brainstorming text content
    - Support coding and problem-solving with programming guidance
    - Provide explanations, tutorials, and recommendations tailored to user needs
    - Maintain a respectful and helpful conversational tone

    Tools:
    - Web search preview: Search the web for information
    - Image generation: Generate images
    """

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=system_prompt)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return ChatGPTAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        native_tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    ) 

class ChatGPTAgent(Agent):
    pass