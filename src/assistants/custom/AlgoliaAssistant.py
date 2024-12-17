from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import AlgoliaIntegration
from src.integrations.AlgoliaIntegration import AlgoliaIntegrationConfiguration
from src.assistants.foundation.SupportAssitant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "An assistant that helps you interact with Algolia search services, including searching indexes and managing records."
AVATAR_URL = "https://res.cloudinary.com/crunchbase-production/image/upload/c_lpad,h_256,w_256,f_auto,q_auto:eco,dpr_1/v1397187054/a498c6a8002d90d41f36341ae0989cb9.png"
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
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="algolia_assistant",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    )