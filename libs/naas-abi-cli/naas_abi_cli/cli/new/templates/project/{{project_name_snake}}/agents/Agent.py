from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

NAME = "{{project_name_snake}} Agent"
DESCRIPTION = "An helpful agent that can help you with your tasks."
SYSTEM_PROMPT = """
You are {{project_name_snake}} Agent.
"""


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[Agent]:
    #from {{project_name_snake}} import ABIModule
    
    # Set model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_5 import model as chatgpt_model

    model = chatgpt_model.model

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    tools: list = []

    agents: list = []

    return {{project_name_pascal}}Agent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        memory=None,
        state=agent_shared_state,
        configuration=agent_configuration,
    )


class {{project_name_pascal}}Agent(Agent):
    pass
