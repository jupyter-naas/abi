from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from src import secret
from fastapi import APIRouter
from src.marketplace.__demo__.workflows.ExecutePythonCodeWorkflow import ExecutePythonCodeWorkflow, ExecutePythonCodeWorkflowConfiguration
from enum import Enum
from typing import Optional
from pydantic import SecretStr
from langchain_core.tools import Tool, BaseTool

NAME = "BodoAgent"
MODEL = "gpt-4o"
TEMPERATURE = 0
DESCRIPTION = "An agent that can analyze large data with Bodo DataFrames"
# TODO: Add avatar
AVATAR_URL = "https://raw.githubusercontent.com/jupyter-naas/awesome-notebooks/refs/heads/master/.github/assets/logos/Naas.png"
SYSTEM_PROMPT = f"""
You are {NAME}, a data analysis assistant that uses Bodo DataFrames to efficiently explore and analyze datasets.
You can execute Python code through the ExecutePythonWorkflow tool to perform your analyses.

When a user asks a question involving data (e.g., describing a dataset, computing aggregates, or exploring patterns), you should:

 * Write a complete Python script to perform the analysis.

 * Always import bodo.pandas as pd at the top of the script (never use regular pandas).

 * Read data using pandas-style APIs (for example: `pd.read_parquet("/path/to/file"))`.

 * Perform any operations or computations using standard pandas syntax (groupby, describe, value_counts, etc.).

 * Print concise, readable outputs — summary statistics, shapes, missing value counts, or aggregates.

 * Avoid unsafe or network operations; only read data and compute results.

 * After running the workflow, summarize the findings in plain English.

Your responses should be short, factual, and focused on analytical insights rather than speculation.
"""
SUGGESTIONS = ["Summarize this CSV file: /path/to/file.csv"]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None
) -> Agent:
    # Init
    tools: list[Tool | BaseTool | Agent] = []

    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get('OPENAI_API_KEY'))
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    # Add tools
    config = ExecutePythonCodeWorkflowConfiguration(timeout=600, allow_imports=True)
    tools += ExecutePythonCodeWorkflow(config).as_tools()

    return BodoAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        state=agent_shared_state,
        configuration=agent_configuration,
        # memory is automatically configured based on POSTGRES_URL environment variable
    )

class BodoAgent(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME,
        description: str = "API endpoints to call the Bodo agent completion.",
        description_stream: str = "API endpoints to call the Bodo agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)