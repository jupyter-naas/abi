from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from src import secret
from fastapi import APIRouter
from src.core.modules.support.agents.SupportAssistant import (
    create_agent as create_support_agent,
)
from src.core.modules.common.prompts.responsabilities_prompt import (
    RESPONSIBILITIES_PROMPT,
)
from src.core.apps.terminal_agent.terminal_style import (
    print_tool_usage,
    print_tool_response,
)
from src.core.modules.common.integrations import PostgresIntegration
from src.core.modules.common.integrations.PostgresIntegration import (
    PostgresIntegrationConfiguration,
)


DESCRIPTION = "A PostgreSQL Assistant for managing database operations."
AVATAR_URL = "https://logo.clearbit.com/postgresql.org"
SYSTEM_PROMPT = f"""
You are a PostgreSQL Assistant with access to PostgresIntegration tools.
If you don't have access to any tool, ask the user to set their PostgreSQL credentials (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD) in .env file.
Always be clear and professional in your communication while helping users manage their PostgreSQL database.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""


def create_postgres_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None,
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            on_tool_usage=lambda message: print_tool_usage(
                message.tool_calls[0]["name"]
            ),
            on_tool_response=lambda message: print_tool_response(
                f"\n{message.content}"
            ),
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Set model
    model = ChatOpenAI(
        model="gpt-4o", temperature=0, api_key=secret.get("OPENAI_API_KEY")
    )

    # Add tools
    postgres_user = secret.get("POSTGRES_USER")
    postgres_password = secret.get("POSTGRES_PASSWORD")
    postgres_dbname = secret.get("POSTGRES_DBNAME")
    postgres_host = secret.get("POSTGRES_HOST")
    postgres_port = secret.get("POSTGRES_PORT")
    if (
        postgres_user
        and postgres_password
        and postgres_dbname
        and postgres_host
        and postgres_port
    ):
        integration_config = PostgresIntegrationConfiguration(
            host=postgres_host,
            port=postgres_port,
            database=postgres_dbname,
            user=postgres_user,
            password=postgres_password,
        )
        tools += PostgresIntegration.as_tools(integration_config)

    # Add agents
    agents.append(create_support_agent(agent_shared_state, agent_configuration))

    return PostgresAssistant(
        name="postgres_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class PostgresAssistant(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = "postgres",
        name: str = "Postgres Assistant",
        description: str = "API endpoints to call the Postgres assistant completion.",
        description_stream: str = "API endpoints to call the Postgres assistant stream completion.",
        tags: list[str] = [],
    ):
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
