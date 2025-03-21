from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from src import secret, services

NAME = "Uexample Assistant"
DESCRIPTION = "A brief description of what your assistant does."
MODEL = "o3-mini"  # Or another appropriate model
TEMPERATURE = 1
AVATAR_URL = "https://example.com/avatar.png"
SYSTEM_PROMPT = """You are the Uexample Assistant. Your role is to help users with tasks related to example.

You can perform the following tasks:
- Task 1
- Task 2
- Task 3

Always be helpful, concise, and focus on solving the user's problem."""

def create_agent(shared_state: AgentSharedState = None) -> Agent:
    """Creates a new instance of the Uexample Assistant."""
    # Configure the underlying chat model
    llm = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=secret.get_openai_api_key()
    )
    
    # Configure the agent
    config = AgentConfiguration(
        name=NAME,
        description=DESCRIPTION,
        model=MODEL,
        temperature=TEMPERATURE,
        system_prompt=SYSTEM_PROMPT,
        avatar_url=AVATAR_URL,
        shared_state=shared_state or AgentSharedState(),
    )
    
    # Create and return the agent
    agent = Agent(llm=llm, config=config)
    
    # Add tools to the agent (uncomment and modify as needed)
    # workflow = YourWorkflow(YourWorkflowConfiguration())
    # agent.add_tools(workflow.as_tools())
    
    return agent

# For testing purposes
if __name__ == "__main__":
    agent = create_agent()
    agent.run("Hello, I need help with example")

