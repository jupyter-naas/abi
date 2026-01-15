from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

NAME = "BodoAgent"
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
SUGGESTIONS = [
    {
        "label": "Summarize CSV",
        "value": "Summarize this CSV file: /path/to/file.csv",
    }
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Set model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    # Add tools
    tools: list = []
    from naas_abi_marketplace.__demo__.workflows.ExecutePythonCodeWorkflow import (
        ExecutePythonCodeWorkflow,
        ExecutePythonCodeWorkflowConfiguration,
    )

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
    )


class BodoAgent(Agent):
    pass
