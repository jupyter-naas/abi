from __future__ import annotations

# Standard library imports for type hints
import atexit
import json
import os
import re
import threading
import uuid
from contextvars import copy_context

# Dataclass imports for configuration
from dataclasses import dataclass, field
from enum import Enum
from queue import Empty, Queue
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Dict,
    Generator,
    Literal,
    Optional,
    Sequence,
    Union,
    cast,
)

import pydash as pd
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, StructuredTool, Tool, tool
from langgraph.prebuilt import InjectedState
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.utils.Expose import Expose
from naas_abi_core.utils.Logger import logger

# Pydantic imports for schema validation (keep - it's already loaded by other modules)
from pydantic import BaseModel, Field

# Only import heavy modules for type checking
if TYPE_CHECKING:
    from fastapi import APIRouter
    from langchain_core.runnables import Runnable
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.types import Command
from naas_abi_core.engine.context import get_default_event_service
from naas_abi_core.services.agent.context import (
    agent_chat_id,
    agent_user_id,
    agent_workspace_id,
    coder_workspace_base,
)
from naas_abi_core.services.agent.ontologies.modules.AgentEventOntology import (
    AgentAIMessageEmitted,
    AgentInvocationCompleted,
    AgentModelCalled,
    AgentRouted,
    AgentToolCalled,
    AgentToolResponded,
    AgentUserMessageReceived,
)
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from sse_starlette.sse import EventSourceResponse

from .tools.default_tools import default_tools
from .tools.utils import can_bind_tools
from .tools.workspace_tools import REQUIRES_WORKSPACE_KEY

cache = CacheFactory.CacheFS_find_storage(subpath="agent")

_shared_checkpointer: BaseCheckpointSaver | None = None
_shared_checkpointer_url: str | None = None
_shared_postgres_connection: Any | None = None
_shared_checkpointer_lock = threading.Lock()


def _close_shared_checkpointer() -> None:
    global _shared_checkpointer
    global _shared_checkpointer_url
    global _shared_postgres_connection

    conn = _shared_postgres_connection
    _shared_checkpointer = None
    _shared_checkpointer_url = None
    _shared_postgres_connection = None

    if conn is None:
        return

    try:
        if getattr(conn, "closed", False) is False:
            conn.close()
            logger.debug("Closed shared PostgreSQL checkpointer connection")
    except Exception as e:
        logger.warning(f"Failed to close shared checkpointer connection: {e}")


def close_shared_checkpointer() -> None:
    with _shared_checkpointer_lock:
        _close_shared_checkpointer()


def _reset_shared_checkpointer_for_tests() -> None:
    close_shared_checkpointer()


atexit.register(_close_shared_checkpointer)


def create_checkpointer() -> BaseCheckpointSaver:
    """Create a checkpointer based on environment configuration.

    Returns a PostgreSQL-backed checkpointer if POSTGRES_URL is set,
    otherwise returns an in-memory checkpointer.
    """
    postgres_url = os.getenv("POSTGRES_URL")

    if postgres_url:
        global _shared_checkpointer
        global _shared_checkpointer_url
        global _shared_postgres_connection

        with _shared_checkpointer_lock:
            if (
                _shared_checkpointer is not None
                and _shared_checkpointer_url == postgres_url
            ):
                # logger.debug("Reusing shared PostgreSQL checkpointer")
                return _shared_checkpointer

            if (
                _shared_checkpointer is not None
                and _shared_checkpointer_url is not None
                and _shared_checkpointer_url != postgres_url
            ):
                logger.warning(
                    "POSTGRES_URL changed at runtime, recreating shared checkpointer"
                )
                _close_shared_checkpointer()

            try:
                import time

                from langgraph.checkpoint.postgres import PostgresSaver
                from psycopg import Connection
                from psycopg.rows import dict_row

                # logger.debug(
                #     f"Using PostgreSQL checkpointer for persistent memory: {postgres_url}"
                # )

                # Try connection with retries (PostgreSQL might still be starting)
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Create connection with proper configuration (matching from_conn_string)
                        conn = Connection.connect(
                            postgres_url,
                            autocommit=True,
                            prepare_threshold=0,
                            row_factory=dict_row,
                        )
                        checkpointer = PostgresSaver(conn)

                        # Setup tables if they don't exist
                        checkpointer.setup()
                        # logger.debug("PostgreSQL checkpointer tables initialized")

                        _shared_checkpointer = checkpointer
                        _shared_checkpointer_url = postgres_url
                        _shared_postgres_connection = conn

                        return checkpointer

                    except Exception as conn_error:
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"PostgreSQL connection attempt {attempt + 1} failed, retrying in 2 seconds..."
                            )
                            time.sleep(2)
                        else:
                            raise conn_error

            except ImportError:
                logger.error(
                    "PostgreSQL checkpointer requested but langgraph.checkpoint.postgres not available. Falling back to in-memory."
                )
            except Exception as e:
                error_msg = str(e)
                if "nodename nor servname provided" in error_msg:
                    logger.error(
                        f"PostgreSQL connection failed - cannot resolve hostname. Check if PostgreSQL is running and hostname is correct in POSTGRES_URL: {postgres_url}"
                    )
                    logger.error(
                        "Hint: If running outside Docker, use 'localhost' instead of 'postgres' in POSTGRES_URL"
                    )
                else:
                    logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}")
                logger.error("Falling back to in-memory checkpointer")

        # Fallback to in-memory checkpointer
        return MemorySaver()
    else:
        # logger.debug(
        #     "Using in-memory checkpointer (set POSTGRES_URL for persistent memory)"
        # )
        return MemorySaver()


class AgentSharedState:
    _thread_id: str
    _current_active_agent: Optional[str]
    _supervisor_agent: Optional[str]
    _requesting_help: bool
    _active_agent_by_thread: dict[str, Optional[str]]

    def __init__(
        self,
        thread_id: str = "1",
        current_active_agent: Optional[str] = None,
        supervisor_agent: Optional[str] = None,
    ):
        assert isinstance(thread_id, str)

        self._thread_id = thread_id
        self._current_active_agent = current_active_agent
        self._supervisor_agent = supervisor_agent
        self._requesting_help = False
        self._active_agent_by_thread = {thread_id: current_active_agent}

    @property
    def thread_id(self) -> str:
        return self._thread_id

    def set_thread_id(self, thread_id: str):
        if thread_id == self._thread_id:
            return
        # Persist current routing for the outgoing thread.
        self._active_agent_by_thread[self._thread_id] = self._current_active_agent
        self._thread_id = thread_id
        # Restore routing for the incoming thread (None if never seen).
        self._current_active_agent = self._active_agent_by_thread.get(thread_id)

    @property
    def current_active_agent(self) -> Optional[str]:
        return self._current_active_agent

    def set_current_active_agent(self, agent_name: Optional[str]):
        if agent_name is None:
            self._current_active_agent = None
        else:
            self._current_active_agent = Agent.validate_name(agent_name)
        self._active_agent_by_thread[self._thread_id] = self._current_active_agent

    @property
    def supervisor_agent(self) -> Optional[str]:
        return self._supervisor_agent

    def set_supervisor_agent(self, agent_name: Optional[str]):
        if agent_name is None:
            self._supervisor_agent = None
        else:
            self._supervisor_agent = Agent.validate_name(agent_name)

    @property
    def requesting_help(self) -> bool:
        return self._requesting_help

    def set_requesting_help(self, requesting_help: bool):
        self._requesting_help = requesting_help


class ABIAgentState(MessagesState):
    system_prompt: str
    # Routing state persisted through the LangGraph checkpointer so that agent
    # delegation survives across separate HTTP turns (each turn rebuilds the
    # agent tree with a fresh AgentSharedState, so in-memory routing alone is
    # lost between requests).
    current_active_agent: Optional[str]
    supervisor_agent: Optional[str]


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
        default="You are a helpful assistant. If a tool you used did not return the result you wanted, look for another tool that might be able to help you. If you don't find a suitable tool. Just output 'I DONT KNOW'"
    )

    def get_system_prompt(self, messages: list[AnyMessage]) -> str:
        return (
            self.system_prompt(messages)
            if callable(self.system_prompt)
            else self.system_prompt
        )


class CompletionQuery(BaseModel):
    prompt: str = Field(..., description="The prompt to send to the agent")
    thread_id: str | int = Field(
        ..., description="The thread ID to use for the conversation"
    )


class Agent(Expose):
    """An Agent class that orchestrates interactions between a language model and tools.

    Performance Features:
        • Lazy Initialization: Efficient resource utilization through lazy loading
        • Connection Pooling: Optimized database connections for memory backends
        • Parallel Execution: Concurrent tool execution where dependencies allow
        • Caching: Intelligent caching of tool results and model responses
        • Resource Management: Proper cleanup and resource management

    Attributes:
        _name (str): Unique identifier for the agent
        _description (str): Human-readable description of the agent's purpose
        _chat_model (BaseChatModel): The underlying language model with tool binding
        _chat_model_with_tools (Runnable): Language model configured with available tools
        _tools (list[Union[Tool, Agent]]): Original list of provided tools and agents
        _structured_tools (list[Union[Tool, BaseTool]]): Processed and validated tools
        _tools_by_name (dict[str, Union[Tool, BaseTool]]): Tool lookup dictionary
        _native_tools (list[dict]): Native tools compatible with the language model
        _agents (list[Agent]): List of sub-agents for delegation
        _checkpointer (BaseCheckpointSaver): Memory backend for conversation persistence
        _state (AgentSharedState): Shared state management for conversation threads
        graph (CompiledStateGraph): Compiled workflow graph for conversation execution
        _configuration (AgentConfiguration): Configuration settings for agent behavior
        _event_queue (Queue): Event queue for real-time event streaming
        _chat_model_output_version (str|None): Version identifier for model output format
    """

    _name: str
    _description: str

    _chat_model: BaseChatModel
    _chat_model_with_tools: Runnable[
        Any
        | str
        | Sequence[BaseMessage | list[str] | tuple[str, str] | str | dict[str, Any]],
        BaseMessage,
    ]
    _chat_model_without_workspace_tools: Runnable[
        Any
        | str
        | Sequence[BaseMessage | list[str] | tuple[str, str] | str | dict[str, Any]],
        BaseMessage,
    ]
    _tools: list[Union[Tool, BaseTool, "Agent"]]
    _original_tools: list[Union[Tool, BaseTool, "Agent"]]
    _tools_by_name: dict[str, Union[Tool, BaseTool]]
    _native_tools: list[dict]
    _enable_default_tools: bool

    # An agent can have other agents.
    # He will be responsible to load them as tools.
    _agents: list["Agent"] = []

    # Opt-in: when True, this agent is a *sequential supervisor*. Its sub-agents
    # return control to it when they finish (instead of ending the turn), so it can
    # delegate to them one after another in a single turn. Applied in __init__ so it
    # survives per-request reconstruction (as_api / duplicate rebuild fresh state).
    sequential_supervisor: bool = False

    # Set on a *sub-agent instance* by a sequential_supervisor parent to the parent's
    # name. Purely per-instance (never the shared state, which is tree-wide and would
    # corrupt sibling agents). When set, call_model returns control to that supervisor
    # on completion instead of ending the turn.
    _returns_to_supervisor: Optional[str] = None

    _chekpointer: BaseCheckpointSaver
    _state: AgentSharedState

    graph: CompiledStateGraph
    _workflow: StateGraph
    _configuration: AgentConfiguration

    _on_tool_usage: Callable[[AnyMessage], None]
    _on_tool_response: Callable[[AnyMessage], None]
    _on_ai_message: Callable[[AnyMessage, str], None]

    # Avent queue used to stream tool usage and responses.
    _event_queue: Queue

    _chat_model_output_version: Union[str, None] = None
    _markdown_pretty_display: bool

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "Agent":
        """Create a new instance of the agent.

        Args:
            agent_shared_state: Optional[AgentSharedState]: The shared state of the agent.
            agent_configuration: Optional[AgentConfiguration]: The configuration of the agent.

        Returns:
            Agent: A new instance of the agent.
        """
        raise NotImplementedError("This method is not implemented")

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        parts.append(text)
                        continue
                    reasoning = item.get("reasoning_content")
                    if isinstance(reasoning, dict):
                        reasoning_text = reasoning.get("text")
                        if isinstance(reasoning_text, str) and reasoning_text:
                            continue
                    content_text = item.get("content")
                    if isinstance(content_text, str) and content_text:
                        parts.append(content_text)
                        continue
                elif isinstance(item, str) and item:
                    parts.append(item)
            if parts:
                return "\n".join(parts)
            return ""
        return str(content)

    @staticmethod
    def _has_tool_calls(message: AnyMessage) -> bool:
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            return True
        return bool(pd.get(message, "additional_kwargs.tool_calls"))

    def __init__(
        self,
        name: str,
        description: str,
        chat_model: BaseChatModel | ChatModel,
        tools: list[Union[Tool, BaseTool, "Agent"]] = [],
        agents: list["Agent"] = [],
        memory: BaseCheckpointSaver | None = None,
        state: AgentSharedState = AgentSharedState(),
        configuration: AgentConfiguration = AgentConfiguration(),
        event_queue: Queue | None = None,
        native_tools: list[dict] = [],
        enable_default_tools: bool = True,
        markdown_pretty_display: bool = False,
    ):
        """Initialize a new Agent instance.

        Args:
            chat_model (BaseChatModel): The language model to use for chat interactions.
                Should support tool binding.
            tools (list[Tool]): List of tools to make available to the agent.
            memory (BaseCheckpointSaver, optional): Component to save conversation state.
                If None, will use PostgreSQL if POSTGRES_URL env var is set, otherwise in-memory.
        """
        self._name = Agent.validate_name(name)
        logger.debug(f"'{self._name}' is being initialized")
        self._description = description
        self._markdown_pretty_display = markdown_pretty_display
        self._state = state
        self._original_tools = tools
        self._original_agents = agents

        # We set the supervisor agent and current active agent before the default tools are injected.
        if (
            self._state.supervisor_agent is not None
            and self._name != self._state.supervisor_agent
        ):
            self._state.set_supervisor_agent(self._state.supervisor_agent)
            logger.debug(
                f"'{self._name}' has supervisor agent '{self._state.supervisor_agent}'"
            )

        # Add tool request help if the agent has a supervisor agent.
        @tool(return_direct=True)
        def request_help(reason: str):
            """
            Request help from the supervisor agent when you (the LLM) are uncertain about the next step or do not have the required capability to fulfill the user's request.

            Use this tool if:
            - You are unsure how to proceed.
            - You lack the necessary knowledge or ability to complete the task.
            - The user's request is outside your capabilities or unclear.

            Args:
                reason (str): A brief explanation of why you are requesting help (e.g., "I am uncertain about the next step", "I do not have the required capability", "The user's request is unclear").

            The supervisor agent will review your reason and provide assistance or take over the conversation.
            """
            logger.debug(f"'{self.name}' is requesting help from the supervisor agent")
            return f"Requesting help from the supervisor agent because {reason}."

        has_supervisor = (
            self._state.supervisor_agent is not None
            and self._state.supervisor_agent.strip() != ""
            and self._state.supervisor_agent != self._name
        )
        if has_supervisor:
            tools.append(request_help)

        # We validate the names of the agents.
        agent_names: list[str] = [
            Agent.validate_name(agent.name) for agent in self._original_agents
        ] + [self._name]
        if (
            self._state.current_active_agent is not None
            and self._state.current_active_agent in agent_names
        ):
            self._state.set_current_active_agent(self._state.current_active_agent)
            logger.debug(
                f"'{self._name}' has current active agent '{self._state.current_active_agent}'"
            )

        # We inject default tools
        self._enable_default_tools = enable_default_tools
        if self._enable_default_tools:
            tools += default_tools(self)

        # We store the original list of provided tools. This will be usefull for duplication.
        self._tools = tools
        self._native_tools = native_tools

        # Assertions
        assert isinstance(name, str)
        assert isinstance(description, str)
        assert isinstance(chat_model, BaseChatModel | ChatModel)

        # We store the provided tools in __structured_tools because we will need to know which ones are provided by the user and which one are agents.
        # This is needed when we duplicate the agent.
        _structured_tools, _agents = self.prepare_tools(
            cast(list[Union[Tool, BaseTool, "Agent"]], tools), self._original_agents
        )
        self._structured_tools = _structured_tools
        self._agents = _agents

        # Sequential-supervisor wiring (opt-in via the class attribute). Tag each
        # sub-agent *instance* (not the shared state — that is tree-wide and shared
        # with any outer supervisor like AbiAgent, so mutating it corrupts siblings)
        # with this agent's name, so that when the sub-agent finishes it returns
        # control here instead of ending the turn (see call_model). Re-applied on
        # every reconstruction because __init__ runs on duplicate/as_api.
        if getattr(self, "sequential_supervisor", False):
            for _sub_agent in self._agents:
                if _sub_agent.name != self._name:
                    _sub_agent._returns_to_supervisor = self._name

        # We assert that the tool that are provided are valid.
        for t in self._structured_tools:
            assert isinstance(t, StructuredTool)
            assert hasattr(t, "name")
            assert hasattr(t, "description")
            assert hasattr(t, "func")
            assert hasattr(t, "args_schema")

        self._tools_by_name: dict[str, Union[Tool, BaseTool]] = {
            tool.name: tool for tool in self._structured_tools
        }

        base_chat_model: BaseChatModel = (
            chat_model if isinstance(chat_model, BaseChatModel) else chat_model.model
        )
        assert isinstance(base_chat_model, BaseChatModel)

        self._chat_model = base_chat_model
        if hasattr(base_chat_model, "output_version"):
            self._chat_model_output_version = base_chat_model.output_version

        self._chat_model_with_tools = base_chat_model
        # Variant bound WITHOUT context-gated tools (e.g. coding-workspace tools),
        # used when the current request is not tied to a workspace so the model
        # never sees tools it cannot use. Falls back to the full model when there
        # are no gated tools to strip.
        self._chat_model_without_workspace_tools = base_chat_model
        if self._tools or self._native_tools:
            tools_to_bind: list[Union[Tool, BaseTool, Dict]] = []
            tools_to_bind.extend(self._structured_tools)
            tools_to_bind.extend(self._native_tools)

            # Test if the chat model can bind tools by trying with a default tool first
            if can_bind_tools(base_chat_model):
                self._chat_model_with_tools = base_chat_model.bind_tools(tools_to_bind)
                gated = [
                    t for t in tools_to_bind if not Agent._requires_workspace(t)
                ]
                self._chat_model_without_workspace_tools = (
                    base_chat_model.bind_tools(gated)
                    if len(gated) != len(tools_to_bind)
                    else self._chat_model_with_tools
                )
            else:
                logger.warning(
                    f"Chat model {type(base_chat_model).__name__} does not support tool calling. Tools will not be available for agent '{self._name}'."
                )
                # Keep the original model without tools
                self._chat_model_with_tools = base_chat_model
                self._chat_model_without_workspace_tools = base_chat_model

        # Use provided memory or create based on environment
        if memory is None:
            self._checkpointer = create_checkpointer()
        else:
            self._checkpointer = memory

        # Randomize the thread_id to prevent the same thread_id to be used by multiple agents.
        if os.getenv("ENV") == "dev":
            self._state.set_thread_id(str(uuid.uuid4()))

        # We set the configuration.
        self._configuration = configuration
        self._on_tool_usage = configuration.on_tool_usage
        self._on_tool_response = configuration.on_tool_response
        self._on_ai_message = configuration.on_ai_message
        self._on_call_model = configuration.on_agent_calling
        self._on_agent_routing = configuration.on_agent_routing

        # Initialize the event queue.
        if event_queue is None:
            self._event_queue = Queue()
        else:
            self._event_queue = event_queue
        self._sync_event_queue_with_subagents()

        # We build the graph.
        self.build_graph()

    @property
    def structured_tools(self) -> list[Tool | BaseTool]:
        return self._structured_tools

    @property
    def state(self) -> AgentSharedState:
        return self._state

    @cache(lambda name: f"validate_name_{name}", cache_type=DataType.TEXT)
    @staticmethod
    def validate_name(name: str) -> str:
        # Only allow characters valid for graph node names (e.g. ':' is reserved and not allowed).
        pattern = r"^[a-zA-Z0-9_-]+$"
        if not re.match(pattern, name):
            # Replace invalid/reserved characters (including ':') with '_'
            valid_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
            # logger.debug(
            #     f"Name '{name}' does not match pattern '{pattern}' (e.g. ':' is reserved). Renaming to '{valid_name}'."
            # )
            return valid_name.replace("__", "_")
        return name

    @staticmethod
    def validate_tool_name(tool: BaseTool) -> BaseTool:
        tool.name = Agent.validate_name(tool.name)
        return tool

    @staticmethod
    def _requires_workspace(tool: Union[Tool, BaseTool, Dict]) -> bool:
        """A tool is workspace-gated when its metadata declares it. Such tools
        are only exposed to the model when a coding workspace is bound to the
        current request."""
        metadata = getattr(tool, "metadata", None)
        return bool(metadata and metadata.get(REQUIRES_WORKSPACE_KEY))

    @staticmethod
    def validate_agent_name(agent: Agent) -> Agent:
        agent._name = Agent.validate_name(agent.name)
        return agent

    def prepare_tools(
        self, tools: list[Union[Tool, BaseTool, "Agent"]], agents: list[Agent]
    ) -> tuple[list[Tool | BaseTool], list["Agent"]]:
        """
        If we have Agents in tools, we are properly loading them as handoff tools.
        It will effectively make the 'self' agent a supervisor agent.

        Ensures no duplicate tools or agents are added by tracking unique names/instances.
        """
        _tools: list[Tool | BaseTool] = []
        _agents: list["Agent"] = []
        _tool_names: set[str] = set()
        _agent_names: set[str] = set()

        # We process tools knowing that they can either be StructutedTools or Agent.
        for t in tools:
            if isinstance(t, Agent):
                # TODO: We might want to duplicate the agent first.
                # logger.debug(f"Agent passed as tool: {t}")
                if t.name not in _agent_names:
                    _agents.append(t)
                    _agent_names.add(t.name)
                    for tool in t.as_tools():
                        tool = Agent.validate_tool_name(tool)
                        if tool.name not in _tool_names:
                            _tools.append(tool)
                            _tool_names.add(tool.name)
            else:
                # Accept both Tool and BaseTool
                if hasattr(t, "name"):
                    t = Agent.validate_tool_name(t)
                    if t.name not in _tool_names:
                        _tools.append(t)
                        _tool_names.add(t.name)

        # We process agents that are not provided in tools.
        for agent in agents:
            if agent.name not in _agent_names:
                _agents.append(agent)
                _agent_names.add(agent.name)
                for tool in agent.as_tools():
                    tool = Agent.validate_tool_name(tool)
                    if tool.name not in _tool_names:
                        _tools.append(tool)
                        _tool_names.add(tool.name)

        return _tools, _agents

    def as_tools(self, parent_graph: bool = False) -> list[BaseTool]:
        return [make_handoff_tool(agent=self, parent_graph=parent_graph)]

    def build_graph(self, patcher: Optional[Callable] = None):
        graph = StateGraph(ABIAgentState)

        graph.add_node(self.render_system_prompt)
        graph.add_edge(START, "render_system_prompt")

        graph.add_node(self.current_active_agent)
        graph.add_edge("render_system_prompt", "current_active_agent")

        graph.add_node(self.continue_conversation)

        graph.add_node(self.call_model)

        graph.add_node(self.call_tools)

        for agent in self._agents:
            agent = self.validate_agent_name(agent)
            logger.debug(f"Adding sub-agent '{agent._name}' to graph '{self._name}'")
            graph.add_node(agent._name, agent.graph)

        # Patcher is callable that can be passed and that will impact the graph before we compile it.
        # This is used to be able to give more flexibility about how the graph is being built.
        if patcher:
            graph = patcher(graph)

        self.graph = graph.compile(checkpointer=self._checkpointer)

    def render_system_prompt(self, state: ABIAgentState) -> Command:
        system_prompt = self._configuration.get_system_prompt(state["messages"])
        return Command(update={"system_prompt": system_prompt})

    def get_last_human_message(self, state: ABIAgentState) -> Any | None:
        """Get the appropriate human message based on AI message context.

        Args:
            state (ABIAgentState): Current conversation state

        Returns:
            Any | None: The relevant human message
        """
        last_ai_message: Any | None = pd.find(
            state["messages"][::-1], lambda m: isinstance(m, AIMessage)
        )
        if (
            last_ai_message is not None
            and last_ai_message.additional_kwargs.get("owner") == self.name
        ):
            return pd.find(
                state["messages"][::-1], lambda m: isinstance(m, HumanMessage)
            )
        elif (
            last_ai_message is not None
            and hasattr(last_ai_message, "additional_kwargs")
            and last_ai_message.additional_kwargs is not None
            and "owner" in last_ai_message.additional_kwargs
        ):
            return pd.filter_(
                state["messages"][::-1], lambda m: isinstance(m, HumanMessage)
            )[1]
        else:
            return pd.find(
                state["messages"][::-1], lambda m: isinstance(m, HumanMessage)
            )

    def current_active_agent(self, state: ABIAgentState) -> Command:
        """Goto the current active agent.

        Args:
            state (ABIAgentState): Current conversation state

        Returns:
            Command: Command to goto the current active agent
        """
        # Restore routing from the checkpointed graph state. Within a single
        # long-lived instance ``self._state`` is already authoritative, so we
        # only hydrate when it is empty — which is exactly the case at the start
        # of a new HTTP turn, where the agent tree was freshly duplicated with a
        # blank AgentSharedState. This is what makes a prior handoff survive
        # across requests instead of falling back to the supervisor every turn.
        persisted_active = state.get("current_active_agent")
        if persisted_active is not None and self._state.current_active_agent is None:
            self._state.set_current_active_agent(persisted_active)
        persisted_supervisor = state.get("supervisor_agent")
        if persisted_supervisor is not None and self._state.supervisor_agent is None:
            self._state.set_supervisor_agent(persisted_supervisor)

        # Log the current active agent
        logger.debug(f"😏 Supervisor agent: '{self._state.supervisor_agent}'")
        logger.debug(f"🟢 Active agent: '{self._state.current_active_agent}'")
        logger.debug(f"🤖 Current Agent: '{self._name}'")

        # Get the last human message
        last_human_message = self.get_last_human_message(state)

        # Handle agent routing via @mention
        if (
            last_human_message is not None
            and isinstance(last_human_message.content, str)
            and last_human_message.content.startswith("@")
            and last_human_message.content.split(" ")[0].split("@")[1] != self.name
        ):
            at_mention = last_human_message.content.split(" ")[0].split("@")[1]
            logger.debug(f"🔀 Handle agent routing via @mention to '{at_mention}'")

            # Check if we have an agent with this name.
            agent = pd.find(
                self._agents, lambda a: a.name.lower() == at_mention.lower()
            )

            # Remove mention from the last human message with re.sub
            import re

            last_human_message.content = re.sub(
                r"^@[^ ]* ", "", last_human_message.content
            )

            if agent is not None:
                agent_name = Agent.validate_name(agent.name)
                self._state.set_current_active_agent(agent_name)
                self._notify_agent_routing(agent_name)
                return Command(
                    goto=agent_name,
                    update={
                        "messages": state["messages"],
                        "current_active_agent": agent_name,
                    },
                )
            else:
                logger.debug(f"❌ Agent '{at_mention}' not found")

        if (
            self._state.current_active_agent is not None
            and self._state.current_active_agent != self._name
        ):
            logger.debug(
                f"⏩ Continuing conversation with: '{self._state.current_active_agent}'"
            )
            # self._notify_agent_routing(self._state.current_active_agent)
            return Command(goto=self._state.current_active_agent)

        # self._state.set_current_active_agent(self.name)
        logger.debug(f"💬 Starting chatting with: '{self._name}'")
        updated_system_prompt = state["system_prompt"]
        if (
            self.state.supervisor_agent is not None
            and self.state.supervisor_agent.strip() != ""
            and self.state.supervisor_agent != self.name
            and "SUPERVISOR SYSTEM PROMPT" not in state["system_prompt"]
        ):
            # This agent is a subagent with a supervisor
            subagent_prompt = f"""
SUPERVISOR SYSTEM PROMPT:

Remember, you are a specialized agent working under the supervision of {self.state.supervisor_agent}.

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

{state["system_prompt"]}
"""
            updated_system_prompt = subagent_prompt

        if "CURRENT_DATE" not in state["system_prompt"]:
            from datetime import datetime

            current_date_str = f"CURRENT_DATE: The current date is {datetime.now().strftime('%Y-%m-%d')}\n"
            # self._system_prompt = self._system_prompt + "\n" + current_date_str
            updated_system_prompt = updated_system_prompt + "\n" + current_date_str
            return Command(
                goto="continue_conversation",
                update={"system_prompt": updated_system_prompt},
            )

        # logger.debug(f"💬 System prompt: {self._system_prompt}")
        return Command(
            goto="continue_conversation",
            update={"system_prompt": updated_system_prompt},
        )

    def continue_conversation(self, state: ABIAgentState) -> Command:
        return Command(goto="call_model")

    def _pretty_display_markdown(
        self,
        response: BaseMessage,
    ) -> BaseMessage:
        prompt = [
            SystemMessage(
                content=(
                    """You are a Markdown formatting pass for AI responses.

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
                )
            ),
            HumanMessage(content=(f"Initial content:\n{response.content}")),
        ]

        try:
            formatted_response = self._chat_model_with_tools.invoke(prompt)
            logger.debug(
                f"Markdown pretty display response: {formatted_response.content}"
            )

            if not isinstance(formatted_response.content, str):
                return response

            response.content = formatted_response.content.strip()
            return response
        except Exception as e:
            logger.warning(
                f"Markdown pretty display failed for agent '{self._name}': {e}"
            )
            return response

    @staticmethod
    def _coerce_tool_args_to_object(args: Any) -> dict[str, Any]:
        """Ensure tool-call args are a JSON object (``dict``).

        Providers such as Amazon Bedrock Converse reject ``toolUse.input`` unless
        it is a JSON object. Some models (notably OpenAI OSS models on Bedrock)
        emit empty lists, empty strings, ``None``, or JSON-encoded strings for
        zero-argument tools. Coerce those shapes so any default chat model can
        safely continue a tool-calling turn.
        """
        if args is None:
            return {}
        if isinstance(args, dict):
            return args
        if isinstance(args, str):
            text = args.strip()
            if not text:
                return {}
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        if isinstance(args, (list, tuple)):
            # boto3 Document decoding historically turns ``{}`` into ``[]``.
            if len(args) == 0:
                return {}
            if len(args) == 1 and isinstance(args[0], dict):
                return args[0]
            return {}
        return {}

    @classmethod
    def _normalize_ai_message_tool_inputs(cls, message: AIMessage) -> AIMessage:
        """Rewrite an AIMessage so every tool input is a dict object."""
        tool_calls = list(getattr(message, "tool_calls", None) or [])
        normalized_calls: list[ToolCall] = []
        calls_changed = False
        for call in tool_calls:
            if not isinstance(call, dict):
                normalized_calls.append(call)
                continue
            coerced = cls._coerce_tool_args_to_object(call.get("args"))
            if coerced is not call.get("args"):
                calls_changed = True
                normalized_calls.append({**call, "args": coerced})
            else:
                normalized_calls.append(call)

        content = message.content
        content_changed = False
        if isinstance(content, list):
            new_blocks: list[Any] = []
            for block in content:
                if not isinstance(block, dict):
                    new_blocks.append(block)
                    continue
                # LangChain uses type=tool_use; Bedrock wire form uses toolUse.
                if block.get("type") == "tool_use":
                    coerced_input = cls._coerce_tool_args_to_object(block.get("input"))
                    if coerced_input is not block.get("input"):
                        content_changed = True
                        new_blocks.append({**block, "input": coerced_input})
                    else:
                        new_blocks.append(block)
                elif "toolUse" in block:
                    tool_use = block.get("toolUse") or {}
                    coerced_input = cls._coerce_tool_args_to_object(
                        tool_use.get("input")
                    )
                    if coerced_input is not tool_use.get("input"):
                        content_changed = True
                        new_blocks.append(
                            {
                                **block,
                                "toolUse": {**tool_use, "input": coerced_input},
                            }
                        )
                    else:
                        new_blocks.append(block)
                else:
                    new_blocks.append(block)
            if content_changed:
                content = new_blocks

        additional_kwargs = dict(getattr(message, "additional_kwargs", None) or {})
        kwargs_changed = False
        raw_tool_calls = additional_kwargs.get("tool_calls")
        if isinstance(raw_tool_calls, list):
            new_raw: list[Any] = []
            for call in raw_tool_calls:
                if not isinstance(call, dict):
                    new_raw.append(call)
                    continue
                # OpenAI-style nested function.arguments may be a JSON string.
                function = call.get("function")
                if isinstance(function, dict) and "arguments" in function:
                    arguments = function.get("arguments")
                    if isinstance(arguments, str):
                        coerced = cls._coerce_tool_args_to_object(arguments)
                        encoded = json.dumps(coerced)
                        if encoded != arguments:
                            kwargs_changed = True
                            new_raw.append(
                                {
                                    **call,
                                    "function": {**function, "arguments": encoded},
                                }
                            )
                        else:
                            new_raw.append(call)
                    elif not isinstance(arguments, dict):
                        kwargs_changed = True
                        new_raw.append(
                            {
                                **call,
                                "function": {
                                    **function,
                                    "arguments": json.dumps(
                                        cls._coerce_tool_args_to_object(arguments)
                                    ),
                                },
                            }
                        )
                    else:
                        new_raw.append(call)
                elif "args" in call:
                    coerced = cls._coerce_tool_args_to_object(call.get("args"))
                    if coerced is not call.get("args"):
                        kwargs_changed = True
                        new_raw.append({**call, "args": coerced})
                    else:
                        new_raw.append(call)
                else:
                    new_raw.append(call)
            if kwargs_changed:
                additional_kwargs["tool_calls"] = new_raw

        if not (calls_changed or content_changed or kwargs_changed):
            return message

        return AIMessage(
            content=content,
            tool_calls=normalized_calls,
            id=message.id,
            additional_kwargs=additional_kwargs,
            response_metadata=dict(getattr(message, "response_metadata", None) or {}),
            usage_metadata=getattr(message, "usage_metadata", None),
            name=getattr(message, "name", None),
        )

    @classmethod
    def _normalize_tool_inputs_in_messages(
        cls, messages: list[AnyMessage]
    ) -> list[AnyMessage]:
        """Normalize tool inputs across a message history before model invoke."""
        normalized: list[AnyMessage] = []
        changed = False
        for message in messages:
            if isinstance(message, AIMessage):
                new_message = cls._normalize_ai_message_tool_inputs(message)
                if new_message is not message:
                    changed = True
                normalized.append(new_message)
            else:
                normalized.append(message)
        return normalized if changed else messages

    def _strip_inbound_handoff_artifacts(
        self, messages: list[AnyMessage]
    ) -> list[AnyMessage]:
        """Hide the parent's `transfer_to_<self>` call/response pair from the sub-agent's LLM.

        When a supervisor hands off to this agent, two artifacts end up in the
        propagated message history:
        1. An AIMessage carrying a ``transfer_to_<self>`` tool_call (from the
           supervisor's LLM).
        2. A ToolMessage with content ``__handoff__:<self>`` produced by
           ``make_handoff_tool``.

        Both are plumbing the sub-agent's LLM does not need to see, and the
        second one in particular reads as a success signal — small models
        pattern-match it to "task complete, just respond" and skip the real
        tool call (the symptom: a fabricated success message with no
        underlying tool result). This helper removes both so the sub-agent
        sees a clean user/assistant transcript.

        Outbound handoffs that this agent emitted itself (to its OWN
        sub-agents) are left untouched.

        The original ``state["messages"]`` is not mutated — this only adjusts
        what the LLM sees on this turn.
        """
        if not messages:
            return messages

        target_name = f"transfer_to_{self._name}"
        inbound_ids: set[str] = set()
        for m in messages:
            if (
                isinstance(m, ToolMessage)
                and isinstance(getattr(m, "name", None), str)
                and m.name == target_name
            ):
                tcid = getattr(m, "tool_call_id", None)
                if isinstance(tcid, str):
                    inbound_ids.add(tcid)

        if not inbound_ids:
            return messages

        def _strip_content_tool_use(content: Any) -> Any:
            """Drop tool_use blocks whose id is inbound from list-form content.

            Anthropic extended-thinking responses carry ``content`` as a list of
            blocks (``thinking`` / ``text`` / ``tool_use``). The ``tool_use``
            block is the raw counterpart of a ``tool_calls`` entry; removing the
            entry from ``.tool_calls`` alone leaves the block in ``content``,
            which the API then rejects as a ``tool_use`` with no ``tool_result``.
            """
            if not isinstance(content, list):
                return content
            return [
                b
                for b in content
                if not (
                    isinstance(b, dict)
                    and b.get("type") == "tool_use"
                    and b.get("id") in inbound_ids
                )
            ]

        def _content_effectively_empty(content: Any) -> bool:
            """True when content has no user-visible text and no tool_use block.

            Bare ``thinking`` / ``redacted_thinking`` blocks are plumbing, not a
            standalone assistant turn, so a message left with only those (after
            the tool_use is stripped) should be dropped entirely.
            """
            if not content:
                return True
            if isinstance(content, str):
                return not content.strip()
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict):
                        btype = b.get("type")
                        if btype == "text" and (b.get("text") or "").strip():
                            return False
                        if btype == "tool_use":
                            return False
                    elif isinstance(b, str) and b.strip():
                        return False
                return True
            return False

        cleaned: list[AnyMessage] = []
        for m in messages:
            if (
                isinstance(m, ToolMessage)
                and getattr(m, "tool_call_id", None) in inbound_ids
            ):
                continue
            if isinstance(m, AIMessage):
                tool_calls = list(getattr(m, "tool_calls", None) or [])
                kept = [tc for tc in tool_calls if tc.get("id") not in inbound_ids]
                new_content = _strip_content_tool_use(m.content)
                tool_calls_changed = len(kept) != len(tool_calls)
                content_changed = new_content is not m.content and (
                    new_content != m.content
                )
                if tool_calls_changed or content_changed:
                    if not kept and _content_effectively_empty(new_content):
                        continue
                    m = AIMessage(
                        content=new_content,
                        tool_calls=kept,
                        id=m.id,
                        additional_kwargs=dict(
                            getattr(m, "additional_kwargs", {}) or {}
                        ),
                    )
            cleaned.append(m)
        return cleaned

    def call_model(
        self,
        state: ABIAgentState,
    ) -> Command[Literal["call_tools", "__end__", "current_active_agent"]]:
        self._state.set_current_active_agent(self.name)
        logger.debug(f"🧠 Calling model for agent '{self._name}'")
        self._notify_call_model(self._name)

        # Persist routing into the checkpointed graph state so that the next
        # HTTP turn (which rebuilds the agent tree from scratch) restores who is
        # currently handling the conversation instead of resetting to the
        # supervisor. A handoff downstream (see make_handoff_tool) overrides
        # this value within the same step.
        routing_update: dict[str, Any] = {
            "current_active_agent": self._state.current_active_agent,
            "supervisor_agent": self._state.supervisor_agent,
        }

        # Inserting system prompt before messages.
        messages = state["messages"]
        if (
            self._state.supervisor_agent is not None
            and self._state.supervisor_agent.strip() != ""
            and self._state.supervisor_agent != self._name
        ):
            messages = self._strip_inbound_handoff_artifacts(messages)
        if state["system_prompt"]:
            messages = [
                SystemMessage(content=state["system_prompt"]),
            ] + messages
        # Bedrock (and some other providers) require toolUse.input to be a JSON
        # object. Normalize any prior assistant tool calls before re-sending.
        messages = self._normalize_tool_inputs_in_messages(messages)
        logger.debug(f"Messages before calling model: {messages}")

        # Calling model. Only expose workspace-gated tools when a coding
        # workspace is bound to this request; otherwise the model never sees
        # tools it cannot use.
        chat_model = (
            self._chat_model_with_tools
            if coder_workspace_base.get()
            else self._chat_model_without_workspace_tools
        )
        try:
            response: BaseMessage = chat_model.invoke(messages)
        except Exception as e:
            logger.error(f"Model invocation failed for agent '{self._name}': {e}")
            return Command(
                goto="__end__",
                update={
                    **routing_update,
                    "messages": [
                        AIMessage(
                            content=f"I'm sorry, I encountered an error while processing your request:\n\n{e}"
                        )
                    ],
                },
            )
        logger.debug(f"Model response: {response}")

        # Normalize freshly returned tool inputs so the next turn (and Bedrock
        # re-serialization) always sees a JSON object for toolUse.input.
        if isinstance(response, AIMessage):
            response = self._normalize_ai_message_tool_inputs(response)

        # Handle tool calls if present
        if (
            isinstance(response, AIMessage)
            and hasattr(response, "tool_calls")
            and len(response.tool_calls) > 0
        ):
            logger.debug("⏩ Calling tools")
            # TODO: Rethink this.
            # This is done to prevent an LLM to call multiple tools at once.
            # It's important because, as some tools are subgraphs, and that we are passing the full state, the subgraph will be able to mess with the state.
            # Therefore, if the LLM calls a tool here like the "add" method, and at the same time request the multiplication agent, the agent will mess with the state, and the result of the "add" tool will be lost.
            #### ----->  A solution would be to rebuild the state to make sure that the following message of a tool call it the response of that call. If we do that we should theroetically be able to call multiple tools at once, which would be more effective.
            # response.tool_calls = [response.tool_calls[0]]

            return Command(
                goto="call_tools",
                update={**routing_update, "messages": [response]},
            )

        if self._markdown_pretty_display:
            logger.debug("Applying Markdown pretty display to response")
            response = self._pretty_display_markdown(response)

        # Sequential supervisor mode (opt-in): if a sequential_supervisor parent
        # tagged this sub-agent instance, hand control back to that supervisor when
        # we finish — so it can run the next step — instead of ending the whole turn.
        # Mirrors the request_help return path but triggers on normal completion.
        return_to = getattr(self, "_returns_to_supervisor", None)
        if return_to is not None and return_to != self._name:
            logger.debug(
                f"↩️  Sub-agent '{self._name}' returning control to supervisor "
                f"'{return_to}'"
            )
            self._state.set_current_active_agent(return_to)
            return Command(
                goto="current_active_agent",
                graph=Command.PARENT,
                update={
                    **routing_update,
                    "current_active_agent": return_to,
                    "messages": [response],
                },
            )

        return Command(
            goto="__end__",
            update={**routing_update, "messages": [response]},
        )

    def call_tools(self, state: ABIAgentState) -> list[Command]:
        # Check if messages are present in the state.
        if (
            "messages" not in state
            or not isinstance(state["messages"], list)
            or len(state["messages"]) == 0
        ):
            logger.warning("No messages in state, cannot call tools")
            return [Command(goto="__end__")]

        # Check if the last message is an AIMessage and has tool calls.
        last_message: AnyMessage = state["messages"][-1]
        if (
            not isinstance(last_message, AIMessage)
            or not hasattr(last_message, "tool_calls")
            or len(last_message.tool_calls) == 0
        ):
            logger.warning(
                f"No tool calls found in last message but call_tools was called: {last_message}"
            )
            return [Command(goto="__end__", update={"messages": [last_message]})]

        # Get the tool calls from the last message.
        tool_calls: list[ToolCall] = last_message.tool_calls
        assert len(tool_calls) > 0, state["messages"][-1]

        # Initialize the results list.
        results: list[Command] = []
        had_tool_error: bool = False

        # Initialize the called tools list.
        called_tools: list[BaseTool] = []
        for tool_call in tool_calls:
            tool_name: str = tool_call["name"]
            logger.debug(f"🛠️  Calling tool: {tool_name}")

            # Guard against hallucinated / out-of-scope tool names. A raw dict
            # lookup here would raise KeyError and kill the whole invoke thread
            # (the user sees a generic crash). Instead, surface a ToolMessage the
            # model can read so it can self-correct on the next loop.
            tool_ = self._tools_by_name.get(tool_name)
            if tool_ is None:
                available = sorted(self._tools_by_name.keys())
                logger.error(
                    f"🚨 Agent '{self._name}' tried to call unknown tool "
                    f"'{tool_name}'. Available tools: {available}"
                )
                had_tool_error = True
                results.append(
                    Command(
                        update={
                            "messages": [
                                ToolMessage(
                                    content=(
                                        f"Tool '{tool_name}' is not available to "
                                        f"agent '{self._name}'. Available tools: "
                                        f"{available}"
                                    ),
                                    name=tool_name,
                                    tool_call_id=tool_call["id"],
                                )
                            ]
                        },
                    )
                )
                continue

            tool_input_fields = tool_.get_input_schema().model_json_schema()[
                "properties"
            ]

            # For tools with InjectedToolCallId, we must pass the full ToolCall object
            # according to LangChain's requirements
            args: dict[str, Any] | ToolCall = tool_call

            # Check if tool needs state injection
            if "state" in tool_input_fields:
                args = {**tool_call, "state": state}  # inject state

            # Check if tool is a handoff tool
            is_handoff = tool_call["name"].startswith("transfer_to_")
            if is_handoff is True:
                args = {"state": state, "tool_call": {**tool_call, "role": "tool_call"}}

            # Try to invoke the tool.
            try:
                logger.debug(f"🔧 Tool arguments: {args.get('args')}")
                tool_response = tool_.invoke(args)
                logger.debug(
                    f"📦 Tool response: {tool_response.content if hasattr(tool_response, 'content') else tool_response}"
                )
                if (
                    tool_response is not None
                    and hasattr(tool_response, "name")
                    and tool_response.name == "request_help"
                    and self._state.supervisor_agent is not None
                    and self._state.supervisor_agent.strip() != ""
                    and self._state.supervisor_agent != self.name
                ):
                    self._state.set_current_active_agent(self._state.supervisor_agent)
                    self._state.set_requesting_help(True)
                    results.append(
                        Command(goto="current_active_agent", graph=Command.PARENT)
                    )
                    return results

                called_tools.append(tool_)

                # Handle tool response.
                if isinstance(tool_response, ToolMessage):
                    results.append(Command(update={"messages": [tool_response]}))
                elif isinstance(tool_response, Command):
                    results.append(tool_response)
                else:
                    logger.warning(
                        f"Tool call {tool_name} returned an unexpected type: {type(tool_response)}"
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
            except Exception as e:
                logger.error(f"🚨 Tool call {tool_name} failed: {e}")
                had_tool_error = True
                called_tools.append(tool_)
                results.append(
                    Command(
                        update={
                            "messages": [
                                ToolMessage(
                                    content=f"Tool call {tool_name} failed: {str(e)}",
                                    name=tool_name,
                                    tool_call_id=tool_call["id"],
                                )
                            ]
                        },
                    )
                )

        assert len(results) > 0, state

        # Checking if every called tools has return_direct set to True.
        # This is used to know if we can send the ToolMessage to the call_model node.
        return_direct: bool = True
        for t in called_tools:
            if hasattr(t, "return_direct") and t.return_direct is False:
                return_direct = False
                break

        # If the last response is a ToolMessage, we want the model to interpret it.
        last_tool_reponse: ToolMessage | Command | None = pd.get(
            results[-1], "update.messages[-1]", None
        )
        logger.debug(f"last_tool_reponse: {last_tool_reponse}")
        if had_tool_error:
            # A tool call failed — including the case where a sub-agent
            # hallucinated a ``transfer_to_*`` handoff tool it does not own and
            # invoked it on itself. Re-call the model so it reads the error
            # ToolMessage and self-corrects on the next loop. This is hoisted
            # above the handoff guard below on purpose: a *successful* handoff
            # navigates via ``Command(goto=...)`` and never sets
            # ``had_tool_error``, so real handoffs are unaffected — but a *failed*
            # transfer still carries a ``transfer_to_*`` name and would otherwise
            # be swallowed by that guard, ending the turn on a raw error with no
            # user-facing reply.
            logger.debug("⏩ Calling model to interpret the tool error response.")
            results.append(Command(goto="call_model"))
        elif (
            isinstance(last_tool_reponse, ToolMessage)
            and hasattr(last_tool_reponse, "name")
            and last_tool_reponse.name is not None
            and not last_tool_reponse.name.startswith("transfer_to_")
        ):
            if return_direct is False:
                logger.debug("⏩ Calling model to interpret the tool response.")
                results.append(Command(goto="call_model"))
            else:
                logger.debug(
                    "📧 Injecting ToolMessage into AIMessage for the user to see."
                )
                results.append(
                    Command(
                        update={
                            "messages": [AIMessage(content=last_tool_reponse.content)]
                        }
                    )
                )

        logger.debug(f"✅ Tool results: {results}")
        return results

    @property
    def workflow(self) -> StateGraph:
        return self._workflow

    def _identity(self) -> dict[str, Any]:
        """Snapshot the per-request identity ContextVars (set by API layer)."""
        return {
            "user_id": agent_user_id.get(),
            "chat_id": agent_chat_id.get() or self._state.thread_id,
            "workspace_id": agent_workspace_id.get(),
        }

    def _publish_agent_event(self, event: Any) -> None:
        """Best-effort publish to the process-wide EventService.

        Silently no-ops when no EventService is configured (tests, library use
        outside a loaded engine). Failures in the EventService must never
        break the conversation flow.
        """
        events = get_default_event_service()
        if events is None:
            return
        try:
            events.publish(event)
        except Exception as exc:
            logger.warning(f"Agent '{self._name}': failed to publish event: {exc}")

    def _stringify_content(self, value: Any) -> str | None:
        """Coerce a LangChain message content (str, list of blocks, or None) to a string for event storage."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        try:
            import json

            return json.dumps(value, default=str)
        except Exception:
            return str(value)

    def _notify_tool_usage(self, message: AnyMessage):
        self._event_queue.put(ToolUsageEvent(payload=message))
        self._on_tool_usage(message)
        identity = self._identity()
        import json

        for call in getattr(message, "tool_calls", []) or []:
            args = (
                call.get("args")
                if isinstance(call, dict)
                else getattr(call, "args", None)
            )
            try:
                args_str = json.dumps(args, default=str) if args is not None else None
            except Exception:
                args_str = str(args)
            self._publish_agent_event(
                AgentToolCalled(
                    agent_name=self._name,
                    tool_name=call.get("name")
                    if isinstance(call, dict)
                    else getattr(call, "name", None),
                    tool_call_id=call.get("id")
                    if isinstance(call, dict)
                    else getattr(call, "id", None),
                    tool_args=args_str,
                    **identity,
                )
            )

    def _notify_tool_response(self, message: AnyMessage):
        self._event_queue.put(ToolResponseEvent(payload=message))
        self._on_tool_response(message)
        content = self._stringify_content(getattr(message, "content", None))
        self._publish_agent_event(
            AgentToolResponded(
                agent_name=self._name,
                tool_name=getattr(message, "name", None),
                tool_call_id=getattr(message, "tool_call_id", None),
                content=content,
                content_length=len(content) if content is not None else None,
                **self._identity(),
            )
        )

    def _notify_ai_message(self, message: AnyMessage, agent_name: str):
        self._event_queue.put(AIMessageEvent(payload=message, agent_name=agent_name))
        self._on_ai_message(message, agent_name)
        content = self._stringify_content(getattr(message, "content", None))
        self._publish_agent_event(
            AgentAIMessageEmitted(
                agent_name=agent_name,
                content=content,
                content_length=len(content) if content is not None else None,
                **self._identity(),
            )
        )

    def _notify_call_model(self, agent_name: str):
        self._event_queue.put(CallModelEvent(payload=agent_name, agent_name=agent_name))
        self._on_call_model(agent_name)
        self._publish_agent_event(
            AgentModelCalled(agent_name=agent_name, **self._identity())
        )

    def _notify_agent_routing(self, agent_name: str):
        self._event_queue.put(
            AgentRoutingEvent(payload=agent_name, agent_name=agent_name)
        )
        self._on_agent_routing(agent_name)
        self._publish_agent_event(
            AgentRouted(
                agent_name=self._name,
                routed_to=agent_name,
                **self._identity(),
            )
        )

    def _sync_event_queue_with_subagents(self):
        """Ensure all nested sub-agents publish runtime events to the same queue."""
        for agent in self._agents:
            agent._event_queue = self._event_queue
            agent._sync_event_queue_with_subagents()

    def on_tool_usage(self, callback: Callable[[AnyMessage], None]):
        """Register a callback to be called when a tool is used.

        The callback will be invoked whenever the model makes a tool call,
        before the tool is actually executed.

        Args:
            callback (Callable[[AnyMessage], None]): Function to call with the message
                containing the tool call
        """
        self._on_tool_usage = callback
        # # Also set the callback on all sub-agents to ensure they notify properly
        # for agent in self._agents:
        #     agent.on_tool_usage(callback)

    def on_tool_response(self, callback: Callable[[AnyMessage], None]):
        """Register a callback to be called when a tool response is received.

        The callback will be invoked whenever a tool response message is processed,
        before passing the messages to the model.

        Args:
            callback (Callable[[AnyMessage], None]): Function to call with the message
                containing the tool response
        """
        self._on_tool_response = callback
        # # Also set the callback on all sub-agents to ensure they notify properly
        # for agent in self._agents:
        #     agent.on_tool_response(callback)

    def on_ai_message(self, callback: Callable[[AnyMessage, str], None]):
        """Register a callback to be called when an AI message is received."""
        self._on_ai_message = callback
        # Also set the callback on all sub-agents to ensure they notify properly
        for agent in self._agents:
            agent.on_ai_message(callback)

    @property
    def app(self):
        """Get the underlying Langchain app.
        This property exposes the underlying Langchain app for advanced usage scenarios.
        Users can call app.invoke() directly with custom message sequences and configurations
        if they need more control than the standard invoke() method provides.

        Returns:
            RunnableSequence: The Langchain runnable sequence that processes messages
        """
        return self._app

    def stream(self, prompt: str) -> Generator[dict[str, Any] | Any, None, None]:
        """Process a user prompt through the agent and yield responses as they come.

        Args:
            prompt (str): The user's text prompt to process

        Yields:
            str: The model's response text
        """
        prompt_str = self._stringify_content(prompt)
        self._publish_agent_event(
            AgentUserMessageReceived(
                agent_name=self._name,
                content=prompt_str,
                content_length=len(prompt_str) if prompt_str is not None else None,
                **self._identity(),
            )
        )

        notified = {}

        for chunk in self.graph.stream(
            {"messages": [HumanMessage(content=prompt)]},
            config={"configurable": {"thread_id": self._state.thread_id}},
            subgraphs=True,
        ):
            source, payload = chunk
            agent_name = self._name if len(source) == 0 else source[0].split(":")[0]
            if isinstance(payload, dict):
                last_messages = []
                v = list(payload.values())[0]

                if v is None:
                    continue

                if isinstance(v, dict):
                    if (
                        "messages" in v
                        and isinstance(v["messages"], list)
                        and len(v["messages"]) > 0
                    ):
                        last_messages = [v["messages"][-1]]
                    else:
                        continue
                elif isinstance(v, list):
                    last_messages = []
                    for e in v:
                        if (
                            isinstance(e, dict)
                            and "messages" in e
                            and isinstance(e["messages"], list)
                            and len(e["messages"]) > 0
                        ):
                            last_messages.append(e["messages"][-1])
                else:
                    continue

                for last_message in last_messages:
                    if isinstance(last_message, AIMessage):
                        if self._has_tool_calls(last_message):
                            # This is a tool call.
                            self._notify_tool_usage(last_message)
                        else:
                            # This if is here to filter each source of AIMessage. Which means that it will notify ai message only if the methods:
                            # - call_model
                            # - call_tools
                            # are called.
                            # If you need another method to be able to return an AIMessage or a Command(..., update={"messages": [AIMessage(...)]}) we either need to add it to the list or have this specific method calling self._notify_ai_message directly.

                            allowed_sources_of_ai_message = ["call_model", "call_tools"]
                            if any(
                                source in payload
                                for source in allowed_sources_of_ai_message
                            ):
                                self._notify_ai_message(last_message, agent_name)

                    elif isinstance(last_message, ToolMessage):
                        is_handoff_tool_response = (
                            hasattr(last_message, "name")
                            and isinstance(last_message.name, str)
                            and last_message.name.startswith("transfer_to_")
                        )
                        if (
                            last_message.id not in notified
                            and is_handoff_tool_response is False
                        ):
                            self._notify_tool_response(last_message)
                            notified[last_message.id] = True
                    else:
                        if "tool_call_id" in last_message:
                            if last_message["tool_call_id"] not in notified:
                                self._notify_tool_response(last_message)
                                notified[last_message["tool_call_id"]] = True
            yield chunk

    def invoke(self, prompt: str) -> str:
        """Process a user prompt through the agent and return the response.

        This method takes a text prompt from the user, processes it through the underlying
        Langchain app, and returns the model's response. The prompt is wrapped in a
        HumanMessage and processed in a new message sequence.

        Args:
            prompt (str): The user's text prompt to process


            str: The model's response text
        """

        chunks: list[dict[str, Any]] = []
        for chunk in self.stream(prompt):
            if isinstance(chunk, tuple):
                chunk = chunk[1]

            if not isinstance(chunk, dict):
                continue

            chunks.append(chunk)

        if len(chunks) == 0:
            return ""

        last_chunk_values = list(chunks[-1].values())
        if len(last_chunk_values) == 0:
            return ""
        value = last_chunk_values[0]
        messages = []
        if (
            isinstance(value, dict)
            and "messages" in value
            and isinstance(value["messages"], list)
        ):
            messages = value["messages"]
        elif isinstance(value, list) and len(value) > 0:
            last_item = value[-1]
            if (
                isinstance(last_item, dict)
                and "messages" in last_item
                and isinstance(last_item["messages"], list)
            ):
                messages = last_item["messages"]

        if len(messages) == 0:
            return ""

        last_message = messages[-1]
        if hasattr(last_message, "content"):
            content = last_message.content
        else:
            content = str(last_message) if last_message is not None else ""
        # content = list(chunks[-1].values())[0]["messages"][-1].content

        completion_content = self._content_to_text(content)
        self._publish_agent_event(
            AgentInvocationCompleted(
                agent_name=self._name,
                content=completion_content,
                content_length=len(completion_content)
                if completion_content is not None
                else None,
                **self._identity(),
            )
        )

        return completion_content

    def reset(self):
        """Reset the agent's conversation state.

        This method increments the internal thread ID counter, effectively starting a new
        conversation thread. Any subsequent invocations will be processed as part of a
        new conversation context.
        """
        try:
            current_thread_id = int(self._state.thread_id)
            self._state.set_thread_id(str(current_thread_id + 1))
        except (ValueError, TypeError):
            # If thread_id is not a valid integer, generate a new UUID
            self._state.set_thread_id(str(uuid.uuid4()))

    def duplicate(
        self,
        queue: Queue | None = None,
        agent_shared_state: AgentSharedState | None = None,
    ) -> "Agent":
        """Create a new instance of the agent with the same configuration.

        This method creates a deep copy of the agent with the same configuration
        but with its own independent state. This is useful when you need to run
        multiple instances of the same agent concurrently.

        Returns:
            Agent: A new Agent instance with the same configuration
        """
        shared_state = agent_shared_state or AgentSharedState()

        if queue is None:
            queue = Queue()

        # We duplicated each agent and add them as tools.
        # This will be recursively done for each sub agents.
        agents: list[Agent] = [
            agent.duplicate(queue, shared_state) for agent in self._original_agents
        ]

        new_agent = self.__class__(
            name=self._name,
            description=self._description,
            chat_model=self._chat_model,
            tools=self._original_tools,
            agents=agents,
            memory=self._checkpointer,
            state=shared_state,  # Create new state instance
            configuration=self._configuration,
            event_queue=queue,
            enable_default_tools=self._enable_default_tools,
            markdown_pretty_display=self._markdown_pretty_display,
        )

        return new_agent

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        """Adds API endpoints for this agent to the given router.

        Args:
            router (APIRouter): The router to add endpoints to
            route_name (str): Optional prefix for route names. Defaults to ""
            name (str): Optional name to add to the endpoints. Defaults to ""
            description (str): Optional description to add to the endpoints. Defaults to ""
            description_stream (str): Optional description to add to the stream endpoints. Defaults to ""
            tags (list[str]): Optional list of tags to add to the endpoints. Defaults to None
        """

        route_name = route_name or self._name
        name = name or self._name.capitalize().replace("_", " ")
        description = description or self._description
        description_stream = description_stream or self._description

        @router.post(
            f"/{route_name}/completion" if route_name else "/completion",
            name=f"{name} completion",
            description=description,
            tags=tags,
        )
        def completion(query: CompletionQuery):
            if isinstance(query.thread_id, int):
                query.thread_id = str(query.thread_id)

            fresh_state = AgentSharedState(thread_id=query.thread_id)
            new_agent = self.duplicate(agent_shared_state=fresh_state)
            return new_agent.invoke(query.prompt)

        @router.post(
            f"/{route_name}/stream-completion" if route_name else "/stream-completion",
            name=f"{name} stream completion",
            description=description_stream,
            tags=tags,
        )
        async def stream_completion(query: CompletionQuery):
            if isinstance(query.thread_id, int):
                query.thread_id = str(query.thread_id)

            fresh_queue: Queue = Queue()
            fresh_state = AgentSharedState(thread_id=query.thread_id)
            new_agent = self.duplicate(
                queue=fresh_queue, agent_shared_state=fresh_state
            )
            return EventSourceResponse(
                new_agent.stream_invoke(query.prompt),
                media_type="text/event-stream; charset=utf-8",
            )

    def stream_invoke(self, prompt: str):
        """Process a user prompt through the agent and yield responses as they come.

        Args:
            prompt (str): The user's text prompt to process

        Yields:
            dict: Event data formatted for SSE
        """

        # Start a thread to run the invoke and put results in queue
        def run_invoke():
            try:
                final_state = self.invoke(prompt)
            except Exception as e:
                logger.error(
                    f"Agent invoke thread error for '{self._name}': {e}", exc_info=True
                )
                final_state = (
                    f"I encountered an error while processing your request: {e}"
                )
            self._event_queue.put(FinalStateEvent(payload=final_state))

        from threading import Thread

        # Carry identity ContextVars across the thread boundary
        # so events published from inside invoke() stay tagged with the caller's
        # request scope. Raw Thread() does not inherit context by default.
        ctx = copy_context()
        thread = Thread(target=ctx.run, args=(run_invoke,))
        thread.start()

        final_state = None
        while True:
            try:
                message = self._event_queue.get(timeout=0.05)
                if isinstance(message, ToolUsageEvent):
                    yield {
                        "event": "tool_usage",
                        "data": str(message.payload.tool_calls[0]["name"]),
                    }
                elif isinstance(message, ToolResponseEvent):
                    yield {
                        "event": "tool_response",
                        "data": str(pd.get(message, "payload.content", "NULL")),
                    }
                elif isinstance(message, AIMessageEvent):
                    yield {
                        "event": "ai_message",
                        "data": self._content_to_text(message.payload.content),
                    }
                elif isinstance(message, CallModelEvent):
                    yield {
                        "event": "call_model",
                        "data": str(message.payload),
                    }
                elif isinstance(message, AgentRoutingEvent):
                    yield {
                        "event": "agent_routing",
                        "data": str(message.payload),
                    }
                elif isinstance(message, FinalStateEvent):
                    final_state = message.payload
                    break

                if (
                    not thread.is_alive()
                    and self._event_queue.empty()
                    and final_state is None
                ):
                    # We have a problem.
                    raise Exception(
                        "Agent thread has died and no final state event was received."
                    )
            except Empty:
                pass

        response = self._content_to_text(final_state)
        logger.debug(f"Response: {response}")

        # Use a buffer to handle text chunks
        buffer = ""
        for char in response:
            buffer += char
            if char in ["\n", "\r"]:
                # if buffer.strip():  # Only send non-empty lines
                yield {"event": "message", "data": buffer.rstrip()}
                buffer = ""

        # Don't forget remaining text
        if buffer.strip():
            yield {"event": "message", "data": buffer}

        yield {"event": "done", "data": "[DONE]"}

    @property
    def tools(self) -> list[Union[Tool, BaseTool]]:
        """Get the list of tools available to the agent.

        Returns:
            list[Tool]: List of tools configured for this agent
        """
        return self._structured_tools

    @property
    def name(self) -> str:
        """Get the name of the agent.

        Returns:
            str: The agent's name
        """
        return self._name

    @property
    def description(self) -> str:
        """Get the description of the agent.

        Returns:
            str: The agent's description
        """
        return self._description

    @property
    def agents(self) -> list["Agent"]:
        return self._agents

    @property
    def chat_model(self) -> BaseChatModel:
        """Get the chat model used by the agent.

        Returns:
            BaseChatModel: The agent's chat model
        """
        if isinstance(self._chat_model, ChatModel):
            return self._chat_model.model
        return self._chat_model

    @property
    def configuration(self) -> AgentConfiguration:
        """Get the configuration used by the agent.

        Returns:
            AgentConfiguration: The agent's configuration
        """
        return self._configuration

    def hello(self) -> str:
        return "Hello"


def make_handoff_tool(*, agent: Agent, parent_graph: bool = False) -> BaseTool:
    """Create a tool that can return handoff via a Command"""
    agent_name = Agent.validate_name(agent.name)
    tool_name = f"transfer_to_{agent_name}"

    @tool(tool_name)
    def handoff_to_agent(
        # # optionally pass current graph state to the tool (will be ignored by the LLM)
        state: Annotated[dict, InjectedState],
        # optionally pass the current tool call ID (will be ignored by the LLM)
        tool_call: Annotated[ToolCall, ToolCall],
    ):
        """Ask another agent for help."""
        tool_message = ToolMessage(
            content=f"__handoff__:{agent_name}",
            name=tool_name,
            tool_call_id=tool_call["id"],
            additional_kwargs={
                "internal": True,
                "handoff_target": agent_name,
            },
        )

        agent.state.set_current_active_agent(agent_name)

        return Command(
            # navigate to another agent node in the PARENT graph
            goto=agent_name,
            graph=Command.PARENT if parent_graph else None,
            # This is the state update that the agent `agent_name` will see when it is invoked.
            # We're passing agent's FULL internal message history AND adding a tool message to make sure
            # the resulting chat history is valid. See the paragraph above for more information.
            # ``current_active_agent`` is persisted through the checkpointer so the
            # delegation is restored on the next turn instead of routing back to
            # the supervisor.
            update={
                "messages": state["messages"] + [tool_message],
                "current_active_agent": agent_name,
            },
        )

    assert isinstance(handoff_to_agent, BaseTool)

    return handoff_to_agent
