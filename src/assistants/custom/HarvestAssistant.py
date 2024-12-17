from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import HarvestIntegration
from src.integrations.HarvestIntegration import HarvestIntegrationConfiguration
from src.assistants.foundation.SupportAssitant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Harvest Assistant for time tracking and project management."
AVATAR_URL = "https://logo.clearbit.com/getharvest.com"
SYSTEM_PROMPT = f"""
You are a Harvest Assistant with access to HarvestIntegration tools.
If you don't have access to any tool, ask the user to set their HARVEST_API_KEY and HARVEST_ACCOUNT_ID in .env file.
Always be clear and professional in your communication while helping users manage their time tracking and projects.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_harvest_agent():
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
    if secret.get('HARVEST_API_KEY') and secret.get('HARVEST_ACCOUNT_ID'):    
        integration_config = HarvestIntegrationConfiguration(
            api_key=secret.get('HARVEST_API_KEY'),
            account_id=secret.get('HARVEST_ACCOUNT_ID')
        )
        tools += HarvestIntegration.as_tools(integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="harvest_assistant",
        description="Use to manage time tracking and project management tasks",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 