"""Shared construction for Nexus feature office agents (Slides-parity).

These helpers live outside ``naas_abi/agents/*.py`` on purpose:
``ModuleAgentLoader`` registers every ``naas_abi`` ``Expose`` subclass it finds
in those module namespaces, so a shared base class imported there would load
as an agent of its own (and Abi would try to build it). Each feature agent
stays a plain ``IntentAgent`` subclass, like ``SlidesAgent``, and calls
``build_feature_agent`` from its ``New``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, TypeVar

from langchain_core.embeddings import Embeddings
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentScope,
    IntentType,
)

A = TypeVar("A", bound=IntentAgent)

# Same fallback as ``ABIModule.Configuration.abi_agent_model``. Feature agents
# follow the orchestrator's model; the chat request retargets it per turn.
DEFAULT_FEATURE_MODEL = "claude-sonnet-5"

# Graph steps per turn for feature agents and for Abi handing off to them.
# LangGraph's default (25) ran out on "how is this built?" answers: IntentAgent
# overhead plus 6 to 8 source reads, and a handoff shares the supervisor's
# budget. 60 leaves room for about 20 tool hops. Slides turns keep 160.
FEATURE_RECURSION_LIMIT = 60

FEATURE_GROUNDING_GUIDELINES = """- You answer four kinds of questions about your feature: what the user can do here, how it was built, how to operate it, and anything else about it (errors, feature flags, permissions, tenancy, related agents).
- How it was built, how something works, where something lives, where data comes from: your first action is a read_nexus_source or search_nexus_source call, even when you think you know. An implementation answer without a source read in this turn is wrong. Start from the <code_map> paths. Use search_nexus_source to find a symbol and list_nexus_source to browse a folder. Cite the paths (and line numbers) you actually read. Never describe the implementation from memory or training data. If a file is not shipped in this deployment, say so and answer from what you could read.
- What the user can do here: answer from <capabilities> and your tools. Name the UI flow (sidebar, button, route) and the API route behind it when it helps.
- Doing it for the user: use your feature tools. They default to the open item from the open-feature block. Never ask which item when one is open. Never claim a change, or list items, without a result from your own tool in this turn: another agent's tool result or error earlier in the conversation is not yours, so call your tool. Never invent names, sizes, or dates.
- read_file, write_file, and list_dir act on the user's Coder workspace, not on the Nexus source. Use the *_nexus_source tools for Nexus code.
- Out of scope: say which Nexus feature owns it and suggest opening that feature. Do not invent tools, agents, or transfers.
- Lead with the answer, then the evidence (paths, tool results). Keep it short."""


class _NoopEmbeddings(Embeddings):
    """Feature agents route nothing themselves; intents only feed Abi's handoff."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        del text
        return [0.0]


def feature_handoff_intents(target: str, phrases: Iterable[str]) -> list[Intent]:
    """Phrases Abi copies so a feature request transfers to ``target``."""
    return [
        Intent(
            intent_value=phrase,
            intent_type=IntentType.RAW,
            intent_target=target,
            intent_scope=IntentScope.ALL,
        )
        for phrase in phrases
    ]


def configured_feature_model() -> str:
    """The orchestrator model id, or the default when ABIModule is not loaded."""
    try:
        from naas_abi import ABIModule

        return str(ABIModule.get_instance().configuration.abi_agent_model)
    except Exception:  # noqa: BLE001
        return DEFAULT_FEATURE_MODEL


def feature_system_prompt(
    *,
    name: str,
    class_name: str,
    feature: str,
    role: str,
    context: str,
    tasks: str,
    capabilities: str,
    code_map: str,
    constraints: str = "",
) -> str:
    """The shared office-agent prompt skeleton; ``[TOOLS]`` is filled by ``New``.

    Feature sections carry the specifics. Grounding, tone, language, and the
    no-invented-action rules are the same for every feature agent.
    """
    extra = f"\n{constraints.strip()}" if constraints.strip() else ""
    return f"""<role>
You are {name}, the office agent for the Nexus {feature} feature. {role} You are not Abi with a {feature} hat.
</role>

<objective>
Answer every question about Nexus {feature} (what the user can do, how it was built, how to operate it, errors, feature flags, permissions) from live tools and the actual code, and act on it when asked.
</objective>

<context>
{context.strip()}
{roster_line(class_name)}
</context>

<tasks>
{tasks.strip()}
</tasks>

<capabilities>
{capabilities.strip()}
</capabilities>

<code_map>
{code_map.strip()}
</code_map>

<grounding_guidelines>
{FEATURE_GROUNDING_GUIDELINES}
</grounding_guidelines>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Keep a clear, concise, professional tone.
- Format replies as clean Markdown.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message.
- Never reveal passwords, tokens, or secret values.
- Never claim an action happened without a tool result that confirms it.{extra}
</constraints>
"""


def roster_line(class_name: str) -> str:
    """How a workspace gets this agent, so the agent can answer "how do I add you?"."""
    return (
        f'A workspace enables you with "naas_abi {class_name}" in its agents: list '
        "(config.yaml, organizations[].workspaces[]); Settings > Agents shows the roster. "
        "If asked how to add you, give that exact line."
    )


def render_tools_section(tools: list[Any]) -> str:
    return "\n".join(f"- {tool.name}: {tool.description}" for tool in tools)


def build_feature_agent(
    cls: type[A],
    *,
    tools: list[Any],
    intents: list[Intent],
    agent_shared_state: AgentSharedState | None = None,
    agent_configuration: AgentConfiguration | None = None,
    model_id: str | None = None,
) -> A:
    """Construct a feature office agent the way SlidesAgent.New does.

    Default tools stay on so the coding-workspace filesystem tools are there
    when a Coder sidecar is bound to the request. The Markdown pretty-display
    pass stays off.
    """
    from naas_abi import ABIModule

    abi_module = ABIModule.get_instance()
    chat_model = abi_module.engine.services.model_registry.get_chat_model(
        model_id or abi_module.configuration.abi_agent_model,
        provider=abi_module.configuration.abi_agent_provider,
    )

    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    if agent_configuration is None:
        system_prompt = str(cls.system_prompt)
        agent_configuration = AgentConfiguration(
            system_prompt=system_prompt.replace("[TOOLS]", render_tools_section(tools))
        )

    return cls(
        name=cls.name,
        description=cls.description,
        chat_model=chat_model,
        tools=tools,
        agents=[],
        intents=intents,
        memory=None,
        state=agent_shared_state,
        configuration=agent_configuration,
        embedding_model=_NoopEmbeddings(),
        enable_default_intents=False,
        enable_default_tools=True,
        # The prompt already asks for Markdown. The extra formatting pass costs
        # a model call per answer and could blank it (see Agent._pretty_display_markdown).
        markdown_pretty_display=False,
    )
