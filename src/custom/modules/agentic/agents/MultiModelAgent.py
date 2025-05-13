
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from src import secret
from langchain_openai import ChatOpenAI
from langchain_core.tools import Tool, tool
# from langchain_anthropic import ChatAnthropic
# from langchain_ollama import ChatOllama
from typing import Any

@tool
def execute_python_code(code: str) -> Any:
    """Execute python code."""
    try:
        import subprocess
        import tempfile
        import os
        
        # Create a temporary file to store the code
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as temp_file:
            temp_file.write(code.encode())
            temp_file_path = temp_file.name
        
        try:
            # Run the code in a separate process and capture output
            result = subprocess.run(
                ['python', temp_file_path],
                capture_output=True,
                text=True,
                timeout=10  # Set a timeout to prevent infinite execution
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
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None,
) -> Agent:
    
    class MultiModelAgent(Agent):
        pass
    
    #shared_state = AgentSharedState()
    
    return MultiModelAgent(
        name="multi_model_agent",
        description="A multi-model agent that can use different models to answer questions.",
        chat_model=ChatOpenAI(
            model="o3-mini", 
            temperature=1, 
            api_key=secret.get("OPENAI_API_KEY")
        ),
        tools=[
            Agent(
                name="o3-mini_agent",
                description="A agent using o3-mini that can answer questions.",
                chat_model=ChatOpenAI(
                    model="o3-mini", 
                    temperature=1, 
                    api_key=secret.get("OPENAI_API_KEY")
                ),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a agent that can answer questions."
                )
            ),
            Agent(
                name="gpt-4o-mini_agent",
                description="A agent using gpt-4o-mini that can answer questions.",
                chat_model=ChatOpenAI(
                    model="gpt-4o-mini", 
                    temperature=1, 
                    api_key=secret.get("OPENAI_API_KEY")
                ),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a agent that can answer questions."
                )
            ),
            Agent(
                name="gpt-4-1_agent",
                description="A agent using gpt-4.1 that can answer questions.",
                chat_model=ChatOpenAI(
                    model="gpt-4.1", 
                    temperature=1, 
                    api_key=secret.get("OPENAI_API_KEY")
                ),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a agent that can answer questions."
                )
            ),
            Agent(
                name="comparison_agent",
                description="A agent that can compare the answers of the different models and present the best and cons of each answer.",
                chat_model=ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=1,
                    api_key=secret.get("OPENAI_API_KEY")
                ),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a comparison agent. You can compare the answers of the different models and present the best and cons of each answer. You must return the best answer and the cons of the other answers."
                )
            ),
            Agent(
                name="python_code_execution_agent",
                description="A agent that can execute python code.",
                chat_model=ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=1,
                    api_key=secret.get("OPENAI_API_KEY")
                ),
                tools=[
                    execute_python_code
                ],
                configuration=AgentConfiguration(
                    system_prompt="You are a python code execution agent. You can execute python code and return the result. ONLY EXECUTE SAFE CODE THAT WON'T HARM THE SYSTEM. The PYTHON CODE MUST PRINT THE RESULT AND NOT RETURN IT FOR YOU TO GRAB THE RESULT."
                )
            )
        ],
        configuration=AgentConfiguration(
            system_prompt="""You have multiple agents, using different models. To answer a users questions, you need to call every model agents and present the different answers:
            - Agent o3-mini
            - Agent gpt-4o-mini
            - Agent gpt-4.1
            
            Once every Model agents have been called you must call the "Comparison Agent" to compare the answers and present best and cons of each answer.
            
            If the user asks for python code execution, you must call the "Python Code Execution Agent" to execute the code.
            """
        )
    )
