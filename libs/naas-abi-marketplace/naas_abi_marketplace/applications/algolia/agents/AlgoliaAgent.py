from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Algolia"
DESCRIPTION = "An Agent that helps you interact with Algolia search services, including searching indexes and managing records."
SYSTEM_PROMPT = """<role>
You are Algolia, an expert search and indexing specialist. You possess deep expertise in:
</role>

<objective>
Help users interact with Algolia search services, including searching indexes and managing records.
</objective>

<context>
You operate within a secure environment with authenticated access to Algolia services through configured API credentials.
</context>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Verify you have access to the tools, otherwise ask the user to set their Algolia credentials (ALGOLIA_API_KEY, ALGOLIA_APPLICATION_ID) in .env file
- Always confirm the index name before performing operations
- For searches, try to understand the user's intent to form the most effective query
- When adding records, ensure they follow the correct format for Algolia indexing

<constraints>
- Be concise and to the point
- Maintain professional tone
- Always cite data sources and explain methodology used
</constraints>
"""
SUGGESTIONS: list[str] = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    # Initialize module
    from naas_abi_marketplace.applications.algolia import ABIModule

    module = ABIModule.get_instance()
    algolia_api_key = module.configuration.algolia_api_key
    algolia_application_id = module.configuration.algolia_application_id

    # Set model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model

    # Set tools
    from naas_abi_marketplace.applications.algolia.integrations.AlgoliaIntegration import (
        AlgoliaIntegrationConfiguration,
        as_tools,
    )

    tools: list = []
    integration_config = AlgoliaIntegrationConfiguration(
        app_id=algolia_application_id,
        api_key=algolia_api_key,
    )
    tools += as_tools(integration_config)

    intents: list = [
        Intent(
            intent_value="Search in Algolia index",
            intent_type=IntentType.TOOL,
            intent_target="algolia_search",
        ),
        Intent(
            intent_value="Add records to index",
            intent_type=IntentType.TOOL,
            intent_target="algolia_add_record",
        ),
        Intent(
            intent_value="List Algolia indexes",
            intent_type=IntentType.TOOL,
            intent_target="algolia_list_indexes",
        ),
        Intent(
            intent_value="Get index statistics",
            intent_type=IntentType.TOOL,
            intent_target="algolia_index_stats",
        ),
    ]

    # Set configuration
    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=system_prompt)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return AlgoliaAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class AlgoliaAgent(IntentAgent):
    pass
