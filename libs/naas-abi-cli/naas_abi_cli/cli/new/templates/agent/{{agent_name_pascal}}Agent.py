from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class {{agent_name_pascal}}Agent(Agent):
    name: str = "{{agent_name_pascal}}"
    description: str = "An helpful agent that can help you with your tasks."
    avatar_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    system_prompt: str = """<role>
You are {{agent_name_pascal}}Agent, a helpful assistant.
</role>

<objective>
Help the user accomplish their tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools — do not fabricate data or capabilities.
</constraints>
"""

    suggestions: list[dict] = [
        {
            "label": "What can you do?",
            "value": "What can you do?",
            "description": "Get an overview of this agent's capabilities",
        },
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "{{agent_name_pascal}}Agent":
        # from {{module_name_snake}} import ABIModule
        from naas_abi_core.engine.context import get_default_model_registry

        # Use the workspace's default chat model from the model registry.
        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        tools: list = []

        agents: list = []

        # Use provided configuration or build one from the class system prompt.
        if agent_configuration is None:
            tools_section = (
                "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
                or ""
            )
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt.replace("[TOOLS]", tools_section)
            )

        # Use provided shared state or create new one
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=agents,
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )
