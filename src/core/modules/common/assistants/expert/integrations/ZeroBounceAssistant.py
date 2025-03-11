from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import ZeroBounceIntegration
from src.core.modules.common.integrations.ZeroBounceIntegration import ZeroBounceIntegrationConfiguration
from src.core.modules.common.assistants.foundation.SupportAssistant import create_support_agent
from src.core.modules.common.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A ZeroBounce Assistant for email validation and verification operations."
AVATAR_URL = "https://www.mailerlite.com/assets/integration/zb.webp"
SYSTEM_PROMPT = f"""
You are a ZeroBounce Assistant with access to ZeroBounceIntegration tools.
If you don't have access to any tool, ask the user to set their ZEROBOUNCE_API_KEY in .env file.
Always be clear and professional in your communication while helping users validate and verify email addresses.
Always provide all the context (tool response, validation results, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_zerobounce_agent():
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
    if secret.get('ZEROBOUNCE_API_KEY'):    
        integration_config = ZeroBounceIntegrationConfiguration(
            api_key=secret.get('ZEROBOUNCE_API_KEY')
        )
        tools += ZeroBounceIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="zerobounce_agent",
        description="Use to validate and verify email addresses",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 