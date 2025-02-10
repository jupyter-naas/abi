from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import QontoIntegration
from src.core.integrations.QontoIntegration import QontoIntegrationConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Qonto Assistant for managing banking operations and financial data."
AVATAR_URL = "https://logo.clearbit.com/qonto.com"
SYSTEM_PROMPT = f"""
You are a Qonto Assistant with access to QontoIntegration tools.
If you don't have access to any tool, ask the user to set their QONTO_SECRET_KEY and QONTO_ORGANIZATION_SLUG in .env file.
Always be clear and professional in your communication while helping users manage their banking operations.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_qonto_agent():
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
    
    # Add integration based on available credentials
    if secret.get('QONTO_SECRET_KEY') and secret.get('QONTO_ORGANIZATION_SLUG'):    
        integration_config = QontoIntegrationConfiguration(
            secret_key=secret.get('QONTO_SECRET_KEY'),
            organization_slug=secret.get('QONTO_ORGANIZATION_SLUG')
        )
        tools += QontoIntegration.as_tools(integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="qonto_assistant",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 