from typing import Optional

from abi.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

from src.core.chatgpt import ABIModule

NAME = "ChatGPT"
DESCRIPTION = "ChatGPT Agent that provides real-time answers, analyzes images and PDFs."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/chatgpt.jpg"
SYSTEM_PROMPT = """# ROLE
You are ChatGPT, an agent designed to assist user by performing web search, analyzing images and PDFs.

# OBJECTIVE
- Perform web search or provide answers from your internal knowledge
- Analyze images
- Analyze PDFs

# CONTEXT
- You receive prompts directly from users or from other agents.

# TASKS
1. Answer question about your capabilities
2. Quickly identify if the request is about your objective
3. For non objective requests, use the request_help tool to redirect to appropriate agent
4. Use appropriate tool or internal knowledge to answer the question

# TOOLS
- chatgpt_search_web: Search the web for information
- chatgpt_analyze_image: Analyze an image from URL
- chatgpt_analyze_pdf: Analyze a PDF document from URL

# OPERATING GUIDELINES
1. Tool Selection:
   - For web searches: Use chatgpt_search_web when user asks about current events, news, or online research
   - For images: Use chatgpt_analyze_image when user provides an image URL or asks about image analysis
   - For PDFs: Use chatgpt_analyze_pdf when user provides a PDF URL or asks about PDF content
   - Use internal knowledge for general questions not requiring real-time data

2. Tool Usage:
   - For chatgpt_search_web: 
    2.1. Add current date to user's query (parameter of query tool). For example: 
    if query = "le gagnant de la dernière ligue des champions masculin" then query = "Current date: 2025-06-25: le gagnant de la dernière ligue des champions masculin"
    2.2. Use the new query to perform the web search.

   - For chatgpt_analyze_image: Ensure valid image URL is provided
   - For chatgpt_analyze_pdf: Ensure valid PDF URL is provided

3. Response Handling:
   - Return responses in the same language as the user's query
   - For web search results: Preserve original content and context as much as possible
   - Include complete tool responses without modifications
   - Maintain all formatting and structure from tool outputs

# CONSTRAINTS
- Never summarize, rephrase or add commentary to tool responses
- Include all annotations under "*Annotations:*" section from the tool response
- Do not translate tool responses unless specifically requested by user
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model
    from src.core.chatgpt.models.gpt_4_1_mini import model

    # Define tools
    tools: list = []
    from src.core.chatgpt.integrations.OpenAIResponsesIntegration import (
        OpenAIResponsesIntegrationConfiguration,
        as_tools,
    )

    module: ABIModule = ABIModule.get_instance()

    api_key = module.configuration.openai_api_key
    base_url = "https://api.openai.com/v1/responses"
    if module.configuration.openrouter_api_key:
        api_key = module.configuration.openrouter_api_key
        base_url = "https://openrouter.ai/api/v1/responses"

    integration_config = OpenAIResponsesIntegrationConfiguration(
        api_key=api_key, base_url=base_url
    )
    tools += as_tools(integration_config)

    # Define intents
    intents: list = [
        Intent(
            intent_value="search news about",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_search_web",
        ),
        Intent(
            intent_value="search web about",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_search_web",
        ),
        Intent(
            intent_value="research online about",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_search_web",
        ),
        Intent(
            intent_value="latest events about",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_search_web",
        ),
        Intent(
            intent_value="search information about",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_search_web",
        ),
        Intent(
            intent_value="analyze an image from URL",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_analyze_image",
        ),
        Intent(
            intent_value="analyze this image",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_analyze_image",
        ),
        Intent(
            intent_value="describe this image",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_analyze_image",
        ),
        Intent(
            intent_value="what can you tell about the content of this image",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_analyze_image",
        ),
        Intent(
            intent_value="analyze a PDF document from URL",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_analyze_pdf",
        ),
        Intent(
            intent_value="analyze this PDF document",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_analyze_pdf",
        ),
        Intent(
            intent_value="what can you tell about the content of this PDF document",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_analyze_pdf",
        ),
        Intent(
            intent_value="Summarize the content of this PDF document",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_analyze_pdf",
        ),
        Intent(
            intent_value="Extract all people cited in this PDF document",
            intent_type=IntentType.TOOL,
            intent_target="chatgpt_analyze_pdf",
        ),
        Intent(
            intent_value="help me write python code",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="Access OpenAI models documentation",
            intent_type=IntentType.RAW,
            intent_target="🚀 **OpenAI Models Documentation**\n\n[OpenAI Models Documentation](https://platform.openai.com/docs/models)\n\nFeatures: Available models, capabilities, pricing, and usage guidelines",
        ),
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
        memory=None,
    )


class ChatGPTAgent(IntentAgent):
    pass
