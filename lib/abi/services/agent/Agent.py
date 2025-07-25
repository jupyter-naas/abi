# Standard library imports for type hints
from typing import Callable, Literal, Any, Union, Sequence, Generator

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
from langgraph.graph import START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.graph.state import CompiledStateGraph

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from typing import Annotated, Optional
from langchain_core.messages import ToolMessage, ToolCall
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command
from enum import Enum

# Pydantic imports for schema validation
from pydantic import BaseModel, Field

from abi.utils.Expose import Expose

# Dataclass imports for configuration
from dataclasses import dataclass, field

from fastapi import APIRouter
from abi.utils.Logger import logger
from sse_starlette.sse import EventSourceResponse

from queue import Queue, Empty
import pydash as pd

class AgentSharedState:
    __thread_id: int

    def __init__(self, thread_id: int = 1):
        self._thread_id = thread_id

    @property
    def thread_id(self) -> int:
        return self._thread_id

    def set_thread_id(self, thread_id: int):
        self._thread_id = thread_id


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

    This class implements an agent that can engage in conversations and use tools through a workflow graph.
    It manages the interaction between a chat model and a set of tools, maintaining conversation state
    and handling tool usage in a structured way.

    Attributes:
        __name (str): The name of the agent
        __description (str): The description of the agent
        __chat_model (BaseChatModel): The underlying language model with tool binding capability
        __tools (list[Tool]): List of tools available to the agent
        __checkpointer (BaseCheckpointSaver): Component that handles saving conversation state
        __thread_id (int): Identifier for the current conversation thread
        __app (CompiledStateGraph): The compiled workflow graph
        __workflow (StateGraph): The workflow definition graph
        __on_tool_usage (Callable[[AnyMessage], None]): Callback triggered when a tool is used
        __on_tool_response (Callable[[AnyMessage], None]): Callback triggered when a tool responds

    The agent uses a graph-based workflow system where:
    - The agent node processes messages using the language model
    - The tools node executes tool actions
    - The workflow alternates between these nodes based on the agent's decisions

    The workflow is configured to:
    1. Start with the agent node
    2. Conditionally route to either tools or end based on agent output
    3. Route back to agent after tool usage
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
    _tools: list[Union[Tool, "Agent"]]
    _tools_by_name: dict[str, Union[Tool, BaseTool]]

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

    def __init__(
        self,
        name: str,
        description: str,
        chat_model: BaseChatModel,
        tools: list[Union[Tool, "Agent"]] = [],
        agents: list["Agent"] = [],
        memory: BaseCheckpointSaver = MemorySaver(),
        state: AgentSharedState = AgentSharedState(),
        configuration: AgentConfiguration = AgentConfiguration(),
        event_queue: Queue | None = None,
    ):
        """Initialize a new Agent instance.

        Args:
            chat_model (BaseChatModel): The language model to use for chat interactions.
                Should support tool binding.
            tools (list[Tool]): List of tools to make available to the agent.
            memory (BaseCheckpointSaver, optional): Component to save conversation state.
                Defaults to an in-memory saver.
        """
        self._name = name
        self._description = description
        self._system_prompt = configuration.system_prompt

        # We store the original list of provided tools. This will be usefull for duplication.
        self._tools = tools

        # Assertions
        assert isinstance(name, str)
        assert isinstance(description, str)

        # We assert agents
        for agent in agents:
            assert isinstance(agent, Agent)

        # We store the provided tools in __structured_tools because we will need to know which ones are provided by the user and which one are agents.
        # This is needed when we duplicate the agent.
        _structured_tools, _agents = self.prepare_tools(tools, agents)
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

        # TODO: Make sure the Agent does not call the version without tools.
        self._chat_model = chat_model
        self._chat_model_with_tools = chat_model.bind_tools(self._structured_tools)
        self._checkpointer = memory
        self._state = state

        self._configuration = configuration

        self._on_tool_usage = configuration.on_tool_usage
        self._on_tool_response = configuration.on_tool_response
        self._on_ai_message = configuration.on_ai_message

        # Initialize the event queue.
        if event_queue is None:
            self._event_queue = Queue()
        else:
            self._event_queue = event_queue

        # self._setup_workflow()

        self.build_graph()

    def prepare_tools(
        self, tools: list[Union[Tool, "Agent"]], agents: list
    ) -> tuple[list[Tool | BaseTool], list["Agent"]]:
        """
        If we have Agents in tools, we are properly loading them as handoff tools.
        It will effectively make the 'self' agent a supervisor agent.
        """
        _tools: list[Tool | BaseTool] = []
        _agents: list["Agent"] = []

        # We process tools knowing that they can either be StructutedTools or Agent.
        for t in tools:
            if isinstance(t, Agent):
                # TODO: We might want to duplicate the agent first.
                logger.debug(f"Agent passed as tool: {t}")
                _agents.append(t)
                for tool in t.as_tools():
                    _tools.append(tool)
            else:
                _tools.append(t)

        # We process agents that are not provided in tools.
        for agent in agents:
            if agent not in _agents:
                _agents.append(agent)
                for tool in agent.as_tools():
                    _tools.append(tool)

        return _tools, _agents

    def as_tools(self, parent_graph: bool = False) -> list[BaseTool]:
        return [make_handoff_tool(agent=self, parent_graph=parent_graph)]

    @property
    def state(self) -> AgentSharedState:
        return self._state

    def build_graph(self, patcher: Optional[Callable] = None):
        graph = StateGraph(MessagesState)
        graph.add_node(self.call_model)
        graph.add_edge(START, "call_model")

        graph.add_node(self.call_tools)
        # This is not needed because the call_tools is generating the proper Command to go to the right node after each tool call.
        # graph.add_edge("call_tools", "call_model")

        for agent in self._agents:
            logger.debug(f"Adding node {agent.name} in graph")
            graph.add_node(agent.name, agent.graph)
            # This makes sure that after calling an agent in a graph, we call the main model of the graph.
            #graph.add_edge(agent.name, "call_model")

        # Patcher is callable that can be passed and that will impact the graph before we compile it.
        # This is used to be able to give more flexibility about how the graph is being built.
        if patcher:
            graph = patcher(graph)

        self.graph = graph.compile(checkpointer=self._checkpointer)

    def call_model(
        self, state: MessagesState
    ) -> Command[Literal["call_tools", "__end__"]]:
        logger.info(f"call_model on: {self.name}")
        messages = state["messages"]
        if self._system_prompt:
            messages = [
                SystemMessage(content=self._system_prompt),
            ] + messages

        response: BaseMessage = self._chat_model_with_tools.invoke(messages)
        if (
            isinstance(response, AIMessage)
            and hasattr(response, "tool_calls")
            and len(response.tool_calls) > 0
        ):
            # TODO: Rethink this.
            # This is done to prevent an LLM to call multiple tools at once.
            # It's important because, as some tools are subgraphs, and that we are passing the full state, the subgraph will be able to mess with the state.
            # Therefore, if the LLM calls a tool here like the "add" method, and at the same time request the multiplication agent, the agent will mess with the state, and the result of the "add" tool will be lost.
            #### ----->  A solution would be to rebuild the state to make sure that the following message of a tool call it the response of that call. If we do that we should theroetically be able to call multiple tools at once, which would be more effective.
            # response.tool_calls = [response.tool_calls[0]]

            return Command(goto="call_tools", update={"messages": [response]})
        # else:
        #     self._configuration._noti((self._name, response))

        return Command(goto="__end__", update={"messages": [response]})

    def call_tools(self, state: MessagesState) -> list[Command]:
        last_message: AnyMessage = state["messages"][-1]
        if not isinstance(last_message, AIMessage) or not hasattr(
            last_message, "tool_calls"
        ) or len(last_message.tool_calls) == 0:
            logger.warning(f"No tool calls found in last message but call_tools was called: {last_message}")
            return [Command(goto="__end__", update={"messages": [last_message]})]

        tool_calls: list[ToolCall] = last_message.tool_calls

        assert len(tool_calls) > 0, state["messages"][-1]

        results: list[Command] = []
        for tool_call in tool_calls:
            tool_: BaseTool = self._tools_by_name[tool_call["name"]]

            tool_input_fields = tool_.get_input_schema().model_json_schema()[
                "properties"
            ]

            args: dict[str, Any] | ToolCall = tool_call

            # this is simplified for demonstration purposes and
            # is different from the ToolNode implementation
            if "state" in tool_input_fields:
                # inject state
                args = {**tool_call, "state": state}

            is_handoff = tool_call["name"].startswith("transfer_to_")
            if is_handoff is True:
                args = {"state": state, "tool_call_id": tool_call["id"]}
            try:
                tool_response = tool_.invoke(args)


                if isinstance(tool_response, ToolMessage):
                    results.append(Command(update={"messages": [tool_response]}))

                # handle tools that return Command directly
                elif isinstance(tool_response, Command):
                    results.append(tool_response)
                else:
                    raise ValueError(
                        f"Tool call {tool_call['name']} returned an unexpected type: {type(tool_response)}"
                    )
            except Exception as e:
                # If the tool call fails, we want the model to interpret it.
                results.append(Command(goto="__end__", update={"messages": [ToolMessage(content=str(e), tool_call_id=tool_call["id"])]}))

        assert len(results) > 0, state

        # If the last response is a ToolMessage, we want the model to interpret it.
        if isinstance(pd.get(results[-1], 'update.messages[-1]', None), ToolMessage):
            logger.debug(f"ToolMessage found in results SENDING TO CALL_MODEL: {results[-1]}")
            results.append(Command(goto="call_model"))

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

    def on_tool_response(self, callback: Callable[[AnyMessage], None]):
        """Register a callback to be called when a tool response is received.

        The callback will be invoked whenever a tool response message is processed,
        before passing the messages to the model.

        Args:
            callback (Callable[[AnyMessage], None]): Function to call with the message
                containing the tool response
        """
        self._on_tool_response = callback
        
    def on_ai_message(self, callback: Callable[[AnyMessage, str], None]):
        """Register a callback to be called when an AI message is received.
        """
        self._on_ai_message = callback

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

                logger.debug(f"payload: {payload}")
                # print(f"{left} {self} payload: {payload}")
                
                # agent_name = self._name
                # if 'call_model' not in payload:
                #     agent_name = list(payload.keys())[0]
                
                v = list(payload.values())[0]
                
                if v is None:
                    continue
                
                if isinstance(v, dict):
                    if "messages" in v:
                        last_messages = [v["messages"][-1]]
                    else:
                        continue
                else:
                    logger.debug(f"v: {v}")
                    last_messages = [e["messages"][-1] for e in v]


                for last_message in last_messages:

                    if isinstance(last_message, AIMessage):
                        if pd.get(last_message, "additional_kwargs.tool_calls"):
                            # This is a tool call.
                            self._notify_tool_usage(last_message)
                        else:
                            if 'call_model' in payload or 'intent_mapping_router' in payload:
                                self._notify_ai_message(last_message, agent_name)
                            # This is a message.
                            # print("\n\nIntermediate AI Message:")
                            # print(last_message.content)
                            # print(last_message)
                            # print('\n\n')
                            pass
                    elif isinstance(last_message, ToolMessage):
                        if last_message.id not in notified:
                            self._notify_tool_response(last_message)
                            notified[last_message.id] = True
                    else:
                        if "tool_call_id" in last_message:
                            if last_message["tool_call_id"] not in notified:
                                self._notify_tool_response(last_message)
                                notified[last_message["tool_call_id"]] = True
                        else:
                            print("\n\n Unknown message type:")
                            print(type(last_message))
                            print(last_message)
                            print("\n\n")

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

        content = list(chunks[-1].values())[0]["messages"][-1].content

        return content

    def reset(self):
        """Reset the agent's conversation state.

        This method increments the internal thread ID counter, effectively starting a new
        conversation thread. Any subsequent invocations will be processed as part of a
        new conversation context.
        """
        self._state.set_thread_id(self._state.thread_id + 1)

    def __tool_function(self, prompt: str) -> str:
        response = self.invoke(prompt)

        return response

    def duplicate(self, queue: Queue | None = None) -> "Agent":
        """Create a new instance of the agent with the same configuration.

        This method creates a deep copy of the agent with the same configuration
        but with its own independent state. This is useful when you need to run
        multiple instances of the same agent concurrently.

        Returns:
            Agent: A new Agent instance with the same configuration
        """
        # Initialize the tools list with the original list of tools.
        # tools = [tool for tool in self._structured_tools]
        tools: list[Tool] = [tool for tool in self._tools if isinstance(tool, Tool)]

        if queue is None:
            queue = Queue()

        # We duplicated each agent and add them as tools.
        # This will be recursively done for each sub agents.
        agents: list[Agent] = [agent.duplicate(queue) for agent in self._agents]

        new_agent = Agent(
            name=self._name,
            description=self._description,
            chat_model=self._chat_model,
            tools=tools + agents,
            memory=self._checkpointer,
            # TODO: Make sure that this is the behaviour we want.
            state=AgentSharedState(),  # Create new state instance
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
            thread_id: int = Field(
                ..., description="The thread ID to use for the conversation"
            )

        @router.post(
            f"/{route_name}/completion" if route_name else "/completion",
            name=f"{name} completion",
            description=description,
            tags=tags,
        )
        def completion(query: CompletionQuery):
            new_agent = self.duplicate()
            new_agent.state.set_thread_id(query.thread_id)
            return new_agent.invoke(query.prompt)

        @router.post(
            f"/{route_name}/stream-completion" if route_name else "/stream-completion",
            name=f"{name} stream completion",
            description=description_stream,
            tags=tags,
        )
        async def stream_completion(query: CompletionQuery):
            new_agent = self.duplicate()
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
                        "data": str(message.payload.content),
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
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        """Ask another agent for help."""
        agent_label = " ".join(
            word.capitalize() for word in agent.name.replace("_", " ").split()
        )
        tool_message = {
            "role": "tool",
            "content": f"Conversation transferred to {agent_label}",
            "name": tool_name,
            "tool_call_id": tool_call_id,
        }

        return Command(
            # navigate to another agent node in the PARENT graph
            goto=agent.name,
            graph=Command.PARENT if parent_graph else None,
            # This is the state update that the agent `agent_name` will see when it is invoked.
            # We're passing agent's FULL internal message history AND adding a tool message to make sure
            # the resulting chat history is valid. See the paragraph above for more information.
            update={"messages": state["messages"] + [tool_message]},
            # update={"messages": state["messages"]},
        )

    assert isinstance(handoff_to_agent, BaseTool)

    return handoff_to_agent
