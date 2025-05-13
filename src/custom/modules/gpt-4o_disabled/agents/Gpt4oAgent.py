from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, StateGraph
from typing import Dict, Any, List
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import HumanMessage, AIMessage
import os
from ..integrations.OpenAIGpt4oIntegration import OpenAIGpt4oIntegration

def create_agent():
    """Create a GPT-4o agent for general purpose tasks."""
    
    # Initialize the integration
    integration = OpenAIGpt4oIntegration()
    
    # Define the system prompt
    system_prompt = """You are GPT-4o, a model by OpenAI, capable of handling various tasks including text generation, analysis, and multimodal inputs.
    
    You have access to the following tools:
    - Text generation and analysis
    - Structured output generation
    - Vision analysis (when images are provided)
    
    Always provide clear, concise, and accurate responses. When dealing with images, describe what you see in detail.
    """
    
    # Define the prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Define the logic to execute tools based on agent actions
    def _should_continue(state: Dict[str, Any]) -> str:
        """Determine if the agent should continue or finish."""
        if isinstance(state["agent_outcome"], AgentFinish):
            return END
        else:
            return "continue"
    
    # Define the state schema
    class AgentState:
        """State for the GPT-4o agent."""
        
        def __init__(
            self,
            messages: List = None,
            agent_outcome: Any = None,
            agent_scratchpad: List = None,
        ):
            self.messages = messages or []
            self.agent_outcome = agent_outcome
            self.agent_scratchpad = agent_scratchpad or []
            
    # Define the graph nodes
    def run_agent(state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the agent on the current state."""
        messages = state["messages"]
        agent_scratchpad = state.get("agent_scratchpad", [])
        
        # Prepare input for the LLM
        prompt_args = {"messages": messages, "agent_scratchpad": agent_scratchpad}
        
        # Get the last message for the current input
        last_message = messages[-1] if messages else None
        current_input = last_message.content if last_message and isinstance(last_message, HumanMessage) else ""
        
        # Check if this is an image analysis request (placeholder for future implementation)
        is_image_request = False  # This would be determined by the content type
        
        # Generate the agent's response
        if is_image_request:
            # Handle image analysis (placeholder)
            response = "Image analysis would be performed here."
        else:
            # Handle text generation
            response = integration.create_chat_completion(
                prompt=current_input,
                system_prompt=system_prompt,
            )
        
        # Create an agent finish with the response
        agent_outcome = AgentFinish(
            return_values={"output": response},
            log="",
        )
        
        # Update the state
        return {"agent_outcome": agent_outcome}
    
    def process_action(state: Dict[str, Any]) -> Dict[str, Any]:
        """Process an agent action."""
        # This would handle tool calls in a more complex agent
        return state
    
    # Define the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", run_agent)
    workflow.add_node("action", process_action)
    
    # Add edges
    workflow.add_edge("agent", _should_continue)
    workflow.add_conditional_edges(
        "agent",
        lambda state: "action" if isinstance(state["agent_outcome"], AgentAction) else END,
        {
            "action": "action",
            END: END,
        },
    )
    workflow.add_edge("action", "agent")
    
    # Set the entry point
    workflow.set_entry_point("agent")
    
    # Compile the graph
    graph = workflow.compile()
    
    # Define the invoke function
    def invoke(query: str) -> str:
        """Invoke the agent with a query."""
        messages = [HumanMessage(content=query)]
        result = graph.invoke({"messages": messages})
        return result["agent_outcome"].return_values["output"]
    
    # Define the agent class
    class Gpt4oAgent:
        """A wrapper class for the GPT-4o agent."""
        
        def __init__(self):
            self.name = "gpt4o_agent"
            self.description = "A general purpose agent powered by GPT-4o."
            self.invoke = invoke
    
    # Return the agent instance
    return Gpt4oAgent() 