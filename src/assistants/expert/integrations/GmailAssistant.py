from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import GmailIntegration
from src.integrations.GmailIntegration import GmailIntegrationConfiguration
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Gmail Assistant for managing email operations."
AVATAR_URL = "https://static.dezeen.com/uploads/2020/10/gmail-google-logo-rebrand-workspace-design_dezeen_2364_sq.jpg"
SYSTEM_PROMPT = f"""
You are a Gmail Assistant with access to GmailIntegration tools.
If you don't have access to any tool, ask the user to set their GMAIL_API_KEY and necessary OAuth credentials in .env file.
Always be clear and professional in your communication while helping users manage their emails.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_gmail_agent():
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
    email = secret.get('GMAIL_EMAIL')
    app_password = secret.get('GMAIL_APP_PASSWORD')
    if email and app_password:    
        integration_config = GmailIntegrationConfiguration(
            email=email,
            app_password=app_password
        )
        tools += GmailIntegration.as_tools(integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="gmail_assistant",
        description="Use to manage Gmail operations and email tasks",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 