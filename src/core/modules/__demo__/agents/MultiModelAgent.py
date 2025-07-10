from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from src import secret
from langchain_openai import ChatOpenAI
from typing import Any, Optional
from pydantic import SecretStr
from fastapi import APIRouter
from enum import Enum
from langchain_core.tools import tool, StructuredTool
# from langchain_anthropic import ChatAnthropic
# from langchain_ollama import ChatOllama

NAME = "Multi_Models"
MODEL = "o3-mini"
TEMPERATURE = None
AVATAR_URL = "https://freepnglogo.com/images/all_img/chat-gpt-logo-vector-black-3ded.png"
DESCRIPTION = "A multi-model agent that can use different models to answer questions."
SYSTEM_PROMPT = """You have multiple agents, using different models. 
To answer a users questions, you need to call every model agents and present the different answers:
- Agent o3-mini
- Agent gpt-4o-mini
- Agent gpt-4.1
Once every Model agents have been called you must call the "Comparison Agent" to compare the answers and present best and cons of each answer.
On your final outputs display all answers you received from the different Agents.
If the user asks for python code execution, you must call the "Python Code Execution Agent" to execute the code. 

Constraints:
- Must presents the results by agent as follow "> o3-mini Agent" + 2 blank lines in the response.
"""

SUGGESTIONS = [
    {
        "label": "Compare AI Models Analysis",
        "value": "Analyze the impact of AI on healthcare across different models and compare their perspectives"
    },
    {
        "label": "Python Code Execution",
        "value": "Write and execute a Python function that calculates the Fibonacci sequence"
    },
    {
        "label": "Multi-Model Comparison",
        "value": "What are the key differences between renewable and non-renewable energy sources? Compare answers across models."
    }
]

@tool
def execute_python_code(code: str) -> Any:
    """Execute python code."""
    try:
        import subprocess
        import tempfile
        import os

        # Create a temporary file to store the code
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
            temp_file.write(code.encode())
            temp_file_path = temp_file.name

        try:
            # Run the code in a separate process and capture output
            result = subprocess.run(
                ["python", temp_file_path],
                capture_output=True,
                text=True,
                timeout=10,  # Set a timeout to prevent infinite execution
            )

            # Return stdout or stderr if there was an error
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error: {result.stderr}"
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    except Exception as e:
        return f"Error: {e}"

def create_agent(
    agent_shared_state: AgentSharedState | None = None, 
    agent_configuration: AgentConfiguration | None = None
) -> Agent:
    
    # Set model
    model = ChatOpenAI(
        model="o3-mini",
        temperature=1, 
        api_key=SecretStr(secret.get('OPENAI_API_KEY'))
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Set tools
    execute_python_code_tool = StructuredTool(
        name="execute_python_code", 
        description="Execute python code.",
        func=execute_python_code,
        args_schema=None
    )

    return MultiModelAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        state=agent_shared_state,
        configuration=agent_configuration,
        tools=[
            Agent(
                name="o3-mini_agent",
                description="A agent using o3-mini that can answer questions.",
                chat_model=ChatOpenAI(
                    model="o3-mini", temperature=1, api_key=SecretStr(secret.get("OPENAI_API_KEY"))
                ),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a agent that can answer questions."
                ),
            ),
            Agent(
                name="gpt-4o-mini_agent",
                description="A agent using gpt-4o-mini that can answer questions.",
                chat_model=ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=1,
                    api_key=SecretStr(secret.get("OPENAI_API_KEY")),
                ),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a agent that can answer questions."
                ),
            ),
            Agent(
                name="gpt-4-1_agent",
                description="A agent using gpt-4.1 that can answer questions.",
                chat_model=ChatOpenAI(
                    model="gpt-4.1", temperature=1, api_key=SecretStr(secret.get("OPENAI_API_KEY"))
                ),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a agent that can answer questions."
                ),
            ),
            Agent(
                name="comparison_agent",
                description="A agent that can compare the answers of the different models and present the best and cons of each answer.",
                chat_model=ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=1,
                    api_key=SecretStr(secret.get("OPENAI_API_KEY")),
                ),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a comparison agent. You can compare the answers of the different models and present the best and cons of each answer. You must return the best answer and the cons of the other answers."
                ),
            ),
            Agent(
                name="python_code_execution_agent",
                description="A agent that can execute python code.",
                chat_model=ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=1,
                    api_key=SecretStr(secret.get("OPENAI_API_KEY")),
                ),
                tools=[execute_python_code_tool],
                configuration=AgentConfiguration(
                    system_prompt="You are a python code execution agent. You can execute python code and return the result. ONLY EXECUTE SAFE CODE THAT WON'T HARM THE SYSTEM. The PYTHON CODE MUST PRINT THE RESULT AND NOT RETURN IT FOR YOU TO GRAB THE RESULT."
                ),
            ),
        ],
    )

class MultiModelAgent(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = NAME,
        name: str = NAME.capitalize().replace("_", " "),
        description: str = "API endpoints to call the Multi Model Agent completion.", 
        description_stream: str = "API endpoints to call the Multi Model Agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )