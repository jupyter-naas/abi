from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from typing import cast
from langchain_core.tools import Tool, BaseTool
from lib.abi.models.Model import ChatModel
from src.marketplace.applications.pubmed.pipelines.PubMedPipeline import PubMedPipeline, PubMedPipelineConfiguration

from src.core.abi.models.gpt_4_1 import model

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
