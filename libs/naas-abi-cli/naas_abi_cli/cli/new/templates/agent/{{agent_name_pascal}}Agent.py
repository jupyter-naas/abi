from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

NAME = "{{agent_name_pascal}}Agent"
DESCRIPTION = "An helpful agent that can help you with your tasks."
SYSTEM_PROMPT = """
You are {{agent_name_pascal}}Agent.
"""

class {{agent_name_pascal}}Agent(Agent):

    @staticmethod
    def New(cls, agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> "{{agent_name_pascal}}Agent":
        #from {{module_name_snake}} import ABIModule
        
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

        return cls(
            name=NAME,
            description=DESCRIPTION,
            chat_model=model,
            tools=tools,
            agents=agents,
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )