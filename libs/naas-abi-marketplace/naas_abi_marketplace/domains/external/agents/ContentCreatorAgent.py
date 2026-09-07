from __future__ import annotations

from typing import Optional

from langchain_core.messages import AnyMessage
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class ContentCreatorAgent(Agent):
    name: str = "ContentCreator"
    description: str = (
        "Expert content creator specializing in copywriting, social media content, "
        "video scripts, and creative campaigns."
    )
    logo_url: str = "naas_abi_marketplace/domains/external/assets/public/content-creator.png"
    system_prompt: str = """<role>
You are ContentCreatorAgent, a Content Creator expert with deep experience in
copywriting, social media content, video scripts, creative campaigns, content
optimization, and brand voice.
</role>

<objective>
Help the user accomplish their content creation tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Understand target audience and brand voice before drafting.
- Optimize for platform-specific requirements and engagement.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools — do not fabricate data or capabilities.
</constraints>
"""

    suggestions: list[dict] = [
        {
            "label": "Create Content",
            "value": "Create {{Content Type}} for {{Platform/Purpose}}",
            "description": "Create content for a platform or purpose",
        },
        {
            "label": "Social Media Plan",
            "value": "Plan social media content for {{Campaign/Period}}",
            "description": "Plan social media content for a campaign or period",
        },
        {
            "label": "Video Script",
            "value": "Write video script for {{Video Topic/Purpose}}",
            "description": "Write a video script",
        },
        {
            "label": "Campaign Ideas",
            "value": "Generate campaign ideas for {{Product/Service}}",
            "description": "Generate creative campaign ideas",
        },
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "ContentCreatorAgent":
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
