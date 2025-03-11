from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import SendGridIntegration
from src.core.modules.common.integrations.SendGridIntegration import SendGridIntegrationConfiguration
from src.core.modules.support.assistants.SupportAssistant import create_agent as create_support_agent
from src.core.modules.common.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A SendGrid Assistant for managing email operations and campaigns."
AVATAR_URL = "https://logo.clearbit.com/sendgrid.com"
SYSTEM_PROMPT = f"""
You are a SendGrid Assistant with access to SendGridIntegration tools.
If you don't have access to any tool, ask the user to set their SendGrid API key (SENDGRID_API_KEY) in .env file.
Always be clear and professional in your communication while helping users manage their email operations.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_sendgrid_agent():
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
    if secret.get('SENDGRID_API_KEY'):    
        integration_config = SendGridIntegrationConfiguration(
            api_key=secret.get('SENDGRID_API_KEY')
        )
        tools += SendGridIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="sendgrid_agent",
        description="Use to manage SendGrid email operations",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 