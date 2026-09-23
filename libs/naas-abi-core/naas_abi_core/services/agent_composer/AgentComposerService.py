"""Compose agents from records (``AgentSpec``) or from a programmatic spec.

Both entry points share one path, so a record and the equivalent ``create()``
call produce the same agent:

* ``compose(spec_or_name, sub_agents=[...instances], tools=[...inline])``
* ``create(name=..., prompt=..., model=..., tools=[refs | BaseTool],
  sub_agents=[record names | Agent instances])``

Composition reuses the runtime's own mechanics rather than re-implementing
them: the result is a plain ``Agent`` (or a ``CapabilityAgent`` when the
record enables runtime discovery); sub-agents become handoff targets exactly
as for Python-defined supervisors, all sharing one ``AgentSharedState`` whose
``supervisor_agent`` is the composed agent, and existing instances are
duplicated onto that state (the caller's instance is never mutated).

Everything is validated before the agent is built, and every problem found is
reported in one ``AgentCompositionError``: unknown or unauthorized tools,
missing configuration or secrets, inline credentials where a secret reference
is required, unknown models and sub-agent records. Sub-agent cycles raise
``SubAgentCycleError``; two capabilities reaching the model under one name
raise ``ToolNameCollisionError`` (the runtime would otherwise keep the first
and silently drop the other).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from queue import Queue
from typing import TYPE_CHECKING, Any

from langchain_core.tools import BaseTool

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.services.agent.CapabilityAgent import (
    CAPABILITY_TOOL_NAMES,
    CapabilityAgent,
    default_tool_context,
)
from naas_abi_core.services.agent.tools.default_tools import default_tools
from naas_abi_core.services.agent_composer.AgentComposerPort import (
    AgentCompositionError,
    AgentSpec,
    AgentSpecNotFoundError,
    CapabilitiesSpec,
    ConfigValue,
    IAgentSpecRepository,
    ISecretResolverPort,
    ModelRef,
    SecretRef,
    SubAgentCycleError,
    SubAgentRef,
    ToolBindingSpec,
    ToolNameCollisionError,
)
from naas_abi_core.services.model_registry.ModelRegistryPort import IModelRegistry
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IToolRegistry,
    ToolContext,
    ToolDefinition,
    ToolRegistryError,
)

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langgraph.checkpoint.base import BaseCheckpointSaver

# Tools every composed agent gets from the runtime; nothing may shadow them.
_DEFAULT_TOOL_NAMES = frozenset(t.name for t in default_tools(None))
_REQUEST_HELP = "request_help"


class AgentComposerService:
    def __init__(
        self,
        tool_registry: IToolRegistry,
        model_registry: IModelRegistry,
        spec_repository: IAgentSpecRepository | None = None,
        secret_resolver: ISecretResolverPort | None = None,
        memory_factory: Callable[[], BaseCheckpointSaver] | None = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._model_registry = model_registry
        self._repository = spec_repository
        self._secrets = secret_resolver
        self._memory_factory = memory_factory

    @property
    def spec_repository(self) -> IAgentSpecRepository | None:
        return self._repository

    # ------------------------------------------------------------ entry points
    def load(self, name: str) -> AgentSpec:
        if self._repository is None:
            raise AgentCompositionError(
                name,
                [
                    (
                        f"agent record '{name}' was requested but the composer "
                        "has no agent record repository"
                    )
                ],
            )
        return self._repository.get(name)

    def compose(
        self,
        spec: AgentSpec | str,
        *,
        sub_agents: Sequence[Agent] = (),
        tools: Sequence[BaseTool] = (),
        context: ToolContext | None = None,
        state: AgentSharedState | None = None,
        memory: BaseCheckpointSaver | None = None,
        event_queue: Queue | None = None,
    ) -> Agent:
        """Build a runnable agent from a record (or a record's name).

        ``context`` identifies the caller: it decides which registry tools may
        be bound. ``state`` continues an existing conversation; by default the
        agent starts a fresh one.
        """
        if isinstance(spec, str):
            spec = self.load(spec)
        shared_state = state or AgentSharedState(thread_id=uuid.uuid4().hex)
        if shared_state.supervisor_agent is None:
            # Like Python-defined supervisors: the whole tree shares one state
            # naming the top agent, which gives sub-agents their handoff back.
            shared_state.set_supervisor_agent(spec.name)
        return self._build(
            spec,
            instances=sub_agents,
            inline_tools=tools,
            context=context,
            shared_state=shared_state,
            memory=memory,
            queue=event_queue or Queue(),
            path=(),
        )

    def create(
        self,
        *,
        name: str,
        prompt: str,
        description: str = "",
        model: str | ModelRef | None = None,
        tools: Sequence[str | ToolBindingSpec | BaseTool] = (),
        sub_agents: Sequence[str | SubAgentRef | Agent] = (),
        capabilities: CapabilitiesSpec | Mapping[str, Any] | None = None,
        context: ToolContext | None = None,
        state: AgentSharedState | None = None,
        memory: BaseCheckpointSaver | None = None,
    ) -> Agent:
        """Programmatic creation: the same composition, from Python values.

        ``tools`` mixes registry references and ready ``BaseTool`` instances;
        ``sub_agents`` mixes record names and existing ``Agent`` instances.
        """
        bindings = [t for t in tools if not isinstance(t, BaseTool)]
        inline = [t for t in tools if isinstance(t, BaseTool)]
        refs = [s for s in sub_agents if not isinstance(s, Agent)]
        instances = [s for s in sub_agents if isinstance(s, Agent)]
        spec = AgentSpec.model_validate(
            {
                "name": name,
                "prompt": prompt,
                "description": description,
                "model": model,
                "tools": bindings,
                "sub_agents": refs,
                "capabilities": capabilities or CapabilitiesSpec(),
            }
        )
        return self.compose(
            spec,
            sub_agents=instances,
            tools=inline,
            context=context,
            state=state,
            memory=memory,
        )

    # --------------------------------------------------------------- building
    def _build(
        self,
        spec: AgentSpec,
        *,
        instances: Sequence[Agent],
        inline_tools: Sequence[BaseTool],
        context: ToolContext | None,
        shared_state: AgentSharedState,
        memory: BaseCheckpointSaver | None,
        queue: Queue,
        path: tuple[str, ...],
    ) -> Agent:
        path = (*path, spec.name)
        problems: list[str] = []
        resolution_context = context or ToolContext()

        chat_model = self._resolve_model(spec.model, problems)
        registry_tools = self._resolve_tools(spec.tools, resolution_context, problems)
        tool_config = self._resolve_capability_config(spec.capabilities, problems)

        children: list[Agent] = []
        for ref in spec.sub_agents:
            if ref.agent in path:
                raise SubAgentCycleError([*path, ref.agent])
            try:
                child_spec = self.load(ref.agent)
            except AgentSpecNotFoundError:
                problems.append(f"sub-agent record '{ref.agent}' does not exist")
                continue
            except AgentCompositionError as exc:
                problems.extend(exc.problems)
                continue
            children.append(
                self._build(
                    child_spec,
                    instances=(),
                    inline_tools=(),
                    context=context,
                    shared_state=shared_state,
                    memory=memory,
                    queue=queue,
                    path=path,
                )
            )
        children.extend(agent.duplicate(queue, shared_state) for agent in instances)

        child_names = [Agent.validate_name(child.name) for child in children]
        for duplicated in sorted({n for n in child_names if child_names.count(n) > 1}):
            problems.append(f"more than one sub-agent is named '{duplicated}'")

        if problems:
            raise AgentCompositionError(spec.name, problems)

        tools = [*inline_tools, *registry_tools]
        is_sub_agent = shared_state.supervisor_agent not in (None, spec.name)
        self._check_names(spec, tools, child_names, is_sub_agent)

        assert chat_model is not None
        options: dict[str, Any] = {
            "name": spec.name,
            "description": spec.description,
            "chat_model": chat_model,
            "tools": tools,
            "agents": children,
            "memory": memory or self._new_memory(),
            "state": shared_state,
            "configuration": AgentConfiguration(system_prompt=spec.prompt),
            "event_queue": queue,
        }
        if not spec.capabilities.enabled:
            return Agent(**options)
        return CapabilityAgent(
            **options,
            tool_registry=self._tool_registry,
            context_provider=(lambda: context)
            if context is not None
            else default_tool_context,
            allow=spec.capabilities.allow,
            max_enabled=spec.capabilities.max_enabled,
            tool_config=tool_config,
        )

    def _new_memory(self) -> BaseCheckpointSaver | None:
        # ``None`` lets the Agent pick the environment's default checkpointer.
        return self._memory_factory() if self._memory_factory is not None else None

    # -------------------------------------------------------------- resolution
    def _resolve_model(
        self, ref: ModelRef | None, problems: list[str]
    ) -> BaseChatModel | None:
        try:
            if ref is None:
                return self._model_registry.get_default_chat_model().model
            return self._model_registry.get_chat_model(
                ref.id, provider=ref.provider
            ).model
        except Exception as exc:  # noqa: BLE001 - reported as a composition problem
            target = (
                f"model '{ref.id}'" if ref is not None else "the default chat model"
            )
            problems.append(f"{target} cannot be resolved: {exc}")
            return None

    def _resolve_config(
        self,
        definition: ToolDefinition,
        config: Mapping[str, ConfigValue],
        problems: list[str],
    ) -> dict[str, Any] | None:
        secret_keys = {r.key for r in definition.requirements.config if r.secret}
        resolved: dict[str, Any] = {}
        ok = True
        for key, value in config.items():
            if isinstance(value, SecretRef):
                secret = self._secrets.resolve(value.secret) if self._secrets else None
                if secret is None:
                    problems.append(
                        f"secret '{value.secret}' for '{key}' of tool "
                        f"'{definition.id}' is not set"
                    )
                    ok = False
                    continue
                resolved[key] = secret
            elif key in secret_keys and value not in (None, ""):
                problems.append(
                    f"'{key}' of tool '{definition.id}' is a credential: reference a "
                    f"secret ({{secret: NAME}}) instead of writing its value"
                )
                ok = False
            else:
                resolved[key] = value
        return resolved if ok else None

    def _resolve_tools(
        self,
        bindings: Sequence[ToolBindingSpec],
        context: ToolContext,
        problems: list[str],
    ) -> list[BaseTool]:
        resolved: list[BaseTool] = []
        for binding in bindings:
            try:
                definition = self._tool_registry.get_definition(binding.tool)
            except ToolRegistryError as exc:
                problems.append(str(exc))
                continue
            config = self._resolve_config(definition, binding.config, problems)
            if config is None:
                continue
            try:
                built = self._tool_registry.resolve(
                    definition.id, context, config=config
                )
            except ToolRegistryError as exc:
                problems.append(str(exc))
                continue
            if not isinstance(built, BaseTool):
                problems.append(
                    f"tool '{definition.id}' resolved to {type(built).__name__}, "
                    "not a LangChain BaseTool"
                )
                continue
            resolved.append(built)
        return resolved

    def _resolve_capability_config(
        self, capabilities: CapabilitiesSpec, problems: list[str]
    ) -> dict[str, dict[str, Any]]:
        resolved: dict[str, dict[str, Any]] = {}
        for tool_id, config in capabilities.tool_config.items():
            try:
                definition = self._tool_registry.get_definition(tool_id)
            except ToolRegistryError as exc:
                problems.append(f"capabilities.tool_config: {exc}")
                continue
            values = self._resolve_config(definition, config, problems)
            if values is not None:
                resolved[str(definition.id)] = values
        return resolved

    # ------------------------------------------------------------- validation
    @staticmethod
    def _check_names(
        spec: AgentSpec,
        tools: Sequence[BaseTool],
        child_names: Sequence[str],
        is_sub_agent: bool,
    ) -> None:
        owners: dict[str, list[str]] = {}
        for name in _DEFAULT_TOOL_NAMES:
            owners.setdefault(name, []).append("the runtime's default tools")
        if is_sub_agent:
            owners.setdefault(_REQUEST_HELP, []).append("the supervisor handoff")
        if spec.capabilities.enabled:
            for name in CAPABILITY_TOOL_NAMES:
                owners.setdefault(name, []).append("runtime capability discovery")
        for child in child_names:
            owners.setdefault(f"transfer_to_{child}", []).append(f"sub-agent '{child}'")
        for tool in tools:
            owners.setdefault(Agent.validate_name(tool.name), []).append(
                f"tool '{tool.name}'"
            )
        collisions = [
            f"`{name}` is claimed by {' and '.join(claimants)}"
            for name, claimants in sorted(owners.items())
            if len(claimants) > 1
        ]
        if collisions:
            raise ToolNameCollisionError(spec.name, collisions)
