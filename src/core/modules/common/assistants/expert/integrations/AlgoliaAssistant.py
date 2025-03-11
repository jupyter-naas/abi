from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import AlgoliaIntegration
from src.core.modules.common.integrations.AlgoliaIntegration import AlgoliaIntegrationConfiguration
from src.core.modules.common.assistants.foundation.SupportAssistant import create_support_agent
from src.core.modules.common.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "An assistant that helps you interact with Algolia search services, including searching indexes and managing records."
AVATAR_URL = "https://logo.clearbit.com/algolia.com"
SYSTEM_PROMPT = f"""
You are Algolia Assistant with access to Algolia search and indexing capabilities.
You can help users search through their Algolia indexes and add new records to them.

When working with Algolia:
1. Always confirm the index name before performing operations
2. For searches, try to understand the user's intent to form the most effective query
3. When adding records, ensure they follow the correct format for Algolia indexing

{RESPONSIBILITIES_PROMPT}
"""

def create_algolia_agent():
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
    
    # Add Algolia integration if credentials are available
    if secret.get('ALGOLIA_API_KEY') and secret.get('ALGOLIA_APPLICATION_ID'):
        integration_config = AlgoliaIntegrationConfiguration(
            app_id=secret.get('ALGOLIA_APPLICATION_ID'),
            api_key=secret.get('ALGOLIA_API_KEY')
        )
        tools += AlgoliaIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="algolia_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    )