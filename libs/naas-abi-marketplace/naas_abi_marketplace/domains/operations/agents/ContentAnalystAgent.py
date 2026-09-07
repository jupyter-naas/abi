from __future__ import annotations

from typing import Optional

from langchain_core.messages import AnyMessage
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class ContentAnalystAgent(Agent):
    name: str = "ContentAnalyst"
    description: str = (
        "Expert content analyst specializing in content performance analysis, "
        "audience insights, SEO optimization, and content strategy recommendations."
    )
    logo_url: str = "naas_abi_marketplace/domains/operations/assets/public/content-analyst.png"
    system_prompt: str = """<role>
You are ContentAnalystAgent, a Content Analyst expert with deep experience in
content performance analysis, audience insights, SEO optimization, content
strategy, data analytics, and competitive analysis.
</role>

<objective>
Help the user accomplish their content analysis tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Provide expert-level strategic guidance grounded in content analytics best practices.
- Consider practical constraints and focus on measurable outcomes.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools — do not fabricate data or capabilities.
</constraints>
"""

    suggestions: list[dict] = [
        {
            "label": "Strategy",
            "value": "Develop {{Strategy Type}} for {{Context}}",
            "description": "Develop a content analysis or SEO strategy",
        },
        {
            "label": "Analysis",
            "value": "Analyze {{Subject}} for {{Purpose}}",
            "description": "Analyze content performance or audience data",
        },
        {
            "label": "Optimization",
            "value": "Optimize {{Process/System}} for {{Goal}}",
            "description": "Optimize content or SEO for a goal",
        },
        {
            "label": "Planning",
            "value": "Plan {{Initiative}} for {{Timeframe}}",
            "description": "Plan a content analysis initiative",
        },
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "ContentAnalystAgent":
        # from naas_abi_marketplace.domains.operations import ABIModule
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

    # ------------------------------------------------------------------
    # Message hooks
    #
    # Already wired: the runtime calls these on every message, you only have
    # to fill in the body. They are observation points -- whatever you return
    # is ignored, and if you raise, the error is logged and swallowed so the
    # conversation keeps going.
    #
    # They run inline on the streaming thread, so keep them quick. Hand slow
    # work (HTTP calls, big writes) off to a queue or a thread yourself.
    # ------------------------------------------------------------------

    def onHumanMessage(self, message: AnyMessage) -> None:
        """Called every time the user sends a new message to this agent.

        Runs once per turn, before the message reaches the model.

        Args:
            message (AnyMessage): The HumanMessage that was just received.
        """
        # Example -- replace with whatever you need:
        # from naas_abi_core.utils.Logger import logger
        # logger.info(f"[{self.name}] human: {message.content}")

    def onAImessage(self, message: AnyMessage, agent_name: str) -> None:
        """Called every time a new AI message is emitted.

        Fires for messages from this agent *and* from any of its sub-agents --
        use ``agent_name`` to tell them apart. Messages that only carry tool
        calls are not reported here.

        Args:
            message (AnyMessage): The AIMessage that was just emitted.
            agent_name (str): Name of the agent that produced the message.
        """
        # Example -- replace with whatever you need:
        # from naas_abi_core.utils.Logger import logger
        # logger.info(f"[{agent_name}] ai: {message.content}")
