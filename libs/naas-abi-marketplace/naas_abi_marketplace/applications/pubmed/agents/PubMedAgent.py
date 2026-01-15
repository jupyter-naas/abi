from typing import cast
import concurrent.futures
import os

from langchain_core.tools import BaseTool, Tool
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    tool
)
from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model
from naas_abi_marketplace.applications.pubmed.pipelines.PubMedPipeline import (
    PubMedPipeline,
    PubMedPipelineConfiguration,
)
from naas_abi_marketplace.applications.pubmed.integrations.PubMedAPI.PubMedAPI import (
    PubMedIntegration,
    PubMedAPIConfiguration,
)
from naas_abi_marketplace.applications.pubmed import ABIModule
import tempfile
from typing import List
NAME = "PubMedAgent"
DESCRIPTION = "PubMedAgent is an agent that can search for papers in PubMed."
SYSTEM_PROMPT = """You are a PubMed Agent aimed to help users search for papers in PubMed.
When using tools, you might receive a Turtle serialized graph as a response.
You must always display the request results as a Markdown table.
"""


class PubMedAgent(Agent):
    pass

@tool(description="Download a PDF from PubMed Central using it's PMCID")
def download_pdf(pmcids: List[str]) -> str:
    object_storage = ABIModule.get_instance().engine.services.object_storage

    def _download_and_store(pmcid: str) -> None:
        print(f"Downloading {pmcid}")
        integration = PubMedIntegration(PubMedAPIConfiguration())
        stream = integration.download_pubmed_central_pdf(pmcid)

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(stream.read())
            pdf_path = temp_file.name

        with open(pdf_path, "rb") as pdf_file:
            object_storage.put_object("pubmed/pdfs", f"{pmcid}.pdf", pdf_file.read())

        os.remove(pdf_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(_download_and_store, pmcids))

    return "PDFs downloaded and saved."

def create_agent() -> PubMedAgent:
    pipeline = PubMedPipeline(PubMedPipelineConfiguration())
    tools = pipeline.as_tools()

    return PubMedAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=cast(ChatModel, model).model,
        tools=cast(list[Tool | BaseTool | Agent], [cast(BaseTool, t) for t in tools]) + [download_pdf],
        agents=[],
        state=AgentSharedState(thread_id=str(__import__("uuid").uuid4().hex)),
        configuration=AgentConfiguration(system_prompt=SYSTEM_PROMPT),
        memory=None,
    )
