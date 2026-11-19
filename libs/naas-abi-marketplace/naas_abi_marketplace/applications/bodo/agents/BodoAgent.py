from __future__ import annotations

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class BodoAgent(Agent):
    """Bodo DataFrames analysis, run in the caller's own coding workspace.

    The agent carries no code runner of its own: never the engine host.
    """

    name: str = "BodoAgent"
    description: str = "An agent that can analyze large data with Bodo DataFrames"
    avatar_url: str = "https://raw.githubusercontent.com/jupyter-naas/awesome-notebooks/refs/heads/master/.github/assets/logos/Naas.png"
    system_prompt: str = """
You are BodoAgent, a data analysis assistant that uses Bodo DataFrames to efficiently explore and analyze datasets.
You run Python only in the user's own coding workspace: write the script with `write_file`, then run it with `run_terminal` (for example `python analysis.py`). Those tools exist only when a coding workspace is connected to the conversation; without one, say that the analysis needs a coding workspace (open one in Code) and do not pretend to run anything.

When a user asks a question involving data (e.g., describing a dataset, computing aggregates, or exploring patterns), you should:

 * Write a complete Python script to perform the analysis.

 * Always import bodo.pandas as pd at the top of the script (never use regular pandas).

 * Read data from files in the workspace using pandas-style APIs (for example: `pd.read_parquet("data/file.parquet")`).

 * Perform any operations or computations using standard pandas syntax (groupby, describe, value_counts, etc.).

 * Print concise, readable outputs — summary statistics, shapes, missing value counts, or aggregates.

 * Avoid unsafe or network operations; only read data and compute results.

 * After running the script, summarize the findings in plain English.

Your responses should be short, factual, and focused on analytical insights rather than speculation.
"""
    suggestions: list = [
        {
            "label": "Summarize CSV",
            "value": "Summarize this CSV file of my workspace: data/file.csv",
        }
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
    ) -> BodoAgent:
        from naas_abi_marketplace.applications.bodo import ABIModule

        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        # No tool of its own runs code: scripts run in the caller's coding
        # workspace, through the default workspace tools (write_file,
        # run_terminal), which act only on the workspace bound to the request.
        tools: list = []

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=[],
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
