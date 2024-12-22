from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import PostgresIntegration
from src.integrations.PostgresIntegration import PostgresIntegrationConfiguration
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A PostgreSQL Assistant for managing database operations."
AVATAR_URL = "https://logo.clearbit.com/postgresql.org"
SYSTEM_PROMPT = f"""
You are a PostgreSQL Assistant with access to PostgresIntegration tools.
If you don't have access to any tool, ask the user to set their PostgreSQL credentials (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD) in .env file.
Always be clear and professional in your communication while helping users manage their PostgreSQL database.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_postgres_agent():
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
    if all(secret.get(key) for key in ['POSTGRES_HOST', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']):    
        integration_config = PostgresIntegrationConfiguration(
            host=secret.get('POSTGRES_HOST'),
            port=int(secret.get('POSTGRES_PORT', 5432)),
            database=secret.get('POSTGRES_DB'),
            user=secret.get('POSTGRES_USER'),
            password=secret.get('POSTGRES_PASSWORD')
        )
        tools += PostgresIntegration.as_tools(integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="postgres_assistant",
        description="Use to manage PostgreSQL database operations",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 