from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import GmailIntegration
from src.core.modules.common.integrations.GmailIntegration import GmailIntegrationConfiguration
from src.core.modules.common.assistants.foundation.SupportAssistant import create_support_agent
from src.core.modules.common.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Gmail Assistant for managing email operations."
AVATAR_URL = "https://static.dezeen.com/uploads/2020/10/gmail-google-logo-rebrand-workspace-design_dezeen_2364_sq.jpg"
SYSTEM_PROMPT = f"""
You are a Gmail Assistant with access to GmailIntegration tools.
If you don't have access to any tool, ask the user to set their GMAIL_EMAIL, GMAIL_APP_PASSWORD, GMAIL_SMTP_TYPE, GMAIL_SMTP_SERVER, and GMAIL_SMTP_PORT in .env file.
Always be clear and professional in your communication while helping users manage their emails.
Always provide all the context (tool response, draft, etc.) to the user in your final response.
You MUST validate email content twice with the user before sending it.

{RESPONSIBILITIES_PROMPT}
"""

def create_gmail_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
        system_prompt=SYSTEM_PROMPT
    )
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    # Add integration based on available credentials
    username = secret.get('GMAIL_EMAIL')
    app_password = secret.get('GMAIL_APP_PASSWORD')
    smtp_type = secret.get('GMAIL_SMTP_TYPE')
    smtp_server = secret.get('GMAIL_SMTP_SERVER')
    smtp_port = secret.get('GMAIL_SMTP_PORT')
    if username and app_password:    
        integration_config = GmailIntegrationConfiguration(
            username=username,
            app_password=app_password,
            smtp_type=smtp_type,
            smtp_server=smtp_server,
            smtp_port=smtp_port
        )
        tools += GmailIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="gmail_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 