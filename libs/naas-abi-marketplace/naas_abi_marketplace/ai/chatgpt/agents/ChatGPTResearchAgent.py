from typing import Optional

from langchain_openai import ChatOpenAI
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class ChatGPTResponsesAgent(Agent):
    name: str = "ChatGPT Research"
    description: str = "ChatGPT Research Agent provides real-time answers to any question on the web using responses v1 OpenAI api."
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/chatgpt.jpg"
    )
    model_name = "gpt-5-mini"
    native_tools: list = [{"type": "web_search_preview"}]

    @staticmethod
    def get_model(cls) -> ChatOpenAI:

        from naas_abi_marketplace.ai.chatgpt import ABIModule
        from pydantic import SecretStr

        module: ABIModule = ABIModule.get_instance()

        model = ChatOpenAI(
            model=cls.model_name,
            output_version="responses/v1",
            api_key=SecretStr(module.configuration.openai_api_key),
        )
        return model

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "ChatGPTResponsesAgent":

        # Set configuration
        if agent_configuration is None:
            agent_configuration = AgentConfiguration()
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=cls.get_model(cls=cls),
            native_tools=cls.native_tools,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
