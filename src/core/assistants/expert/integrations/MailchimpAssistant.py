from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import MailchimpMarketingIntegration
from src.core.integrations.MailchimpMarketingIntegration import MailchimpMarketingIntegrationConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Mailchimp Assistant with access to Mailchimp Integration tools."
AVATAR_URL = "https://logo.clearbit.com/mailchimp.com"
SYSTEM_PROMPT = f"""
You are a Mailchimp Assistant with access to MailchimpIntegration tools.
If you don't have access to any tool, ask the user to set their MAILCHIMP_API_KEY and MAILCHIMP_SERVER_PREFIX in .env file.
Always be clear and professional in your communication while helping users interact with Mailchimp services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_mailchimp_agent():
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
    
    if secret.get('MAILCHIMP_API_KEY') and secret.get('MAILCHIMP_SERVER_PREFIX'):    
        integration_config = MailchimpMarketingIntegrationConfiguration(
            api_key=secret.get('MAILCHIMP_API_KEY'),
            server_prefix=secret.get('MAILCHIMP_SERVER_PREFIX')
        )
        tools += MailchimpMarketingIntegration.as_tools(integration_config)

    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="mailchimp_assistant",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 