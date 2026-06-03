from typing import Optional, TypeVar

from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

TAgent = TypeVar("TAgent", bound=Agent)


class ZettafoxAgent(Agent):
    name: str = "Zettafox Agent"
    description: str = "A Zettafox agent."
    system_prompt: str = """
    You are Zettafox Agent.
    """
    logo_url: str = (
        "naas_abi_marketplace/ai/zettafox/assets/public/zettafox-logo-square.png"
    )

    @staticmethod
    def get_model() -> ChatModel:
        from naas_abi_marketplace.ai.zettafox.models.qwen_3_6 import model

        return model

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "ZettafoxAgent":
        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)

        if agent_shared_state is None:
            agent_shared_state = AgentSharedState()

        tools: list = []
        agents: list = []

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=cls.get_model(),
            tools=tools,
            agents=agents,
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )
