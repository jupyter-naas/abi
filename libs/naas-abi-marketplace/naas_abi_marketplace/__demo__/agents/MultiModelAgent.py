from enum import Enum
from typing import Optional

from fastapi import APIRouter
from naas_abi import ABIModule
from naas_abi_core.models.Model import CanonicalModelId
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_marketplace.__demo__.workflows.ExecutePythonCodeWorkflow import (
    ExecutePythonCodeWorkflow,
    ExecutePythonCodeWorkflowConfiguration,
)

# from langchain_anthropic import ChatAnthropic
# from langchain_ollama import ChatOllama

NAME = "Multi_Models"
MODEL = CanonicalModelId.GPT_5_2
TEMPERATURE = None
AVATAR_URL = (
    "https://freepnglogo.com/images/all_img/chat-gpt-logo-vector-black-3ded.png"
)
DESCRIPTION = "A multi-model agent that can use different models to answer questions."
SYSTEM_PROMPT = """You have multiple agents, using different models. 
To answer a users questions, you need to call every model agents and present the different answers:
- Agent gpt-5.2
- Agent gpt-5-mini
- Agent gpt-5.5
Once every Model agents have been called you must call the "Comparison Agent" to compare the answers and present best and cons of each answer.
On your final outputs display all answers you received from the different Agents.
If the user asks for python code execution, you must call the "Python Code Execution Agent" to execute the code. 

Constraints:
- Must presents the results by agent as follow "> gpt-5.2 Agent" + 2 blank lines in the response.
"""

SUGGESTIONS = [
    {
        "label": "Compare AI Models Analysis",
        "value": "Analyze the impact of AI on healthcare across different models and compare their perspectives",
    },
    {
        "label": "Python Code Execution",
        "value": "Write and execute a Python function that calculates the Fibonacci sequence",
    },
    {
        "label": "Multi-Model Comparison",
        "value": "What are the key differences between renewable and non-renewable energy sources? Compare answers across models.",
    },
]


def create_agent(
    agent_shared_state: AgentSharedState | None = None,
    agent_configuration: AgentConfiguration | None = None,
) -> Agent:
    abi_module = ABIModule.get_instance()
    registry = abi_module.engine.services.model_registry

    def _chat_model(model_id: str):
        return registry.get_chat_model(model_id)

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    # Set tools
    python_code_execution_tools: list = []
    execute_python_code_workflow = ExecutePythonCodeWorkflow(
        ExecutePythonCodeWorkflowConfiguration()
    )
    python_code_execution_tools += execute_python_code_workflow.as_tools()

    return MultiModelAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=_chat_model(CanonicalModelId.GPT_5_2),
        state=agent_shared_state,
        configuration=agent_configuration,
        tools=[
            Agent(
                name="gpt-5.2_agent",
                description="A agent using gpt-5.2 that can answer questions.",
                chat_model=_chat_model(CanonicalModelId.GPT_5_2),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a agent that can answer questions."
                ),
            ),
            Agent(
                name="gpt-5-mini_agent",
                description="A agent using gpt-5-mini that can answer questions.",
                chat_model=_chat_model(CanonicalModelId.GPT_5_MINI),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a agent that can answer questions."
                ),
            ),
            Agent(
                name="gpt-5.5_agent",
                description="A agent using gpt-5.5 that can answer questions.",
                chat_model=_chat_model(CanonicalModelId.GPT_5_5),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a agent that can answer questions."
                ),
            ),
            Agent(
                name="comparison_agent",
                description="A agent that can compare the answers of the different models and present the best and cons of each answer.",
                chat_model=_chat_model(CanonicalModelId.GPT_5_MINI),
                tools=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a comparison agent. You can compare the answers of the different models and present the best and cons of each answer. You must return the best answer and the cons of the other answers."
                ),
            ),
            Agent(
                name="python_code_execution_agent",
                description="A agent that can execute python code.",
                chat_model=_chat_model(CanonicalModelId.GPT_5_MINI),
                tools=python_code_execution_tools,
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
