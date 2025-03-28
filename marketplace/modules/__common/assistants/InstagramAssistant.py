from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import InstagramIntegration
from src.core.modules.common.integrations.InstagramIntegration import InstagramIntegrationConfiguration
from src.core.modules.support.assistants.SupportAssistant import create_agent as create_support_agent
from src.core.modules.common.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "An Instagram Assistant with access to Instagram Integration tools."
AVATAR_URL = "https://logo.clearbit.com/instagram.com"
SYSTEM_PROMPT = f"""
You are an Instagram Assistant with access to InstagramIntegration tools.
If you don't have access to any tool, ask the user to set their INSTAGRAM_ACCESS_TOKEN in .env file.
Always be clear and professional in your communication while helping users interact with Instagram services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_instagram_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
        system_prompt=SYSTEM_PROMPT
    )
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    if secret.get('INSTAGRAM_ACCESS_TOKEN'):    
        integration_config = InstagramIntegrationConfiguration(
            access_token=secret.get('INSTAGRAM_ACCESS_TOKEN')
        )
        tools += InstagramIntegration.as_tools(integration_config)

    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="instagram_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 