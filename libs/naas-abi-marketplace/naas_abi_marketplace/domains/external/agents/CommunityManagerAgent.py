from __future__ import annotations

from typing import Optional

from langchain_core.messages import AnyMessage
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class CommunityManagerAgent(Agent):
    name: str = "CommunityManager"
    description: str = (
        "Expert community manager specializing in community building, engagement "
        "strategies, social media management, and brand advocacy."
    )
    logo_url: str = "naas_abi_marketplace/domains/external/assets/public/community-manager.png"
    system_prompt: str = """<role>
You are CommunityManagerAgent, a Community Manager expert with deep experience in
community building, engagement strategies, social media management, brand
advocacy, event management, and community analytics.
</role>

<objective>
Help the user accomplish their community management tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Prioritize authentic community relationships and inclusive environments.
- Align community activities with brand values and objectives.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools — do not fabricate data or capabilities.
</constraints>
"""

    suggestions: list[dict] = [
        {
            "label": "Community Strategy",
            "value": "Develop community strategy for {{Platform/Brand}}",
            "description": "Develop a community strategy for a platform or brand",
        },
        {
            "label": "Engagement Campaign",
            "value": "Create engagement campaign for {{Community/Event}}",
            "description": "Create an engagement campaign",
        },
        {
            "label": "Social Media Plan",
            "value": "Plan social media content for {{Platform/Campaign}}",
            "description": "Plan social media content",
        },
        {
            "label": "Event Planning",
            "value": "Plan community event for {{Occasion/Topic}}",
            "description": "Plan a community event",
        },
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "CommunityManagerAgent":
        # from naas_abi_marketplace.domains.external import ABIModule
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        tools: list = []
        agents: list = []

        if agent_configuration is None:
            tools_section = (
                "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
                or ""
            )
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt.replace("[TOOLS]", tools_section)
            )

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

    def onHumanMessage(self, message: AnyMessage) -> None:
        """Called every time the user sends a new message to this agent."""

    def onAImessage(self, message: AnyMessage, agent_name: str) -> None:
        """Called every time a new AI message is emitted."""
