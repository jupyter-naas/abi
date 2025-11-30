from typing import cast

from langchain_core.tools import BaseTool, Tool
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model
from naas_abi_marketplace.applications.pubmed.pipelines.PubMedPipeline import (
    PubMedPipeline,
    PubMedPipelineConfiguration,
)

NAME = "PubMedAgent"
DESCRIPTION = "PubMedAgent is an agent that can search for papers in PubMed."
SYSTEM_PROMPT = """You are a PubMed Agent aimed to help users search for papers in PubMed.
When using tools, you might receive a Turtle serialized graph as a response.
You must always display the request results as a Markdown table.
"""


class PubMedAgent(Agent):
    pass


def create_agent() -> PubMedAgent:
    pipeline = PubMedPipeline(PubMedPipelineConfiguration())
    tools = pipeline.as_tools()

    return PubMedAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=cast(ChatModel, model).model,
        tools=cast(list[Tool | BaseTool | Agent], [cast(BaseTool, t) for t in tools]),
        agents=[],
        state=AgentSharedState(thread_id=str(__import__("uuid").uuid4().hex)),
        configuration=AgentConfiguration(system_prompt=SYSTEM_PROMPT),
        memory=None,
    )
