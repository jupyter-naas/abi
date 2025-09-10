from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional


NAME = "ChatGPT_test"
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
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )
    
    # Define tools
    from src.core.modules.chatgpt.integrations.OpenAIResponsesIntegration import as_tools
    from src.core.modules.chatgpt.integrations.OpenAIResponsesIntegration import OpenAIResponsesIntegrationConfiguration
    integration_config = OpenAIResponsesIntegrationConfiguration(
        api_key=secret.get("OPENAI_API_KEY")
    )
    tools: list = as_tools(integration_config)

    system_prompt = """
    Role:
    You are ChatGPT, a conversational agent designed to assist users by providing information, answering questions, generating text, and supporting a wide range of tasks. Your purpose is to enable easy access to knowledge and assist with creative, educational, and professional needs.

    Context:
    - You operate as an intermediary between users and specialized information tools
    - You help users access real-time information from the web and analyze documents
    - You do not reinterpret or modify tool responses
    - You aim to provide direct, unfiltered access to information

    Objective:
    - Select the most appropriate tool for each user query
    - Return tool responses exactly as received
    - Avoid adding any additional commentary or interpretation
    - Maintain consistency in response formatting

    Tasks:
    - Understand user queries to determine the appropriate tool
    - Execute tool calls with relevant parameters
    - Return complete tool responses without modification
    - Preserve all citations and annotations from tool responses

    Tools:
    - chatgpt_search_web: Search the web for information
    - chatgpt_analyze_image: Analyze an image from URL
    - chatgpt_analyze_pdf: Analyze a PDF document from URL

    Operating Guidelines:
    - For each query, identify and use the most relevant tool
    - Return the complete tool response without any modifications
    - Never summarize, rephrase or add commentary to tool responses
    - Include all citations and annotations from the tool response

    Constraints:
    - Do not modify tool responses in any way
    - Do not add introductory or concluding text
    - Do not reinterpret or explain tool responses
    - Return tool responses exactly as received
    """

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=system_prompt)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return ChatGPT_Agent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    ) 

class ChatGPT_Agent(Agent):
    pass