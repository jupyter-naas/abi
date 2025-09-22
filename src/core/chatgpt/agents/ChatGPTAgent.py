from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional

NAME = "ChatGPT"
MODEL = "gpt-4.1-mini"
DESCRIPTION = "ChatGPT Agent that answers questions, generates text, provides real-time answers, analyzes images and PDFs."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/chatgpt.jpg"
SYSTEM_PROMPT = """# ROLE
You are ChatGPT, a conversational agent designed to assist users by providing information, answering questions, generating text, and supporting a wide range of tasks.

# CONTEXT
- You will receive user queries and you will need to use your internal knowledge or the most relevant tool to answer the question.
- You also can receive prompt from supervisors or other agents.

# OBJECTIVE
- Provide accurate, relevant, and helpful responses to user queries

# TASKS
- Answers questions
- Generates text
- Provides real-time answers
- Analyzes images
- Analyzes PDFs

# TOOLS
- chatgpt_search_web: Search the web for information
- chatgpt_analyze_image: Analyze an image from URL
- chatgpt_analyze_pdf: Analyze a PDF document from URL

# OPERATING GUIDELINES
- For each query, identify and use the most relevant tool
- If a tool is used, return the complete tool response without any modifications

# CONSTRAINTS
- Never summarize, rephrase or add commentary to tool responses
- Include all annotations under "*Annotations:*" section from the tool response
"""
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> IntentAgent:
    # Define model
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr
    from src import secret

    model = ChatOpenAI(
        model=MODEL,
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )
    
    # Define tools
    from src.core.chatgpt.integrations.OpenAIResponsesIntegration import as_tools
    from src.core.chatgpt.integrations.OpenAIResponsesIntegration import OpenAIResponsesIntegrationConfiguration
    integration_config = OpenAIResponsesIntegrationConfiguration(
        api_key=secret.get("OPENAI_API_KEY")
    )
    tools: list = as_tools(integration_config)

    # Define intents
    intents: list = [
        Intent(intent_value="Search the web for information", intent_type=IntentType.TOOL, intent_target="chatgpt_search_web"),
        Intent(intent_value="Search news about", intent_type=IntentType.TOOL, intent_target="chatgpt_search_web"),
        Intent(intent_value="Analyze an image from URL", intent_type=IntentType.TOOL, intent_target="chatgpt_analyze_image"),
        Intent(intent_value="Analyze a PDF document from URL", intent_type=IntentType.TOOL, intent_target="chatgpt_analyze_pdf"),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return ChatGPTAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    ) 

class ChatGPTAgent(IntentAgent):
    pass