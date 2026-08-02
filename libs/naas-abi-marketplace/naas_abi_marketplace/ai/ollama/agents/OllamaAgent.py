from __future__ import annotations

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class OllamaAgent(Agent):
    name: str = "Ollama"
    description: str = (
        "Local assistant powered by Qwen2.5 3B through Ollama — private, "
        "keyless, and works offline."
    )
    avatar_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
    )
    system_prompt: str = """<role>
You are a helpful assistant running entirely on the user's own machine via a
local Ollama server. Nothing the user tells you leaves this machine.
</role>

<objective>
Answer questions and help with everyday tasks — writing, editing, explaining,
brainstorming, and general reasoning.
</objective>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Prefer short, direct answers; offer to go deeper rather than pre-empting.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- You have no tools and no network access. If a task needs live data or an
  external action, say so plainly and suggest an agent that has the tools.
</constraints>

<identity>
You run on Qwen2.5 3B via a local Ollama server.
</identity>
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
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
    ) -> OllamaAgent:
        from naas_abi_marketplace.ai.ollama import ABIModule

        registry = ABIModule.get_instance().engine.services.model_registry
        chat_model = registry.get_chat_model("qwen-2.5-3b")

        # No tools of its own — it's a general local assistant. The model does
        # support tool calling, so tools can be added here without swapping it.
        tools: list = []
        agents: list = []

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
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
            # `Agent` injects get_time_date, write_file, read_file, list_dir
            # and run_terminal by default. Declaring `tools = []` does not stop
            # it, so this agent's prompt — "no tools, no network access,
            # nothing leaves this machine" — was false at runtime, and
            # run_terminal made the privacy claim wrong outright in a coding
            # workspace. Turning them off keeps the prompt honest rather than
            # rewriting the prompt to describe tools this agent has no use for.
            enable_default_tools=False,
        )
