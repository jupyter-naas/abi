"""An agent that discovers and switches its own tools during a conversation.

``CapabilityAgent`` starts with its static tools plus four capability tools:

* ``search_capabilities(query, limit)``: semantic search over the tool
  registry. Discovery only; it neither runs nor grants anything.
* ``enable_capability(tool_id)``: checks the allow list, the enabled-tool
  limit, the caller's access and the tool's configuration, and rejects a
  model-facing name already in use. On success the tool is bound from the next
  model call on.
* ``disable_capability(tool_id)``: removes it from binding and dispatch.
* ``list_enabled_capabilities()``.

Semantics:

* **Scope.** The selection lives in the conversation's checkpointed graph
  state (``ABIAgentState.enabled_capabilities``, keyed by agent name), so it
  survives across turns and agent reconstruction, and never leaks into
  another conversation or the shared registry.
* **Default state.** Nothing is enabled; static tools are always on.
* **Timing.** Changes apply from the next graph step. Calls the model already
  issued in the current step are dispatched against the tool set the step
  started with, so a call issued alongside its own ``disable_capability``
  still completes; the next model call no longer sees the tool.
* **Batches.** All calls of one step see the state the step started with, so
  each enable or disable is validated against that state plus the changes
  issued before it in the same step: simultaneous enables cannot exceed the
  limit or claim one model-facing name.
* **Authorization.** Access is checked when enabling (``ToolAction.ENABLE``)
  and again every time the tool is bound or dispatched
  (``ToolAction.EXECUTE``), for the caller of the current request, together
  with the agent's current allow list. An enabled tool the caller may no
  longer run, or that the allow list no longer covers, is neither bound nor
  dispatched.
"""

from __future__ import annotations

import fnmatch
import json
import threading
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Annotated, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.tools import (
    BaseTool,
    InjectedToolCallId,
    StructuredTool,
    Tool,
    tool,
)
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.Agent import (
    ABIAgentState,
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.services.agent.context import (
    agent_user_id,
    agent_workspace_id,
    coder_workspace_base,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IToolRegistry,
    ToolAccessDeniedError,
    ToolAction,
    ToolContext,
    ToolId,
    ToolRef,
    ToolRegistryError,
)
from naas_abi_core.utils.Logger import logger

if TYPE_CHECKING:
    from queue import Queue

    from langchain_core.runnables import Runnable
    from langgraph.checkpoint.base import BaseCheckpointSaver

CAPABILITY_TOOL_NAMES = (
    "search_capabilities",
    "enable_capability",
    "disable_capability",
    "list_enabled_capabilities",
)


class CapabilityLimitError(ToolRegistryError):
    """Enabling one more tool would exceed the agent's limit."""


class CapabilityNameCollisionError(ToolRegistryError):
    """The tool's model-facing name is already bound for this agent."""


def default_tool_context() -> ToolContext:
    """The caller of the current request, from the agent request context."""
    return ToolContext(
        user_id=agent_user_id.get(), workspace_id=agent_workspace_id.get()
    )


class CapabilityAgent(Agent):
    _tool_registry: IToolRegistry
    _context_provider: Callable[[], ToolContext]
    _allow: tuple[str, ...]
    _max_enabled: int
    _tool_config: dict[str, dict[str, Any]]
    _search_limit: int

    def __init__(
        self,
        name: str,
        description: str,
        chat_model: BaseChatModel | ChatModel,
        tool_registry: IToolRegistry,
        tools: list[Tool | BaseTool | Agent] | None = None,
        agents: list[Agent] | None = None,
        memory: BaseCheckpointSaver | None = None,
        state: AgentSharedState | None = None,
        configuration: AgentConfiguration | None = None,
        event_queue: Queue | None = None,
        native_tools: list[dict] | None = None,
        enable_default_tools: bool = True,
        markdown_pretty_display: bool = False,
        *,
        context_provider: Callable[[], ToolContext] | None = None,
        allow: Sequence[str] = ("*",),
        max_enabled: int = 10,
        tool_config: Mapping[str, Mapping[str, Any]] | None = None,
        search_limit: int = 10,
    ):
        if max_enabled < 1:
            raise ValueError("max_enabled must be at least 1")
        self._tool_registry = tool_registry
        self._context_provider = context_provider or default_tool_context
        self._allow = tuple(allow)
        self._max_enabled = max_enabled
        self._tool_config = {k: dict(v) for k, v in (tool_config or {}).items()}
        self._search_limit = search_limit
        self._bound_cache: dict[tuple[tuple[str, ...], bool], Runnable] = {}
        # Capability changes issued by the step ``call_tools`` is running.
        self._step = threading.local()

        # Keep the caller's list untouched: ``duplicate`` passes it back in.
        user_tools = list(tools or [])
        super().__init__(
            name=name,
            description=description,
            chat_model=chat_model,
            tools=[*user_tools, *self._capability_tools()],
            agents=agents,
            memory=memory,
            state=state if state is not None else AgentSharedState(),
            configuration=configuration
            if configuration is not None
            else AgentConfiguration(),
            event_queue=event_queue,
            native_tools=native_tools,
            enable_default_tools=enable_default_tools,
            markdown_pretty_display=markdown_pretty_display,
        )
        self._user_tools = user_tools

    # ------------------------------------------------------------ properties
    @property
    def tool_registry(self) -> IToolRegistry:
        return self._tool_registry

    @property
    def max_enabled(self) -> int:
        return self._max_enabled

    @property
    def allow(self) -> tuple[str, ...]:
        return self._allow

    # ------------------------------------------------------------- selection
    def _context(self) -> ToolContext:
        return self._context_provider()

    def _allowed(self, tool_id: str) -> bool:
        return any(fnmatch.fnmatchcase(tool_id, pattern) for pattern in self._allow)

    def enabled_tool_ids(self, state: Mapping[str, Any]) -> list[str]:
        selections = state.get("enabled_capabilities") or {}
        return list(selections.get(self.name, []))

    def _pending(self) -> list[tuple[str, str]]:
        pending = getattr(self._step, "pending", None)
        return pending if pending is not None else []

    def _record(self, operation: str, tool_ids: Sequence[str]) -> None:
        pending = getattr(self._step, "pending", None)
        if pending is not None:
            pending.extend((operation, tool_id) for tool_id in tool_ids)

    def _selection(self, state: Mapping[str, Any]) -> list[str]:
        """Enabled ids once the changes issued earlier in this step apply."""
        ids = self.enabled_tool_ids(state)
        for operation, tool_id in self._pending():
            if operation == "enable" and tool_id not in ids:
                ids.append(tool_id)
            elif operation == "disable" and tool_id in ids:
                ids.remove(tool_id)
        return ids

    def _definition_name(self, tool_id: str) -> str | None:
        try:
            return self._tool_registry.get_definition(tool_id).name
        except ToolRegistryError:
            return None

    def _resolve_enabled(self, state: Mapping[str, Any]) -> dict[str, BaseTool]:
        """Enabled tools the current caller may run, by model-facing name.

        The allow list is applied here too, not only when enabling, so
        narrowing it revokes selections persisted in existing conversations.
        A restored tool whose name a static tool now owns is left out, and
        tools are bound under the normalised name dispatch uses.
        """
        context = self._context()
        resolved: dict[str, BaseTool] = {}
        for tool_id in self.enabled_tool_ids(state):
            if not self._allowed(tool_id):
                logger.warning(
                    f"Agent '{self.name}': enabled tool '{tool_id}' is outside the "
                    f"allow list ({', '.join(self._allow)}) and is not bound."
                )
                continue
            try:
                built = self._tool_registry.resolve(
                    tool_id, context, config=self._tool_config.get(tool_id)
                )
            except ToolRegistryError as exc:
                logger.warning(
                    f"Agent '{self.name}': enabled tool '{tool_id}' is unavailable "
                    f"for this request and is not bound: {exc}"
                )
                continue
            if not isinstance(built, BaseTool):
                logger.error(
                    f"Agent '{self.name}': tool '{tool_id}' resolved to "
                    f"{type(built).__name__}, not a LangChain BaseTool; not bound."
                )
                continue
            name = Agent.validate_name(built.name)
            if name in self._tools_by_name:
                # Checked on enable, but a restored selection can meet a
                # static tool added since. Dispatch prefers the static tool,
                # so binding matches it.
                logger.warning(
                    f"Agent '{self.name}': enabled tool '{tool_id}' is shadowed by "
                    f"the agent's own tool `{name}` and is not bound."
                )
                continue
            if name in resolved:
                logger.error(
                    f"Agent '{self.name}': enabled tool '{tool_id}' shares the name "
                    f"`{name}` with another enabled tool; only the first is bound."
                )
                continue
            if built.name != name:
                # Bind under the normalised name dispatch looks up, on a copy:
                # the registry's instance is shared with other agents.
                built = built.model_copy(update={"name": name})
            resolved[name] = built
        return resolved

    @staticmethod
    def _binding_signature(tools: Mapping[str, BaseTool]) -> tuple[str, ...]:
        """What the model is shown for each tool.

        Keying the bound-model cache on this (not on names) rebinds when a
        tool is swapped for another version or republished with a new schema.
        """
        signature = []
        for name, bound_tool in sorted(tools.items()):
            schema = bound_tool.tool_call_schema
            schema = schema if isinstance(schema, dict) else schema.model_json_schema()
            signature.append(
                json.dumps(
                    [name, bound_tool.description, schema], sort_keys=True, default=str
                )
            )
        return tuple(signature)

    # ---------------------------------------------------------- agent hooks
    def _chat_model_for_turn(self, state: ABIAgentState) -> Runnable:
        dynamic = self._resolve_enabled(state)
        if not dynamic:
            return super()._chat_model_for_turn(state)
        with_workspace = bool(coder_workspace_base.get())
        key = (self._binding_signature(dynamic), with_workspace)
        cached = self._bound_cache.get(key)
        if cached is not None:
            return cached
        tools: list[Tool | BaseTool | dict] = [
            *self._structured_tools,
            *dynamic.values(),
            *self._native_tools,
        ]
        if not with_workspace:
            tools = [t for t in tools if not Agent._requires_workspace(t)]
        bound = self._chat_model.bind_tools(tools)
        self._bound_cache[key] = bound
        return bound

    def _tool_for_call(
        self, tool_name: str, state: ABIAgentState
    ) -> Tool | BaseTool | None:
        static = super()._tool_for_call(tool_name, state)
        if static is not None:
            return static
        return self._resolve_enabled(state).get(tool_name)

    def _tool_names_for_turn(self, state: ABIAgentState) -> list[str]:
        return sorted(
            {*super()._tool_names_for_turn(state), *self._resolve_enabled(state)}
        )

    def call_tools(self, state: ABIAgentState) -> list[Command]:
        # Every call of this step receives the same starting ``state``; the
        # capability tools record their changes here so later calls of the
        # step validate against them.
        self._step.pending = []
        try:
            return super().call_tools(state)
        finally:
            self._step.pending = None

    # -------------------------------------------------------- capability tools
    def _capability_tools(self) -> list[BaseTool]:
        agent = self

        @tool("search_capabilities")
        def search_capabilities(
            query: str,
            state: Annotated[dict, InjectedState],
            limit: int = 5,
        ) -> str:
            """Search the tools you could enable, by describing the capability you need.

            Returns candidate tools as JSON (tool_id, name, description, score,
            available, missing_config, enabled). Searching does not enable a
            tool: call enable_capability with a tool_id to use it.

            Args:
                query: The capability you need, in plain words, e.g. "open a ticket in the bug tracker".
                limit: Maximum number of candidates to return.
            """
            limit = max(1, min(int(limit), agent._search_limit))
            enabled = set(agent.enabled_tool_ids(state))
            # The allow list filters inside the registry's widening search, so
            # tools outside it never starve the limit.
            results = agent._tool_registry.search_tools(
                query,
                context=agent._context(),
                limit=limit,
                where=lambda definition: agent._allowed(str(definition.id)),
            )
            candidates = [
                {
                    "tool_id": r.tool_id,
                    "name": r.name,
                    "description": r.description,
                    "score": round(r.score, 4),
                    "available": r.availability.available,
                    "missing_config": list(r.availability.missing_config),
                    "enabled": r.tool_id in enabled,
                }
                for r in results
            ]
            return json.dumps(candidates)

        @tool("enable_capability")
        def enable_capability(
            tool_id: str,
            state: Annotated[dict, InjectedState],
            tool_call_id: Annotated[str, InjectedToolCallId],
        ) -> Command:
            """Enable a tool found with search_capabilities, so you can call it from your next step.

            Args:
                tool_id: The tool_id returned by search_capabilities.
            """
            definition = agent._tool_registry.get_definition(tool_id)
            canonical = str(definition.id)
            if not agent._allowed(canonical):
                raise ToolAccessDeniedError(
                    f"Tool '{canonical}' is not allowed for agent '{agent.name}' "
                    f"(allowed: {', '.join(agent._allow)})."
                )
            enabled = [i for i in agent._selection(state) if agent._allowed(i)]
            if canonical in enabled:
                return _reply(
                    tool_call_id,
                    "enable_capability",
                    f"'{canonical}' is already enabled as `{definition.name}`.",
                )
            if len(enabled) >= agent._max_enabled:
                raise CapabilityLimitError(
                    f"Agent '{agent.name}' reached its limit of "
                    f"{agent._max_enabled} enabled tools. Disable one first "
                    f"(enabled: {', '.join(enabled)})."
                )
            taken = set(agent._tools_by_name) | {
                name
                for name in (agent._definition_name(i) for i in enabled)
                if name is not None
            }
            if definition.name in taken:
                raise CapabilityNameCollisionError(
                    f"A tool named `{definition.name}` is already available to "
                    f"agent '{agent.name}', so '{canonical}' cannot be enabled."
                )
            # Enforces access (ENABLE) and configuration, and proves the tool builds.
            agent._tool_registry.resolve(
                canonical,
                agent._context(),
                config=agent._tool_config.get(canonical),
                action=ToolAction.ENABLE,
            )
            agent._record("enable", [canonical])
            return Command(
                update={
                    "enabled_capabilities": {agent.name: {"enable": [canonical]}},
                    "messages": [
                        _message(
                            tool_call_id,
                            "enable_capability",
                            f"Enabled '{canonical}'. Call it as `{definition.name}` "
                            "from your next step.",
                        )
                    ],
                }
            )

        @tool("disable_capability")
        def disable_capability(
            tool_id: str,
            state: Annotated[dict, InjectedState],
            tool_call_id: Annotated[str, InjectedToolCallId],
        ) -> Command:
            """Disable a tool you enabled earlier. It is removed from your next step on.

            Args:
                tool_id: The tool_id of an enabled tool.
            """
            ref = ToolRef.parse(tool_id)
            enabled = agent._selection(state)
            matches = [
                enabled_id
                for enabled_id in enabled
                if ref.matches(ToolId.parse(enabled_id))
            ]
            if not matches:
                raise ToolRegistryError(
                    f"'{tool_id}' is not enabled for agent '{agent.name}' "
                    f"(enabled: {', '.join(enabled) or 'none'})."
                )
            agent._record("disable", matches)
            return Command(
                update={
                    "enabled_capabilities": {agent.name: {"disable": matches}},
                    "messages": [
                        _message(
                            tool_call_id,
                            "disable_capability",
                            f"Disabled {', '.join(matches)}.",
                        )
                    ],
                }
            )

        @tool("list_enabled_capabilities")
        def list_enabled_capabilities(state: Annotated[dict, InjectedState]) -> str:
            """List the tools you enabled in this conversation, as JSON."""
            listed = []
            for tool_id in agent.enabled_tool_ids(state):
                try:
                    name = agent._tool_registry.get_definition(tool_id).name
                except ToolRegistryError:
                    name = None
                listed.append({"tool_id": tool_id, "name": name})
            return json.dumps(listed)

        tools: list[BaseTool] = [
            search_capabilities,
            enable_capability,
            disable_capability,
            list_enabled_capabilities,
        ]
        for t in tools:
            assert isinstance(t, StructuredTool)
        return tools

    # ------------------------------------------------------------ duplication
    def duplicate(
        self,
        queue: Queue | None = None,
        agent_shared_state: AgentSharedState | None = None,
    ) -> CapabilityAgent:
        from queue import Queue as _Queue

        shared_state = agent_shared_state or AgentSharedState()
        queue = queue if queue is not None else _Queue()
        agents = [
            agent.duplicate(queue, shared_state) for agent in self._original_agents
        ]
        new_agent = self.__class__(
            name=self._name,
            description=self._description,
            chat_model=self._chat_model,
            tool_registry=self._tool_registry,
            tools=self._user_tools,
            agents=agents,
            memory=self._checkpointer,
            state=shared_state,
            configuration=self._configuration,
            event_queue=queue,
            native_tools=self._native_tools,
            enable_default_tools=self._enable_default_tools,
            markdown_pretty_display=self._markdown_pretty_display,
            context_provider=self._context_provider,
            allow=self._allow,
            max_enabled=self._max_enabled,
            tool_config=self._tool_config,
            search_limit=self._search_limit,
        )
        own_limit = getattr(self, "recursion_limit", None)
        if isinstance(own_limit, int) and own_limit > 0:
            new_agent.recursion_limit = own_limit
        return new_agent


def _message(tool_call_id: str, name: str, content: str) -> ToolMessage:
    return ToolMessage(content=content, name=name, tool_call_id=tool_call_id)


def _reply(tool_call_id: str, name: str, content: str) -> Command:
    return Command(update={"messages": [_message(tool_call_id, name, content)]})
