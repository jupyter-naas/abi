# Standard library imports for type hints
from typing import Callable, Literal, Any

# LangChain Core imports for base components
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AnyMessage, SystemMessage
from langchain_core.tools import Tool, StructuredTool

# LangGraph imports for workflow and state management
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

# Pydantic imports for schema validation
from pydantic import BaseModel, Field

# Dataclass imports for configuration
from dataclasses import dataclass, field

class AgentSharedState:
    __thread_id: int

    def __init__(self, thread_id: int = 1):
        self.__thread_id = 1
        
    @property
    def thread_id(self) -> int:
        return self.__thread_id
    
    def set_thread_id(self, thread_id: int):
        self.__thread_id = thread_id

@dataclass
class AgentConfiguration:
    on_tool_usage: Callable[[AnyMessage], None] = field(default_factory=lambda: lambda _: None)
    on_tool_response: Callable[[AnyMessage], None] = field(default_factory=lambda: lambda _: None)
    system_prompt: str = field(default="You are a helpful assistant. If a tool you used did not return the result you wanted, look for another tool that might be able to help you. If you don't find a suitable tool. Just output 'I DONT KNOW'")

class Agent:
    
    """An Agent class that orchestrates interactions between a language model and tools.

    This class implements an agent that can engage in conversations and use tools through a workflow graph.
    It manages the interaction between a chat model and a set of tools, maintaining conversation state
    and handling tool usage in a structured way.

    Attributes:
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
    __chat_model: BaseChatModel
    __tools: list[Tool]
    __chekpointer: BaseCheckpointSaver
    __state: AgentSharedState
    
    __app: CompiledStateGraph
    __workflow: StateGraph
    __configuration: AgentConfiguration
    
    __on_tool_usage: Callable[[AnyMessage], None]
    __on_tool_response: Callable[[AnyMessage], None]

    def __init__(self, chat_model: BaseChatModel, tools: list[Tool], memory: BaseCheckpointSaver = MemorySaver(), state: AgentSharedState = AgentSharedState(), configuration: AgentConfiguration = AgentConfiguration()):
        """Initialize a new Agent instance.
        
        Args:
            chat_model (BaseChatModel): The language model to use for chat interactions.
                Should support tool binding.
            tools (list[Tool]): List of tools to make available to the agent.
            memory (BaseCheckpointSaver, optional): Component to save conversation state.
                Defaults to an in-memory saver.
        """
        self.__tools = tools
        self.__chat_model = chat_model.bind_tools(self.__tools)
        self.__checkpointer = memory
        self.__state = state
        
        self.__configuration = configuration

        self.__on_tool_usage = configuration.on_tool_usage
        self.__on_tool_response = configuration.on_tool_response
        
        self.__setup_workflow()
        
    def __setup_workflow(self):
        """Set up the workflow graph for agent-tool interaction.
        
        Creates a StateGraph with two main nodes:
        - 'agent': Processes messages using the language model
        - 'tools': Executes tool actions when requested
        
        The workflow starts at the agent node and conditionally routes to either:
        - The tools node if the agent requests a tool
        - End if the agent completes the task
        
        After tool execution, control returns to the agent node.
        """
        workflow = StateGraph(MessagesState)

        # Define the two nodes we will cycle between
        workflow.add_node("agent", self.__call_model)
        workflow.add_node("tools", ToolNode(self.__tools))

        # Set the entrypoint as `agent`
        # This means that this node is the first one called
        workflow.add_edge(START, "agent")

        # We now add a conditional edge
        workflow.add_conditional_edges(
            # First, we define the start node. We use `agent`.
            # This means these are the edges taken after the `agent` node is called.
            "agent",
            # Next, we pass in the function that will determine which node is called next.
            self.__should_continue,
        )


        # We now add a normal edge from `tools` to `agent`.
        # This means that after `tools` is called, `agent` node is called next.
        workflow.add_edge("tools", 'agent')


        self.__workflow = workflow

        # Finally, we compile it!
        # This compiles it into a LangChain Runnable,
        # meaning you can use it as you would any other runnable.
        # Note that we're (optionally) passing the memory when compiling the graph
        self.__app = workflow.compile(checkpointer=self.__checkpointer)

    def workflow_compile(self) -> None:
        self.__app = self.__workflow.compile(checkpointer=self.__checkpointer)
        
    @property
    def workflow(self) -> StateGraph:
        return self.__workflow
    
    
    def __should_continue(self, state: MessagesState) -> Literal["tools", END]:
        """Determine the next node in the workflow based on the current state.
        
        Examines the last message in the state to determine if a tool call is needed.
        If the last message contains tool calls, routes to the 'tools' node.
        Otherwise, ends the workflow.
        
        Args:
            state (MessagesState): The current workflow state containing message history
            
        Returns:
            Literal["tools", END]: Either "tools" to execute a tool call, or END to complete
        """
        messages = state['messages']
        last_message = messages[-1]
        # If the LLM makes a tool call, then we route to the "tools" node
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            self.__on_tool_usage(last_message)
            return "tools"
        return END
        
    def __call_model(self, state: MessagesState):
        """Process the current state through the model.
        
        Takes the current message state and:
        1. Checks if the last message was a tool response and triggers callback if so
        2. Invokes the chat model with the messages
        3. Returns the model response wrapped in a messages dict
        
        Args:
            state (MessagesState): Current workflow state containing message history
            
        Returns:
            dict: New state containing the model's response message
        """
        messages = state['messages']
        last_message = messages[-1]
        if hasattr(last_message, 'tool_call_id'):
            self.__on_tool_response(last_message)
        response = self.__chat_model.invoke(messages)
        # We return a list, because this will get added to the existing list
        return {"messages": [response]}
    
    def on_tool_usage(self, callback: Callable[[AnyMessage], None]):
        """Register a callback to be called when a tool is used.
        
        The callback will be invoked whenever the model makes a tool call,
        before the tool is actually executed.
        
        Args:
            callback (Callable[[AnyMessage], None]): Function to call with the message
                containing the tool call
        """
        self.__on_tool_usage = callback
        
    def on_tool_response(self, callback: Callable[[AnyMessage], None]):
        """Register a callback to be called when a tool response is received.
        
        The callback will be invoked whenever a tool response message is processed,
        before passing the messages to the model.
        
        Args:
            callback (Callable[[AnyMessage], None]): Function to call with the message
                containing the tool response
        """
        self.__on_tool_response = callback
        
    @property
    def app(self):
        """Get the underlying Langchain app.
        This property exposes the underlying Langchain app for advanced usage scenarios.
        Users can call app.invoke() directly with custom message sequences and configurations
        if they need more control than the standard invoke() method provides.
        
        Returns:
            RunnableSequence: The Langchain runnable sequence that processes messages
        """
        return self.__app
    
    def invoke(self, prompt: str) -> str:
        """Process a user prompt through the agent and return the response.
        
        This method takes a text prompt from the user, processes it through the underlying
        Langchain app, and returns the model's response. The prompt is wrapped in a
        HumanMessage and processed in a new message sequence.
        
        Args:
            prompt (str): The user's text prompt to process
            
        Returns:
            str: The model's response text
        """
        final_state = self.__app.invoke(
            {"messages": [SystemMessage(content=self.__configuration.system_prompt), HumanMessage(content=prompt)]},
            config={"configurable": {"thread_id": self.__state.thread_id}}
        )
        return final_state["messages"][-1].content
    
    def reset(self):
        """Reset the agent's conversation state.
        
        This method increments the internal thread ID counter, effectively starting a new
        conversation thread. Any subsequent invocations will be processed as part of a
        new conversation context.
        """
        self.__thread_id += 1
    
    def __tool_function(self, prompt: str) -> str:
        response = self.invoke(prompt)
        
        return response
    
    def as_tool(self, name: str, description: str) -> StructuredTool:
        class AgentToolSchema(BaseModel):
            prompt: str = Field(..., description="The prompt to send to the agent")
        
        return StructuredTool(
            name=name,
            description=description,
            func=self.__tool_function,
            args_schema=AgentToolSchema
        )