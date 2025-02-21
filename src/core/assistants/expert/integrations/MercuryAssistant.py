from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import MercuryIntegration
from src.core.integrations.MercuryIntegration import MercuryIntegrationConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_agent
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Mercury Assistant for managing banking operations and financial data."
AVATAR_URL = "https://logo.clearbit.com/mercury.com"
SYSTEM_PROMPT = f"""
You are a Mercury Assistant with access to MercuryIntegration tools.
If you don't have access to any tool, ask the user to set their MERCURY_API_TOKEN in .env file.
Always be clear and professional in your communication while helping users manage their banking operations.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_mercury_agent():
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
    if secret.get('MERCURY_API_TOKEN'):    
        integration_config = MercuryIntegrationConfiguration(
            api_key=secret.get('MERCURY_API_TOKEN')
        )
        tools += MercuryIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="mercury_agent",
        description="Use to manage Mercury banking operations and financial data",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 