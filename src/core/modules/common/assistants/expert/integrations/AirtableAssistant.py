from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import AirtableIntegration
from src.core.modules.common.integrations.AirtableIntegration import AirtableIntegrationConfiguration
from src.core.modules.common.assistants.foundation.SupportAssistant import create_support_agent
from src.core.modules.common.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "An Airtable Assistant with access to Airtable Integration tools."
AVATAR_URL = "https://logo.clearbit.com/airtable.com"
SYSTEM_PROMPT = f"""
You are an Airtable Assistant with access to AirtableIntegration tools.
If you don't have access to any tool, ask the user to set their AIRTABLE_API_KEY and AIRTABLE_BASE_ID in .env file.
Always be clear and professional in your communication while helping users interact with Airtable services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_airtable_agent():
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
    if secret.get('AIRTABLE_API_KEY') and secret.get('AIRTABLE_BASE_ID'):    
        integration_config = AirtableIntegrationConfiguration(
            api_key=secret.get('AIRTABLE_API_KEY'),
            base_id=secret.get('AIRTABLE_BASE_ID')
        )
        tools += AirtableIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="airtable_agent",
        description="Use to manage Airtable operations and data",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 