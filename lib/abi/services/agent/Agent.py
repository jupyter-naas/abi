# Standard library imports for type hints
from typing import Callable, Literal, Any, Union, Sequence, Generator, Annotated, Optional, Dict, cast
import os

# LangChain Core imports for base components
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    HumanMessage,
    AnyMessage,
    BaseMessage,
    SystemMessage,
    AIMessage,
)
from langchain_core.tools import Tool, StructuredTool, BaseTool
from langchain_core.runnables import Runnable

# LangGraph imports for workflow and state management
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START
from langgraph.graph.message import MessagesState
from langgraph.graph.state import CompiledStateGraph

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langchain_core.messages import ToolMessage, ToolCall
from langgraph.types import Command
from enum import Enum

# Pydantic imports for schema validation
from pydantic import BaseModel, Field

from abi.utils.Expose import Expose
from lib.abi.models.Model import ChatModel

# Dataclass imports for configuration
from dataclasses import dataclass, field

from fastapi import APIRouter
from abi import logger
from sse_starlette.sse import EventSourceResponse

from queue import Queue, Empty
import pydash as pd
import re
import uuid


def create_checkpointer() -> BaseCheckpointSaver:
    """Create a checkpointer based on environment configuration.
    
    Returns a PostgreSQL-backed checkpointer if POSTGRES_URL is set,
    otherwise returns an in-memory checkpointer.
    """
    postgres_url = os.getenv("POSTGRES_URL")
    
    if postgres_url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg import Connection
            from psycopg.rows import dict_row
            import time
            logger.debug(f"Using PostgreSQL checkpointer for persistent memory: {postgres_url}")
            
            # Try connection with retries (PostgreSQL might still be starting)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Create connection with proper configuration (matching from_conn_string)
                    conn = Connection.connect(
                        postgres_url,
                        autocommit=True,
                        prepare_threshold=0,
                        row_factory=dict_row
                    )
                    checkpointer = PostgresSaver(conn)
                    
                    # Setup tables if they don't exist
                    checkpointer.setup()
                    logger.debug("PostgreSQL checkpointer tables initialized")
                    
                    return checkpointer
                    
                except Exception as conn_error:
                    if attempt < max_retries - 1:
                        logger.warning(f"PostgreSQL connection attempt {attempt + 1} failed, retrying in 2 seconds...")
                        time.sleep(2)
                    else:
                        raise conn_error
                        
        except ImportError:
            logger.error("PostgreSQL checkpointer requested but langgraph.checkpoint.postgres not available. Falling back to in-memory.")
        except Exception as e:
            # Provide more helpful error messages
            error_msg = str(e)
            if "nodename nor servname provided" in error_msg:
                logger.error(f"PostgreSQL connection failed - cannot resolve hostname. Check if PostgreSQL is running and hostname is correct in POSTGRES_URL: {postgres_url}")
                logger.error("Hint: If running outside Docker, use 'localhost' instead of 'postgres' in POSTGRES_URL")
            else:
                logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}")
            logger.error("Falling back to in-memory checkpointer")
        
        # Fallback to in-memory checkpointer
        return MemorySaver()
    else:
        logger.debug("Using in-memory checkpointer (set POSTGRES_URL for persistent memory)")
        return MemorySaver()

class AgentSharedState:
    _thread_id: str
    _current_active_agent: Optional[str]
    _supervisor_agent: Optional[str]
    _requesting_help: bool

    def __init__(self, thread_id: str = "1", current_active_agent: Optional[str] = None, supervisor_agent: Optional[str] = None):
        assert isinstance(thread_id, str)
        
        self._thread_id = thread_id
        self._current_active_agent = current_active_agent
        self._supervisor_agent = supervisor_agent
        self._requesting_help = False

    @property
    def thread_id(self) -> str:
        return self._thread_id

    def set_thread_id(self, thread_id: str):
        self._thread_id = thread_id
    
    @property 
    def current_active_agent(self) -> Optional[str]:
        return self._current_active_agent
    
    def set_current_active_agent(self, agent_name: Optional[str]):
        self._current_active_agent = agent_name

    @property
    def supervisor_agent(self) -> Optional[str]:
        return self._supervisor_agent

    def set_supervisor_agent(self, agent_name: Optional[str]):
        self._supervisor_agent = agent_name
        
    @property
    def requesting_help(self) -> bool:
        return self._requesting_help
    
    def set_requesting_help(self, requesting_help: bool):
        self._requesting_help = requesting_help

@dataclass
class Event:
    payload: Any


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
    system_prompt: str = field(
        default="You are a helpful assistant. If a tool you used did not return the result you wanted, look for another tool that might be able to help you. If you don't find a suitable tool. Just output 'I DONT KNOW'"
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
        _system_prompt (str): System prompt that defines the agent's behavior
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
    _system_prompt: str

    _chat_model: BaseChatModel
    _chat_model_with_tools: Runnable[
        Any
        | str
        | Sequence[BaseMessage | list[str] | tuple[str, str] | str | dict[str, Any]],
        BaseMessage,
    ]
    _tools: list[Union[Tool, BaseTool, "Agent"]]
    _original_tools: list[Union[Tool, BaseTool, "Agent"]]
    _tools_by_name: dict[str, Union[Tool, BaseTool]]
    _native_tools: list[dict]

    # An agent can have other agents.
    # He will be responsible to load them as tools.
    _agents: list["Agent"] = []

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
    ):
        """Initialize a new Agent instance.

        Args:
            chat_model (BaseChatModel): The language model to use for chat interactions.
                Should support tool binding.
            tools (list[Tool]): List of tools to make available to the agent.
            memory (BaseCheckpointSaver, optional): Component to save conversation state.
                If None, will use PostgreSQL if POSTGRES_URL env var is set, otherwise in-memory.
        """
        logger.debug(f"Initializing agent: {name}")
        self._name = name
        self._description = description
        self._system_prompt = configuration.system_prompt
        self._state = state
        self._original_tools = tools
        self._original_agents = agents

        # We set the supervisor agent and current active agent before the default tools are injected.
        if self._state.supervisor_agent is not None:
            self._state.set_supervisor_agent(self._state.supervisor_agent)
        logger.debug(f"Supervisor agent: {self._state.supervisor_agent}")

        agent_names = [a.name for a in self._original_agents] + [name]
        if self._state.current_active_agent is not None and self._state.current_active_agent in agent_names:
            self._state.set_current_active_agent(self._state.current_active_agent)
        logger.debug(f"Current active agent: {self._state.current_active_agent}")

        # We inject default tools
        tools += self.default_tools()

        # We store the original list of provided tools. This will be usefull for duplication.
        self._tools = tools
        self._native_tools = native_tools

        # Assertions
        assert isinstance(name, str)
        assert isinstance(description, str)
        assert isinstance(chat_model, BaseChatModel | ChatModel)

        # We assert agents
        for agent in agents:
            assert isinstance(agent, Agent)

        # We store the provided tools in __structured_tools because we will need to know which ones are provided by the user and which one are agents.
        # This is needed when we duplicate the agent.
        _structured_tools, _agents = self.prepare_tools(cast(list[Union[Tool, BaseTool, "Agent"]], tools), agents)
        self._structured_tools = _structured_tools
        self._agents = _agents

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

        base_chat_model: BaseChatModel = chat_model if isinstance(chat_model, BaseChatModel) else chat_model.model
        assert isinstance(base_chat_model, BaseChatModel)

        self._chat_model = base_chat_model
        if hasattr(base_chat_model, "output_version"):
            self._chat_model_output_version = base_chat_model.output_version
            
        self._chat_model_with_tools = base_chat_model
        if self._tools or self._native_tools:
            tools_to_bind: list[Union[Tool, BaseTool, Dict]] = []
            tools_to_bind.extend(self._structured_tools)
            tools_to_bind.extend(self._native_tools)
            
            # Test if the chat model can bind tools by trying with a default tool first
            if self._can_bind_tools(base_chat_model):
                self._chat_model_with_tools = base_chat_model.bind_tools(tools_to_bind)
            else:
                logger.warning(f"Chat model {type(base_chat_model).__name__} does not support tool calling. Tools will not be available for agent '{self._name}'.")
                # Keep the original model without tools
                self._chat_model_with_tools = base_chat_model
        
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

        # Initialize the event queue.
        if event_queue is None:
            self._event_queue = Queue()
        else:
            self._event_queue = event_queue

        # We build the graph.
        self.build_graph()

    def _can_bind_tools(self, chat_model: BaseChatModel) -> bool:
        """Test if the chat model can bind tools by attempting to bind the get_time_date default tool.
        
        Args:
            chat_model (BaseChatModel): The chat model to test
            
        Returns:
            bool: True if the model can bind tools, False otherwise
        """
        try:
            # Create the get_time_date tool that's used in default_tools()
            @tool(return_direct=True)
            def get_time_date(timezone: str = 'Europe/Paris') -> str:
                """Get the current time and date."""
                from datetime import datetime
                from zoneinfo import ZoneInfo
                return datetime.now(ZoneInfo(timezone)).strftime("%H:%M:%S %Y-%m-%d")
            
            # Try to bind this single tool to test if the model supports tool binding
            chat_model.bind_tools([get_time_date])
            
            # If we get here without an exception, the model supports tool binding
            # logger.debug(f"Chat model {type(chat_model).__name__} supports tool calling.")
            return True
            
        except Exception as e:
            # If binding tools raises an exception, the model doesn't support tools
            logger.debug(f"Chat model {type(chat_model).__name__} does not support tool calling: {e}")
            return False

    def default_tools(self) -> list[Tool | BaseTool]:
        @tool(return_direct=True)
        def request_help(
            reason: str
        ):
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
            return "Requesting help from the supervisor agent."
        
        @tool(return_direct=False)
        def get_time_date(timezone: str = 'Europe/Paris') -> str:
            """Returns the current date and time for a given timezone."""
            from datetime import datetime
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(timezone)).strftime("%H:%M:%S %Y-%m-%d")
        
        @tool(return_direct=True)
        def get_current_active_agent() -> str:
            """Returns the current active agent."""
            return "The current active agent is: " + (self._state.current_active_agent or self.name)
        
        @tool(return_direct=True)
        def get_supervisor_agent() -> str:
            """Returns the supervisor agent."""
            if self._state.supervisor_agent is None:
                return "I don't have a supervisor agent."
            return "The supervisor agent is: " + self._state.supervisor_agent
        
        @tool(return_direct=True)
        def list_tools_available() -> str:
            """Displays a formatted list of all available tools."""
            if not hasattr(self, "_structured_tools") or len(self._structured_tools) == 0:
                return "I don't have any tools available to help you at the moment."
            
            tools_text = "Here are the tools I can use to help you:\n\n"
            for t in self._structured_tools:
                if not t.name.startswith("transfer_to"):
                    tools_text += f"- `{t.name}`: {t.description.splitlines()[0]}\n"
            return tools_text.rstrip()

        @tool(return_direct=True)
        def list_subagents_available() -> str:
            """Displays a formatted list of all available sub-agents."""
            if not hasattr(self, "_agents") or len(self._agents) == 0:
                return "I don't have any sub-agents that can assist me at the moment."
                
            agents_text = "I can collaborate with these sub-agents:\n"
            for agent in self._agents:
                agents_text += f"- `{agent.name}`: {agent.description}\n"
            return agents_text.rstrip()
        
        @tool(return_direct=True)
        def list_intents_available() -> str:
            """Displays a formatted list of all available intents."""
            if not hasattr(self, "_intents") or len(self._intents) == 0:
                return "I haven't been configured with any specific intents yet."
            
            from abi.services.agent.IntentAgent import Intent, IntentType, IntentScope
            
            # Group intents by scope and type
            intents_by_scope: dict[Optional[IntentScope], dict[IntentType, list[Intent]]] = {}
            for intent in self._intents:
                if intent.intent_scope not in intents_by_scope:
                    intents_by_scope[intent.intent_scope] = {}
                if intent.intent_type not in intents_by_scope[intent.intent_scope]:
                    intents_by_scope[intent.intent_scope][intent.intent_type] = []
                intents_by_scope[intent.intent_scope][intent.intent_type].append(intent)
            
            intents_text = "Here are all the intents I'm configured with:\n\n"
            for scope, types_dict in intents_by_scope.items():
                intents_text += f"### Intents for {str(scope)}\n\n"
                for intent_type, intents in types_dict.items():
                    intents_text += f"#### {str(intent_type)}\n\n"
                    intents_text += "| Intent | Target |\n"
                    intents_text += "|--------|--------|\n"
                    for intent in intents:
                        if intent.intent_scope == IntentType.RAW:
                            intents_text += f"| {intent.intent_value} | {intent.intent_target} |\n"
                        else:
                            intents_text += f"| {intent.intent_value} | `{intent.intent_target}` |\n"
                    intents_text += "\n"
            return intents_text.rstrip()
        
        @tool(return_direct=False)
        def read_makefile() -> str:
            """Read the Makefile and return the content."""
            try:
                with open("Makefile", "r") as f:
                    makefile_content = f.read()
                
                return "Here are the make commands available:\n\n" + makefile_content

            except FileNotFoundError:
                return "Could not find Makefile in the root directory."
            except Exception as e:
                return f"Error reading Makefile: {str(e)}"

        tools: list[Tool | BaseTool] = [
            get_time_date, 
            list_tools_available, 
            list_subagents_available, 
            list_intents_available,
        ]
        if self.state.supervisor_agent and self.state.supervisor_agent != self.name:
            tools.append(request_help)

        if self.state.supervisor_agent is not None or len(self._agents) > 0:
            tools.append(get_current_active_agent)
            tools.append(get_supervisor_agent)
            
        if self.state.supervisor_agent == self.name and os.getenv("ENV") == "dev":
            tools.append(read_makefile)
        return tools

    @property
    def system_prompt(self) -> str:
        return self._system_prompt
    
    def set_system_prompt(self, system_prompt: str):
        self._system_prompt = system_prompt

    @property
    def structured_tools(self) -> list[Tool | BaseTool]:
        return self._structured_tools

    @property
    def state(self) -> AgentSharedState:
        return self._state

    def validate_tool_name(self, tool: BaseTool) -> BaseTool:
        if not re.match(r'^[a-zA-Z0-9_-]+$', tool.name):
            # Replace invalid characters with '_'
            valid_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tool.name)
            logger.warning(f"Tool name '{tool.name}' does not comply with '^[a-zA-Z0-9_-]+$'. Renaming to '{valid_name}'.")
            tool.name = valid_name
        return tool

    def prepare_tools(
        self, 
        tools: list[Union[Tool, BaseTool, "Agent"]], 
        agents: list
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
                        tool = self.validate_tool_name(tool)
                        if tool.name not in _tool_names:
                            _tools.append(tool)
                            _tool_names.add(tool.name)
            else:
                # Accept both Tool and BaseTool
                if hasattr(t, "name"):
                    if t.name not in _tool_names:
                        _tools.append(t)
                        _tool_names.add(t.name)

        # We process agents that are not provided in tools.
        for agent in agents:
            if agent.name not in _agent_names:
                _agents.append(agent)
                _agent_names.add(agent.name)
                for tool in agent.as_tools():
                    tool = self.validate_tool_name(tool)
                    if tool.name not in _tool_names:
                        _tools.append(tool)
                        _tool_names.add(tool.name)

        return _tools, _agents

    def as_tools(self, parent_graph: bool = False) -> list[BaseTool]:
        return [make_handoff_tool(agent=self, parent_graph=parent_graph)]

    def build_graph(self, patcher: Optional[Callable] = None):
        graph = StateGraph(MessagesState)

        graph.add_node(self.current_active_agent)
        graph.add_edge(START, "current_active_agent")

        graph.add_node(self.continue_conversation)

        graph.add_node(self.call_model)
        
        graph.add_node(self.call_tools)

        for agent in self._agents:
            graph.add_node(agent.name, agent.graph)

        # Patcher is callable that can be passed and that will impact the graph before we compile it.
        # This is used to be able to give more flexibility about how the graph is being built.
        if patcher:
            graph = patcher(graph)

        self.graph = graph.compile(checkpointer=self._checkpointer)


    def get_last_human_message(self, state: MessagesState) -> Any | None:
        """Get the appropriate human message based on AI message context.

        Args:
            state (MessagesState): Current conversation state
            
        Returns:
            Any | None: The relevant human message
        """
        last_ai_message : Any | None = pd.find(state["messages"][::-1], lambda m: isinstance(m, AIMessage))
        if last_ai_message is not None and last_ai_message.additional_kwargs.get("owner") == self.name:
            return pd.find(state["messages"][::-1], lambda m: isinstance(m, HumanMessage))
        elif last_ai_message is not None and hasattr(last_ai_message, "additional_kwargs") and last_ai_message.additional_kwargs is not None and "owner" in last_ai_message.additional_kwargs:
            return pd.filter_(state["messages"][::-1], lambda m: isinstance(m, HumanMessage))[1]
        else:
            return pd.find(state["messages"][::-1], lambda m: isinstance(m, HumanMessage))
        

    def current_active_agent(self, state: MessagesState) -> Command:
        """Goto the current active agent.
        
        Args:
            state (MessagesState): Current conversation state
            
        Returns:
            Command: Command to goto the current active agent
        """
        # Log the current active agent
        logger.debug(f"😏 Supervisor agent: '{self.state.supervisor_agent}'")
        logger.debug(f"🟢 Active agent: '{self.state.current_active_agent}'")
        logger.debug(f"🤖 Current Agent: '{self.name}'")

        # Get the last human message
        last_human_message = self.get_last_human_message(state)

        # Handle agent routing via @mention
        if (
            last_human_message is not None and 
            isinstance(last_human_message.content, str) and 
            last_human_message.content.startswith("@") and 
            last_human_message.content.split(" ")[0].split("@")[1] != self.name
        ):
            at_mention = last_human_message.content.split(" ")[0].split("@")[1]
            logger.debug(f"🔀 Handle agent routing via @mention to '{at_mention}'")

            # Check if we have an agent with this name.
            agent = pd.find(self._agents, lambda a: a.name.lower() == at_mention.lower())
            
            #Remove mention from the last human message with re.sub
            import re
            last_human_message.content = re.sub(r"^@[^ ]* ", "", last_human_message.content)
            
            if agent is not None:
                self._state.set_current_active_agent(agent.name)
                return Command(goto=agent.name, update={"messages": state["messages"]})
            else:
                logger.debug(f"❌ Agent '{at_mention}' not found")

        if (
            self._state.current_active_agent is not None and 
            self._state.current_active_agent != self.name
        ):
            logger.debug(f"⏩ Continuing conversation with agent '{self._state.current_active_agent}'")
            # Check if current active agent is in list of agents.
            if self._state.current_active_agent in [a.name for a in self._agents]:
                self._state.set_current_active_agent(self._state.current_active_agent)
                return Command(goto=self._state.current_active_agent)
            else:
                logger.debug(f"❌ Agent '{self._state.current_active_agent}' not found")
        
        # self._state.set_current_active_agent(self.name)
        logger.debug(f"💬 Starting chatting with agent '{self.name}'")
        if self.state.supervisor_agent != self.name and "SUPERVISOR SYSTEM PROMPT" not in self._system_prompt:
            # This agent is a subagent with a supervisor
            subagent_prompt = f"""
SUPERVISOR SYSTEM PROMPT:

Remember, you are a specialized agent working under the supervision of {self.state.supervisor_agent}.

1. Stay focused on your specialized role and core capabilities
2. Follow your system prompt instructions precisely
3. For EVERY user message, first evaluate if you can handle it within your core capabilities
4. If you encounter ANY of these situations:
   - You are uncertain about how to proceed
   - The task seems outside your core capabilities 
   - You need clarification about requirements
   - You want to confirm a critical action
   - You are not 100% confident in your ability to handle the task
   Then you MUST use the `request_help` tool to ask your supervisor for help.
5. Do not attempt tasks beyond your defined role
6. Always maintain consistency with your system prompt rules
7. When in doubt, ALWAYS request help rather than risk mistakes

Your supervisor will help ensure you operate effectively within your role while providing guidance for complex scenarios.

--------------------------------

SUBAGENT SYSTEM PROMPT:

{self._system_prompt}
"""
            self.set_system_prompt(subagent_prompt)

        if self.state.supervisor_agent == self.name and os.getenv("ENV") == "dev" and "DEVELOPPER SYSTEM PROMPT" not in self._system_prompt:
            dev_prompt = f"""
DEVELOPPER SYSTEM PROMPT:

For any questions/commands related to the project, use tool: `read_makefile` to get the information you need.

--------------------------------

AGENT SYSTEM PROMPT:

{self._system_prompt}
"""

            self.set_system_prompt(dev_prompt)
            
        if "CURRENT_DATE" not in self._system_prompt:
            from datetime import datetime
            current_date_str = f"CURRENT_DATE: The current date is {datetime.now().strftime('%Y-%m-%d')}\n"
            self._system_prompt = self._system_prompt + "\n" + current_date_str
            self.set_system_prompt(self._system_prompt)
            return Command(goto="current_active_agent")

        # logger.debug(f"💬 System prompt: {self._system_prompt}")
        return Command(goto="continue_conversation")
    
    def continue_conversation(self, state: MessagesState) -> Command:
        return Command(goto="call_model")

    def handle_openai_response_v1(self, response: BaseMessage) -> Command:
        content_str: str = ""
        tool_call: list[ToolCall] = []
        logger.debug(f"Chat model output version is responses/v1: {response}")
        
        if isinstance(response.content, list):
            # Parse response content
            for item in response.content:
                # Ensure item is a dict before accessing attributes
                if isinstance(item, dict):
                    # Get text content
                    if item.get("type") == "text":
                        text_content = item.get("text", "")
                        if isinstance(text_content, str):
                            content_str += text_content
                        
                        # Add sources from annotations if any
                        annotations = item.get("annotations", [])
                        if isinstance(annotations, list) and len(annotations) > 0:
                            content_str += "\n\n\n\n*Annotations:*\n"
                            for annotation in annotations:
                                if isinstance(annotation, dict) and annotation.get("type") == "url_citation":
                                    title = annotation.get('title', '')
                                    url = annotation.get('url', '')
                                    content_str += f"- [{title}]({url})\n"

                    if "action" in item:
                        tool_call.append(ToolCall(
                            name=item["type"],
                            args={"query": item["action"].get("query", "")},
                            id=item.get("id"),
                            type="tool_call"
                        ))
        
        # Create AIMessage with the content
        usage_metadata = None
        if hasattr(response, 'usage_metadata'):
            usage_metadata = response.usage_metadata
        ai_message = AIMessage(content=content_str, usage_metadata=usage_metadata)
        
        # If action was detected, notify tool usage
        if len(tool_call) > 0:
            # Use the ai_message which is already the correct type
            ai_message.tool_calls = tool_call
            self._notify_tool_usage(ai_message)
            tool_message = ToolMessage(
                content=content_str,
                tool_call_id=tool_call[0].get("id")
            )
            self._notify_tool_response(tool_message)
            return Command(goto="__end__", update={"messages": [tool_message, ai_message]})
        
        return Command(goto="__end__", update={"messages": [ai_message]})


    def call_model(
        self,
        state: MessagesState,
    ) -> Command[Literal["call_tools", "__end__"]]:
        self._state.set_current_active_agent(self.name)
        logger.debug(f"🧠 Calling model on current active agent: {self.name}")

        # Inserting system prompt before messages.
        messages = state["messages"]
        if self._system_prompt:
            messages = [
                SystemMessage(content=self._system_prompt),
            ] + messages

        # Calling model
        response: BaseMessage = self._chat_model_with_tools.invoke(messages)
        logger.debug(f"Model response content: {response.content if hasattr(response, 'content') else response}")

        # Handle tool calls if present
        if (
            isinstance(response, AIMessage)
            and hasattr(response, "tool_calls")
            and len(response.tool_calls) > 0
        ):
            tool_names = [tool_call["name"] for tool_call in response.tool_calls]
            logger.debug(f"⏩ Calling tools: {', '.join(tool_names)}")
            # TODO: Rethink this.
            # This is done to prevent an LLM to call multiple tools at once.
            # It's important because, as some tools are subgraphs, and that we are passing the full state, the subgraph will be able to mess with the state.
            # Therefore, if the LLM calls a tool here like the "add" method, and at the same time request the multiplication agent, the agent will mess with the state, and the result of the "add" tool will be lost.
            #### ----->  A solution would be to rebuild the state to make sure that the following message of a tool call it the response of that call. If we do that we should theroetically be able to call multiple tools at once, which would be more effective.
            # response.tool_calls = [response.tool_calls[0]]

            return Command(goto="call_tools", update={"messages": [response]})
        
        elif (
            self._chat_model_output_version == "responses/v1"
        ):
            return self.handle_openai_response_v1(response)

        return Command(goto="__end__", update={"messages": [response]})


    def call_tools(self, state: MessagesState) -> list[Command]:
        # Check if messages are present in the state.
        if "messages" not in state or not isinstance(state["messages"], list) or len(state["messages"]) == 0:
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

        # Initialize the called tools list.
        called_tools: list[BaseTool] = []
        for tool_call in tool_calls:
            tool_name: str = tool_call["name"]
            logger.debug(f"🛠️ Calling tool: {tool_name}")
            tool_: BaseTool = self._tools_by_name[tool_name]

            tool_input_fields = tool_.get_input_schema().model_json_schema()[
                "properties"
            ]

            # For tools with InjectedToolCallId, we must pass the full ToolCall object
            # according to LangChain's requirements
            args: dict[str, Any] | ToolCall = tool_call

            # Check if tool needs state injection
            if "state" in tool_input_fields:
                args = {**tool_call, "state": state} # inject state

            # Check if tool is a handoff tool
            is_handoff = tool_call["name"].startswith("transfer_to_")
            if is_handoff is True:
                args = {"state": state, "tool_call": {**tool_call, "role": "tool_call"}}
                
            # Try to invoke the tool.
            try:
                logger.debug(f"🔧 Tool arguments: {args.get('args')}")
                tool_response = tool_.invoke(args)
                logger.debug(f"📦 Tool response: {tool_response.content if hasattr(tool_response, 'content') else tool_response}")
                if (
                    tool_response is not None and 
                    hasattr(tool_response, "name") and 
                    tool_response.name == "request_help" and 
                    self._state.supervisor_agent != self.name
                ):
                    self._state.set_current_active_agent(self._state.supervisor_agent)
                    self._state.set_requesting_help(True)
                    results.append(Command(goto="current_active_agent", graph=Command.PARENT))
                    return results

                called_tools.append(tool_)

                # Handle tool response.
                if isinstance(tool_response, ToolMessage):
                    results.append(Command(update={"messages": [tool_response]}))
                elif isinstance(tool_response, Command):
                    results.append(tool_response)
                else:
                    logger.warning(f"Tool call {tool_name} returned an unexpected type: {type(tool_response)}")
                    results.append(Command(goto="__end__", update={"messages": [ToolMessage(content=str(tool_response), tool_call_id=tool_call["id"])]}))
            except Exception as e:
                logger.error(f"🚨 Tool call {tool_name} failed: {e}")
                results.append(Command(goto="__end__", update={"messages": [ToolMessage(content=f"Tool call {tool_name} failed: {str(e)}", tool_call_id=tool_call["id"])]}))

        assert len(results) > 0, state

        # Checking if every called tools has return_direct set to True.
        # This is used to know if we can send the ToolMessage to the call_model node.
        return_direct : bool = True
        for t in called_tools:
            if hasattr(t, "return_direct") and t.return_direct is False:
                return_direct = False
                break

        # If the last response is a ToolMessage, we want the model to interpret it.
        last_tool_reponse: ToolMessage | Command | None = pd.get(results[-1], 'update.messages[-1]', None)
        logger.debug(f"last_tool_reponse: {last_tool_reponse}")
        logger.debug(f"results -1: {results[-1]}")
        if (
            isinstance(last_tool_reponse, ToolMessage) and 
            hasattr(last_tool_reponse, "name") and
            last_tool_reponse.name is not None and
            not last_tool_reponse.name.startswith("transfer_to_")
        ):
            if return_direct is False:
                logger.debug(f"ToolMessage found in results SENDING TO CALL_MODEL: {results[-1]}")
                results.append(Command(goto="call_model"))
            else:
                logger.debug("Injecting ToolMessage into AIMessage for the user to see.")
                logger.debug(f"last_message: {last_message}")
                results.append(Command(update={"messages": [AIMessage(content=last_message.content)]}))

        return results

    @property
    def workflow(self) -> StateGraph:
        return self._workflow

    def _notify_tool_usage(self, message: AnyMessage):
        self._event_queue.put(ToolUsageEvent(payload=message))
        self._on_tool_usage(message)

    def _notify_tool_response(self, message: AnyMessage):
        self._event_queue.put(ToolResponseEvent(payload=message))
        self._on_tool_response(message)
    
    def _notify_ai_message(self, message: AnyMessage, agent_name: str):
        self._event_queue.put(AIMessageEvent(payload=message, agent_name=agent_name))
        self._on_ai_message(message, agent_name)

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
        """Register a callback to be called when an AI message is received.
        """
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
        notified = {}

        for chunk in self.graph.stream(
            {"messages": [HumanMessage(content=prompt)]},
            config={"configurable": {"thread_id": self._state.thread_id}},
            subgraphs=True,
        ):
            source, payload = chunk
            agent_name = self._name if len(source) == 0 else source[0].split(':')[0]
            if isinstance(payload, dict):
                last_messages = []                
                v = list(payload.values())[0]
                
                if v is None:
                    continue
                
                if isinstance(v, dict):
                    if "messages" in v and isinstance(v["messages"], list) and len(v["messages"]) > 0:
                        last_messages = [v["messages"][-1]]
                    else:
                        continue
                elif isinstance(v, list):
                    last_messages = []
                    for e in v:
                        if isinstance(e, dict) and "messages" in e and isinstance(e["messages"], list) and len(e["messages"]) > 0:
                            last_messages.append(e["messages"][-1])
                else:
                    continue


                for last_message in last_messages:
                    if isinstance(last_message, AIMessage):
                        if pd.get(last_message, "additional_kwargs.tool_calls"):
                            # This is a tool call.
                            self._notify_tool_usage(last_message)
                        else:
                            # This if is here to filter each source of AIMessage. Which means that it will notify ai message only if the methods:
                            # - call_model
                            # - call_tools
                            # are called.
                            # If you need another method to be able to return an AIMessage or a Command(..., update={"messages": [AIMessage(...)]}) we either need to add it to the list or have this specific method calling self._notify_ai_message directly.
                            
                            allowed_sources_of_ai_message = ['call_model', 'call_tools']
                            if any(source in payload for source in allowed_sources_of_ai_message):
                                self._notify_ai_message(last_message, agent_name)

                    elif isinstance(last_message, ToolMessage):
                        if last_message.id not in notified:
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

            assert isinstance(chunk, dict)

            chunks.append(chunk)

        if len(chunks) == 0:
            return ""

        last_chunk_values = list(chunks[-1].values())
        if len(last_chunk_values) == 0:
            return ""
        value = last_chunk_values[0]
        messages = []
        if isinstance(value, dict) and "messages" in value and isinstance(value["messages"], list):
            messages = value["messages"]
        elif isinstance(value, list) and len(value) > 0:
            last_item = value[-1]
            if isinstance(last_item, dict) and "messages" in last_item and isinstance(last_item["messages"], list):
                messages = last_item["messages"]

        if len(messages) == 0:
            return ""
        
        last_message = messages[-1]
        if hasattr(last_message, "content"):
            content = last_message.content
        else:
            content = str(last_message) if last_message is not None else ""
         # content = list(chunks[-1].values())[0]["messages"][-1].content

        return content

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

    def duplicate(self, queue: Queue | None = None, agent_shared_state: AgentSharedState | None = None) -> "Agent":
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
        agents: list[Agent] = [agent.duplicate(queue, shared_state) for agent in self._original_agents]

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

        class CompletionQuery(BaseModel):
            prompt: str = Field(..., description="The prompt to send to the agent")
            thread_id: str | int = Field(
                ..., description="The thread ID to use for the conversation"
            )

        @router.post(
            f"/{route_name}/completion" if route_name else "/completion",
            name=f"{name} completion",
            description=description,
            tags=tags,
        )
        def completion(query: CompletionQuery):
            if isinstance(query.thread_id, int):
                query.thread_id = str(query.thread_id)
            logger.debug(f"completion - current active agent: {self._state.current_active_agent}")
            logger.debug(f"completion - supervisor agent: {self._state.supervisor_agent}")

            new_agent = self.duplicate(queue=self._event_queue, agent_shared_state=self._state)
            new_agent.state.set_thread_id(query.thread_id)
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
            logger.debug(f"stream_completion - current active agent: {self._state.current_active_agent}")
            logger.debug(f"stream_completion - supervisor agent: {self._state.supervisor_agent}")

            new_agent = self.duplicate(queue=self._event_queue, agent_shared_state=self._state)
            new_agent.state.set_thread_id(query.thread_id)
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
            final_state = self.invoke(prompt)
            self._event_queue.put(FinalStateEvent(payload=final_state))

        from threading import Thread

        thread = Thread(target=run_invoke)
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
                        "data": str(message.payload.content),
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

        response = final_state
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
    tool_name = f"transfer_to_{agent.name}"

    @tool(tool_name)
    def handoff_to_agent(
        # # optionally pass current graph state to the tool (will be ignored by the LLM)
        state: Annotated[dict, InjectedState],
        # optionally pass the current tool call ID (will be ignored by the LLM)
        tool_call: Annotated[ToolCall, ToolCall],
        
    ):
        """Ask another agent for help."""
        agent_label = " ".join(
            word.capitalize() for word in agent.name.replace("_", " ").split()
        )
        
        tool_message = ToolMessage(
            content=f"Conversation transferred to {agent_label}",
            name=tool_name,
            tool_call_id=tool_call["id"],
        )

        agent.state.set_current_active_agent(agent.name)

        return Command(
            # navigate to another agent node in the PARENT graph
            goto=agent.name,
            graph=Command.PARENT if parent_graph else None,
            # This is the state update that the agent `agent_name` will see when it is invoked.
            # We're passing agent's FULL internal message history AND adding a tool message to make sure
            # the resulting chat history is valid. See the paragraph above for more information.
            update={"messages": state["messages"] + [tool_message]},
        )

    assert isinstance(handoff_to_agent, BaseTool)

    return handoff_to_agent