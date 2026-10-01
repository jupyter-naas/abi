"""SDK Agent: the core ``naas_abi_core`` Agent behaviour, async and core-free.

Same constructor shape, class attributes, graph (node names included), callbacks,
hooks and ``stream_invoke`` event vocabulary as core. The deliberate difference is
async execution (``await agent.invoke``, ``async for ... in agent.stream_invoke``):
SDK models and the document checkpointer run on the module event loop.
tests/agent_parity runs every scenario against both implementations.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.types import Command

from naas_abi_sdk.agents._messages import (
    _MAX_TOOL_RESULT_CHARS,
    ToolCallRepair,
    _truncate_tool_content,
    compact_old_tool_messages,
    friendly_model_invoke_error,
    logger,
    validate_name,
)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. If a tool you used did not return the result you "
    "wanted, look for another tool that might be able to help you. If you don't find a "
    "suitable tool. Just output 'I DONT KNOW'"
)


class AgentSharedState:
    """Conversation routing state; ``thread_id`` selects the checkpointed thread."""

    def __init__(
        self,
        thread_id: str = "1",
        current_active_agent: str | None = None,
        supervisor_agent: str | None = None,
    ):
        assert isinstance(thread_id, str)
        self._thread_id = thread_id
        self._current_active_agent = current_active_agent
        self._supervisor_agent = supervisor_agent
        self._requesting_help = False
        self._active_agent_by_thread: dict[str, str | None] = {
            thread_id: current_active_agent
        }

    @property
    def thread_id(self) -> str:
        return self._thread_id

    def set_thread_id(self, thread_id: str) -> None:
        if thread_id == self._thread_id:
            return
        self._active_agent_by_thread[self._thread_id] = self._current_active_agent
        self._thread_id = thread_id
        self._current_active_agent = self._active_agent_by_thread.get(thread_id)

    @property
    def current_active_agent(self) -> str | None:
        return self._current_active_agent

    def set_current_active_agent(self, agent_name: str | None) -> None:
        self._current_active_agent = (
            None if agent_name is None else validate_name(agent_name)
        )
        self._active_agent_by_thread[self._thread_id] = self._current_active_agent

    @property
    def supervisor_agent(self) -> str | None:
        return self._supervisor_agent

    def set_supervisor_agent(self, agent_name: str | None) -> None:
        self._supervisor_agent = (
            None if agent_name is None else validate_name(agent_name)
        )

    @property
    def requesting_help(self) -> bool:
        return self._requesting_help

    def set_requesting_help(self, requesting_help: bool) -> None:
        self._requesting_help = requesting_help


class ABIAgentState(MessagesState):
    system_prompt: str
    current_active_agent: str | None
    supervisor_agent: str | None


@dataclass
class Event:
    payload: Any = field()


@dataclass
class ToolUsageEvent(Event):
    pass


@dataclass
class ToolResponseEvent(Event):
    pass


@dataclass
class AIMessageEvent(Event):
    agent_name: str


@dataclass
class FinalStateEvent(Event):
    pass


@dataclass
class CallModelEvent(Event):
    agent_name: str


@dataclass
class AgentRoutingEvent(Event):
    agent_name: str


@dataclass
class AgentConfiguration:
    on_tool_usage: Callable[[AnyMessage], None] = field(
        default_factory=lambda: lambda _: None
    )
    on_tool_response: Callable[[AnyMessage], None] = field(
        default_factory=lambda: lambda _: None
    )
    on_ai_message: Callable[[AnyMessage, str], None] = field(
        default_factory=lambda: lambda _, __: None
    )
    on_agent_calling: Callable[[str], None] = field(
        default_factory=lambda: lambda _: None
    )
    on_agent_routing: Callable[[str], None] = field(
        default_factory=lambda: lambda _: None
    )
    system_prompt: str | Callable[[list[AnyMessage]], str] = field(
        default=DEFAULT_SYSTEM_PROMPT
    )

    def get_system_prompt(self, messages: list[AnyMessage]) -> str:
        return (
            self.system_prompt(messages)
            if callable(self.system_prompt)
            else self.system_prompt
        )


def default_tools(agent: Agent) -> list[BaseTool]:
    @tool(return_direct=False)
    def get_time_date(timezone: str = "Europe/Paris") -> str:
        """Returns the current date and time for a given timezone."""
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(timezone)).strftime("%H:%M:%S %Y-%m-%d")

    return [get_time_date]


def can_bind_tools(chat_model: BaseChatModel) -> bool:
    try:

        @tool(return_direct=True)
        def get_time_date(timezone: str = "Europe/Paris") -> str:
            """Get the current time and date."""
            return timezone

        chat_model.bind_tools([get_time_date])
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "Chat model %s does not support tool calling: %s",
            type(chat_model).__name__,
            exc,
        )
        return False


class Agent(ToolCallRepair):
    """Binds a chat model to tools in a LangGraph tool loop, like core ``Agent``.

    Subclasses set ``name``, ``description``, ``system_prompt``, ``suggestions``,
    ``logo_url`` and ``recursion_limit`` and build themselves in an async ``New``.
    """

    recursion_limit: int = 0

    @classmethod
    async def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
    ) -> Agent:
        raise NotImplementedError("This method is not implemented")

    def __init__(
        self,
        name: str,
        description: str,
        chat_model: Any,
        tools: list[Any] | None = None,
        agents: list[Any] | None = None,
        memory: BaseCheckpointSaver | None = None,
        state: AgentSharedState | None = None,
        configuration: AgentConfiguration | None = None,
        enable_default_tools: bool = True,
        markdown_pretty_display: bool = False,
    ):
        if agents:
            raise NotImplementedError(
                "Local sub-agents are not supported yet; pass remote agents through tools"
            )
        assert isinstance(name, str)
        assert isinstance(description, str)
        self._name = validate_name(name)
        self._description = description
        self._markdown_pretty_display = markdown_pretty_display
        self._state = state if state is not None else AgentSharedState()
        self._configuration = (
            configuration if configuration is not None else AgentConfiguration()
        )
        self._original_tools = list(tools or [])
        self._enable_default_tools = enable_default_tools
        # SDK RemoteModel (model registry over NATS) and core-style wrappers expose .model.
        base_chat_model = (
            chat_model if isinstance(chat_model, BaseChatModel) else chat_model.model
        )
        assert isinstance(base_chat_model, BaseChatModel)
        self._chat_model = base_chat_model
        self._checkpointer = memory if memory is not None else InMemorySaver()
        self._event_queue: asyncio.Queue | None = None
        self._wire_callbacks()
        self._wire_tools()
        self.build_graph()

    # --- wiring ------------------------------------------------------------------------

    def _wire_callbacks(self) -> None:
        self._on_tool_usage = self._configuration.on_tool_usage
        self._on_tool_response = self._configuration.on_tool_response
        self._on_ai_message = self._configuration.on_ai_message
        self._on_call_model = self._configuration.on_agent_calling
        self._on_agent_routing = self._configuration.on_agent_routing

    def _wire_tools(self) -> None:
        tools = list(self._original_tools)
        if self._enable_default_tools:
            tools += default_tools(self)
        self._tools = tools
        self._structured_tools = self.prepare_tools(tools)
        self._tools_by_name: dict[str, BaseTool] = {
            t.name: t for t in self._structured_tools
        }
        self._chat_model_with_tools = self._chat_model
        if self._structured_tools:
            if can_bind_tools(self._chat_model):
                self._chat_model_with_tools = self._chat_model.bind_tools(
                    self._structured_tools
                )
            else:
                logger.warning(
                    "Chat model %s does not support tool calling. Tools will not be available for agent '%s'.",
                    type(self._chat_model).__name__,
                    self._name,
                )

    @staticmethod
    def prepare_tools(tools: list[Any]) -> list[BaseTool]:
        """Tools by unique sanitised name; remote agents (``as_tools()``) become tools."""
        prepared: list[BaseTool] = []
        names: set[str] = set()
        for item in tools:
            candidates = (
                item.as_tools()
                if not isinstance(item, BaseTool) and hasattr(item, "as_tools")
                else [item]
            )
            for candidate in candidates:
                if not hasattr(candidate, "name"):
                    continue
                candidate.name = validate_name(candidate.name)
                if candidate.name not in names:
                    prepared.append(candidate)
                    names.add(candidate.name)
        return prepared

    def build_graph(self) -> None:
        graph = StateGraph(ABIAgentState)
        graph.add_node("render_system_prompt", self.render_system_prompt)
        graph.add_edge(START, "render_system_prompt")
        graph.add_node("current_active_agent", self.current_active_agent)
        graph.add_edge("render_system_prompt", "current_active_agent")
        graph.add_node("continue_conversation", self.continue_conversation)
        graph.add_node("call_model", self.call_model)
        graph.add_node("call_tools", self.call_tools)
        self.graph = graph.compile(checkpointer=self._checkpointer)

    # --- graph nodes -------------------------------------------------------------------

    async def render_system_prompt(self, state: ABIAgentState) -> Command:
        return Command(
            update={
                "system_prompt": self._configuration.get_system_prompt(
                    state["messages"]
                )
            }
        )

    def _has_supervisor(self) -> bool:
        supervisor = self._state.supervisor_agent
        return (
            supervisor is not None
            and supervisor.strip() != ""
            and supervisor != self._name
        )

    async def current_active_agent(self, state: ABIAgentState) -> Command:
        persisted_active = state.get("current_active_agent")
        if persisted_active is not None and self._state.current_active_agent is None:
            self._state.set_current_active_agent(persisted_active)
        persisted_supervisor = state.get("supervisor_agent")
        if persisted_supervisor is not None and self._state.supervisor_agent is None:
            self._state.set_supervisor_agent(persisted_supervisor)

        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        if (
            last_human is not None
            and isinstance(last_human.content, str)
            and last_human.content.startswith("@")
            and last_human.content.split(" ")[0].split("@")[1] != self.name
        ):
            # Core strips an @mention it cannot route (no sub-agent of that name).
            import re

            last_human.content = re.sub(r"^@[^ ]* ", "", last_human.content)

        system_prompt = state["system_prompt"]
        if self._has_supervisor() and "SUPERVISOR SYSTEM PROMPT" not in system_prompt:
            system_prompt = _supervised_prompt(
                self._state.supervisor_agent or "", system_prompt
            )
        if "CURRENT_DATE" not in state["system_prompt"]:
            current_date = f"CURRENT_DATE: The current date is {datetime.now(UTC).strftime('%Y-%m-%d')}\n"
            system_prompt = system_prompt + "\n" + current_date
        return Command(
            goto="continue_conversation", update={"system_prompt": system_prompt}
        )

    async def continue_conversation(self, state: ABIAgentState) -> Command:
        return Command(goto="call_model")

    async def call_model(
        self, state: ABIAgentState
    ) -> Command[Literal["call_tools", "__end__"]]:
        self._state.set_current_active_agent(self.name)
        self._notify_call_model(self._name)
        routing_update: dict[str, Any] = {
            "current_active_agent": self._state.current_active_agent,
            "supervisor_agent": self._state.supervisor_agent,
        }
        messages = state["messages"]
        if state["system_prompt"]:
            messages = [SystemMessage(content=state["system_prompt"]), *messages]
        messages = self._normalize_tool_inputs_in_messages(messages)
        messages = compact_old_tool_messages(messages)
        try:
            response = await self._chat_model_with_tools.ainvoke(messages)
        except Exception as e:  # noqa: BLE001
            logger.error("Model invocation failed for agent '%s': %s", self._name, e)
            return Command(
                goto="__end__",
                update={
                    **routing_update,
                    "messages": [AIMessage(content=friendly_model_invoke_error(e))],
                },
            )
        if isinstance(response, AIMessage):
            response = self._normalize_ai_message_tool_inputs(response)
        if (
            isinstance(response, AIMessage)
            and len(getattr(response, "tool_calls", None) or []) > 0
        ):
            return Command(
                goto="call_tools", update={**routing_update, "messages": [response]}
            )
        if self._markdown_pretty_display:
            response = await self._pretty_display_markdown(response)
        return Command(
            goto="__end__", update={**routing_update, "messages": [response]}
        )

    async def _pretty_display_markdown(self, response: BaseMessage) -> BaseMessage:
        prompt = [
            SystemMessage(content=PRETTY_DISPLAY_PROMPT),
            HumanMessage(content=f"Initial content:\n{response.content}"),
        ]
        try:
            formatted_response = await self._chat_model.ainvoke(prompt)
            formatted = formatted_response.content
            if (
                not isinstance(formatted, str)
                or not formatted.strip()
                or getattr(formatted_response, "tool_calls", None)
            ):
                return response
            response.content = formatted.strip()
            return response
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Markdown pretty display failed for agent '%s': %s", self._name, e
            )
            return response

    @staticmethod
    def _merge_direct_tool_contents(messages: list[ToolMessage]) -> Any:
        if len(messages) == 1:
            return messages[0].content
        if all(isinstance(message.content, str) for message in messages):
            return "\n\n".join(
                message.content
                for message in messages
                if isinstance(message.content, str) and message.content.strip()
            )
        blocks: list[str | dict] = []
        for message in messages:
            if isinstance(message.content, str):
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
            else:
                blocks.extend(message.content)
        return blocks

    async def call_tools(self, state: ABIAgentState) -> list[Command]:
        if not isinstance(state.get("messages"), list) or not state["messages"]:
            logger.warning("No messages in state, cannot call tools")
            return [Command(goto="__end__")]
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage) or not getattr(
            last_message, "tool_calls", None
        ):
            return [Command(goto="__end__", update={"messages": [last_message]})]

        tool_calls: list[ToolCall] = last_message.tool_calls
        results: list[Command] = []
        had_tool_error = False
        called_tools: list[BaseTool] = []
        for tool_call in tool_calls:
            tool_name: str = tool_call["name"]
            tool_ = self._tools_by_name.get(tool_name)
            if tool_ is None:
                available = sorted(self._tools_by_name.keys())
                logger.error(
                    "Agent '%s' tried to call unknown tool '%s'", self._name, tool_name
                )
                had_tool_error = True
                results.append(
                    Command(
                        update={
                            "messages": [
                                ToolMessage(
                                    content=(
                                        f"Tool '{tool_name}' is not available to "
                                        f"agent '{self._name}'. Available tools: {available}"
                                    ),
                                    name=tool_name,
                                    tool_call_id=tool_call["id"],
                                )
                            ]
                        }
                    )
                )
                continue

            tool_input_fields = tool_.get_input_schema().model_json_schema()[
                "properties"
            ]
            args: dict[str, Any] | ToolCall = tool_call
            if "state" in tool_input_fields:
                args = {**tool_call, "state": state}
            try:
                tool_response = await tool_.ainvoke(args)
                called_tools.append(tool_)
                if isinstance(tool_response, ToolMessage):
                    results.append(Command(update={"messages": [tool_response]}))
                elif isinstance(tool_response, Command):
                    results.append(tool_response)
                else:
                    logger.warning(
                        "Tool call %s returned an unexpected type: %s",
                        tool_name,
                        type(tool_response),
                    )
                    results.append(
                        Command(
                            goto="__end__",
                            update={
                                "messages": [
                                    ToolMessage(
                                        content=str(tool_response),
                                        tool_call_id=tool_call["id"],
                                    )
                                ]
                            },
                        )
                    )
            except Exception as e:  # noqa: BLE001
                logger.error("Tool call %s failed: %s", tool_name, e)
                had_tool_error = True
                called_tools.append(tool_)
                results.append(
                    Command(
                        update={
                            "messages": [
                                ToolMessage(
                                    content=f"Tool call {tool_name} failed: {e!s}",
                                    name=tool_name,
                                    tool_call_id=tool_call["id"],
                                )
                            ]
                        }
                    )
                )

        return_direct = all(
            getattr(t, "return_direct", True) is not False for t in called_tools
        )
        last_tool_response = _last_update_message(results[-1])
        direct_tool_responses = [
            message
            for message in (_last_update_message(result) for result in results)
            if isinstance(message, ToolMessage)
            and isinstance(message.name, str)
            and not message.name.startswith("transfer_to_")
        ]
        if had_tool_error:
            results.append(Command(goto="call_model"))
        elif (
            isinstance(last_tool_response, ToolMessage)
            and last_tool_response.name is not None
            and not last_tool_response.name.startswith("transfer_to_")
        ):
            if not return_direct:
                results.append(Command(goto="call_model"))
            else:
                results.append(
                    Command(
                        update={
                            "messages": [
                                AIMessage(
                                    content=self._merge_direct_tool_contents(
                                        direct_tool_responses
                                    )
                                )
                            ]
                        }
                    )
                )
        return results

    # --- notifications -----------------------------------------------------------------

    def _emit(self, event: Event) -> None:
        if self._event_queue is not None:
            self._event_queue.put_nowait(event)

    def _notify_tool_usage(self, message: AnyMessage) -> None:
        self._emit(ToolUsageEvent(payload=message))
        self._on_tool_usage(message)

    def _notify_tool_response(self, message: AnyMessage) -> None:
        self._emit(ToolResponseEvent(payload=message))
        self._on_tool_response(message)

    def _notify_ai_message(self, message: AnyMessage, agent_name: str) -> None:
        self._emit(AIMessageEvent(payload=message, agent_name=agent_name))
        self._on_ai_message(message, agent_name)
        self._call_hook(self.onAImessage, message, agent_name)

    def _notify_call_model(self, agent_name: str) -> None:
        self._emit(CallModelEvent(payload=agent_name, agent_name=agent_name))
        self._on_call_model(agent_name)

    def _notify_agent_routing(self, agent_name: str) -> None:
        self._emit(AgentRoutingEvent(payload=agent_name, agent_name=agent_name))
        self._on_agent_routing(agent_name)

    def _call_hook(self, hook: Callable[..., Any], *args: Any) -> None:
        try:
            hook(*args)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Agent '%s': %s raised: %s",
                self._name,
                getattr(hook, "__name__", "hook"),
                exc,
            )

    def onHumanMessage(self, message: AnyMessage) -> None:
        """Subclass hook: a new human message entered the conversation."""

    def onAImessage(self, message: AnyMessage, agent_name: str) -> None:
        """Subclass hook: a new (non tool-call) AI message was emitted."""

    def on_tool_usage(self, callback: Callable[[AnyMessage], None]) -> None:
        self._on_tool_usage = callback

    def on_tool_response(self, callback: Callable[[AnyMessage], None]) -> None:
        self._on_tool_response = callback

    def on_ai_message(self, callback: Callable[[AnyMessage, str], None]) -> None:
        self._on_ai_message = callback

    @staticmethod
    def _tool_response_key(message: Any) -> Any:
        if isinstance(message, dict):
            return message.get("tool_call_id") or id(message)
        return getattr(message, "tool_call_id", None) or message.id or id(message)

    # --- running -------------------------------------------------------------------------

    def _stream_config(self) -> RunnableConfig:
        config: RunnableConfig = {"configurable": {"thread_id": self._state.thread_id}}
        own_limit = getattr(self, "recursion_limit", None)
        if isinstance(own_limit, int) and own_limit > 0:
            config["recursion_limit"] = own_limit
        return config

    async def stream(self, prompt: str) -> AsyncIterator[Any]:
        """Raw LangGraph chunks (``subgraphs=True``), notifying events like core."""
        human_message = HumanMessage(content=prompt)
        self._call_hook(self.onHumanMessage, human_message)
        notified: dict[Any, bool] = {}
        async for chunk in self.graph.astream(
            {"messages": [human_message]}, config=self._stream_config(), subgraphs=True
        ):
            source, payload = chunk
            agent_name = self._name if len(source) == 0 else source[0].split(":")[0]
            if isinstance(payload, dict):
                for last_message in _last_messages(payload):
                    if isinstance(last_message, AIMessage):
                        if self._has_tool_calls(last_message):
                            self._notify_tool_usage(last_message)
                        elif any(
                            node in payload for node in ("call_model", "call_tools")
                        ):
                            self._notify_ai_message(last_message, agent_name)
                    elif isinstance(last_message, ToolMessage):
                        is_handoff = isinstance(
                            last_message.name, str
                        ) and last_message.name.startswith("transfer_to_")
                        key = self._tool_response_key(last_message)
                        if key not in notified and not is_handoff:
                            self._notify_tool_response(last_message)
                            notified[key] = True
                    elif (
                        isinstance(last_message, dict)
                        and "tool_call_id" in last_message
                        and last_message["tool_call_id"] not in notified
                    ):
                        self._notify_tool_response(last_message)
                        notified[last_message["tool_call_id"]] = True
            yield chunk

    async def invoke(self, prompt: str) -> str:
        """Run one turn and return the final assistant text."""
        last_payload: dict | None = None
        async for chunk in self.stream(prompt):
            payload = chunk[1] if isinstance(chunk, tuple) else chunk
            if isinstance(payload, dict):
                last_payload = payload
        if not last_payload:
            return ""
        values = list(last_payload.values())
        if not values:
            return ""
        value = values[0]
        messages: list[Any] = []
        if isinstance(value, dict) and isinstance(value.get("messages"), list):
            messages = value["messages"]
        elif isinstance(value, list) and value:
            last_item = value[-1]
            if isinstance(last_item, dict) and isinstance(
                last_item.get("messages"), list
            ):
                messages = last_item["messages"]
        if not messages:
            return ""
        last_message = messages[-1]
        content = (
            last_message.content
            if hasattr(last_message, "content")
            else str(last_message or "")
        )
        return self._content_to_text(content)

    async def stream_invoke(self, prompt: str) -> AsyncIterator[dict[str, str]]:
        """Core's SSE event stream: steps as they happen, then the answer line by line."""
        queue: asyncio.Queue = asyncio.Queue()
        self._event_queue = queue

        async def run_invoke() -> None:
            try:
                final_state: Any = await self.invoke(prompt)
            except Exception as e:  # noqa: BLE001
                logger.exception("Agent invoke error for '%s': %s", self._name, e)
                final_state = friendly_model_invoke_error(e)
            queue.put_nowait(FinalStateEvent(payload=final_state))

        task = asyncio.create_task(run_invoke())
        try:
            final_state = None
            while True:
                message = await queue.get()
                if isinstance(message, ToolUsageEvent):
                    yield {
                        "event": "tool_usage",
                        "data": str(message.payload.tool_calls[0]["name"]),
                    }
                elif isinstance(message, ToolResponseEvent):
                    raw = str(_payload_content(message.payload))
                    yield {
                        "event": "tool_response",
                        "data": _truncate_tool_content(raw, _MAX_TOOL_RESULT_CHARS),
                    }
                elif isinstance(message, AIMessageEvent):
                    yield {
                        "event": "ai_message",
                        "data": self._content_to_text(message.payload.content),
                    }
                elif isinstance(message, CallModelEvent):
                    yield {"event": "call_model", "data": str(message.payload)}
                elif isinstance(message, AgentRoutingEvent):
                    yield {"event": "agent_routing", "data": str(message.payload)}
                elif isinstance(message, FinalStateEvent):
                    final_state = message.payload
                    break
        finally:
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        response = self._content_to_text(final_state)
        buffer = ""
        for char in response:
            buffer += char
            if char in ["\n", "\r"]:
                yield {"event": "message", "data": buffer.rstrip()}
                buffer = ""
        if buffer.strip():
            yield {"event": "message", "data": buffer}
        yield {"event": "done", "data": "[DONE]"}

    def as_handler(self) -> Any:
        """Handler for ``BaseModule.expose_agent``: one duplicate per invocation thread."""
        from naas_abi_sdk.agents.hosting import AgentHandler

        return AgentHandler(self)

    def reset(self) -> None:
        try:
            self._state.set_thread_id(str(int(self._state.thread_id) + 1))
        except (ValueError, TypeError):
            self._state.set_thread_id(str(uuid.uuid4()))

    def _populate_duplicate_shell(self, clone: Agent) -> None:
        """Copy subclass-specific fields onto a duplicate before ``build_graph``."""

    def duplicate(self, agent_shared_state: AgentSharedState | None = None) -> Agent:
        """Same configuration, models, tools and checkpointer; its own state."""
        clone = object.__new__(type(self))
        clone.__dict__.update(self.__dict__)
        clone._state = agent_shared_state or AgentSharedState()
        clone._event_queue = None
        clone._wire_callbacks()
        own_limit = getattr(self, "recursion_limit", None)
        if isinstance(own_limit, int) and own_limit > 0:
            clone.recursion_limit = own_limit
        self._populate_duplicate_shell(clone)
        clone.build_graph()
        return clone

    # --- accessors -----------------------------------------------------------------------

    @property
    def state(self) -> AgentSharedState:
        return self._state

    @property
    def tools(self) -> list[BaseTool]:
        return self._structured_tools

    @property
    def structured_tools(self) -> list[BaseTool]:
        return self._structured_tools

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def chat_model(self) -> BaseChatModel:
        return self._chat_model

    @property
    def configuration(self) -> AgentConfiguration:
        return self._configuration

    @property
    def checkpointer(self) -> BaseCheckpointSaver:
        """The saver holding this agent's threads (read-only; not on core Agent)."""
        return self._checkpointer


PRETTY_DISPLAY_PROMPT = """You are a Markdown formatting pass for AI responses.

## Objective
Reformat the input into clean, readable Markdown. Preserve all meaning and details — do not add or remove information.

## Formatting rules

- Write in prose by default. Use structure only when it genuinely improves readability.
- Bullets: only for genuinely enumerable content. Write short lists inline: "options include x, y, and z."
- Headers: only for long, document-like content. Avoid in conversational or explanatory responses.
- Bold: reserved for key terms. Not for decorative emphasis.
- Code blocks: always use for code, commands, file paths, and technical strings.
- Tables: only for structured comparisons with clear categories.
- Length: match the complexity of the content. Remove filler, padding, and restatements.

## Spacing conventions

- After a greeting: add two blank lines before continuing.
- Before a question to the user: add two blank lines above it.

## Constraints

- Return only the reformatted response — no preamble, no commentary.
- Preserve technical accuracy: warnings, links, code, commands, and citations must be kept intact.
- Preserve the language of the input.
- If the input is already well-formatted, make minimal changes."""


def _supervised_prompt(supervisor: str, system_prompt: str) -> str:
    return f"""
SUPERVISOR SYSTEM PROMPT:

Remember, you are a specialized agent working under the supervision of {supervisor}.

1. Stay focused on your specialized role and core capabilities.
2. Follow your system prompt instructions precisely.
3. For EVERY user message, first evaluate if you can handle it within your core capabilities.
4. If the user message is not clear, ask for clarification and evaluate again if you can handle it within your core capabilities.
5. If you encounter ANY of these situations:
   - You are uncertain about how to proceed
   - The task seems outside your core capabilities
   - You need clarification about requirements
   - You want to confirm a critical action
   - You are not 100% confident in your ability to handle the task
   Then you MUST use the `request_help` tool to ask your supervisor for help.
   IMPORTANT: Do NOT explain to the user that you cannot perform the task or say it is outside your scope. Instead, IMMEDIATELY and directly use `request_help`.
6. Do not attempt tasks beyond your defined role.
7. Always maintain consistency with your system prompt rules.
8. When in doubt, ALWAYS request help rather than risk mistakes. Do not type or explain your inability—just use the tool.

Your supervisor will help ensure you operate effectively within your role while providing guidance for complex scenarios.

--------------------------------

SUBAGENT SYSTEM PROMPT:

{system_prompt}
"""


def _last_update_message(command: Any) -> Any:
    update = getattr(command, "update", None)
    if isinstance(update, dict):
        messages = update.get("messages")
        if isinstance(messages, list) and messages:
            return messages[-1]
    return None


def _last_messages(payload: dict) -> list[Any]:
    value = next(iter(payload.values()), None)
    if isinstance(value, dict):
        messages = value.get("messages")
        return [messages[-1]] if isinstance(messages, list) and messages else []
    if isinstance(value, list):
        return [
            e["messages"][-1]
            for e in value
            if isinstance(e, dict)
            and isinstance(e.get("messages"), list)
            and e["messages"]
        ]
    return []


def _payload_content(payload: Any) -> Any:
    if isinstance(payload, dict):
        return payload.get("content", "NULL")
    return getattr(payload, "content", "NULL")


__all__ = ["ABIAgentState", "Agent", "AgentConfiguration", "AgentSharedState"]
