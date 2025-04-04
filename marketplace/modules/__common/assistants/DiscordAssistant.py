from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import DiscordIntegration
from src.core.modules.common.integrations.DiscordIntegration import DiscordIntegrationConfiguration
from src.core.modules.support.agents.SupportAssistant import create_agent as create_support_agent
from src.core.modules.common.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Discord Assistant with access to Discord Integration tools."
AVATAR_URL = "https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0a6a49cf127bf92de1e2_icon_clyde_blurple_RGB.png"
SYSTEM_PROMPT = f"""
You are a Discord Assistant with access to Discord Integration tools.
If you don't have access to any tool, ask the user to set their access token in .env file.
Always be clear and professional in your communication while helping users interact with Clockify services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_discord_agent():
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
    if secret.get('DISCORD_TOKEN'):    
        discord_integration_config = DiscordIntegrationConfiguration(token=secret.get('DISCORD_TOKEN'))
        tools += DiscordIntegration.as_tools(discord_integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)    
    tools += support_agent.as_tools()
    
    return Agent(
        name="discord_agent",
        description="Use to manage Discord channels, messages and more",
        chat_model=model,
        tools=tools, 
        state=AgentSharedState(thread_id=1), 
        configuration=agent_configuration, 
        memory=MemorySaver()    
    )