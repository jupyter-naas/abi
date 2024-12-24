from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import YouTubeIntegration
from src.integrations.YouTubeIntegration import YouTubeIntegrationConfiguration
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A YouTube Assistant for managing video operations and data retrieval."
AVATAR_URL = "https://logo.clearbit.com/youtube.com"
SYSTEM_PROMPT = f"""
You are a YouTube Assistant with access to YouTubeIntegration tools.
If you don't have access to any tool, ask the user to set their YOUTUBE_API_KEY in .env file.
Always be clear and professional in your communication while helping users interact with YouTube data.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_youtube_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
        system_prompt=SYSTEM_PROMPT
    )
    model = ChatOpenAI(
        model="gpt-4",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    # Add integration based on available credentials
    if secret.get('YOUTUBE_API_KEY'):    
        integration_config = YouTubeIntegrationConfiguration(
            api_key=secret.get('YOUTUBE_API_KEY')
        )
        tools += YouTubeIntegration.as_tools(integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="youtube_assistant",
        description="Use to manage YouTube data and video operations",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 