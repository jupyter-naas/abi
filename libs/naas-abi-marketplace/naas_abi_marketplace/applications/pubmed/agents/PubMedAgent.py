from __future__ import annotations

import concurrent.futures
import os
import tempfile
from typing import List, Optional, cast

from langchain_core.tools import BaseTool, Tool, tool
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class PubMedAgent(Agent):
    name: str = "PubMedAgent"
    description: str = "PubMedAgent is an agent that can search for papers in PubMed."
    system_prompt: str = """You are a PubMed Agent aimed to help users search for papers in PubMed.
When using tools, you might receive a Turtle serialized graph as a response.
You must always display the request results as a Markdown table.
"""

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "PubMedAgent":
        from naas_abi_core.engine.context import get_default_model_registry
        from naas_abi_marketplace.applications.pubmed import ABIModule
        from naas_abi_marketplace.applications.pubmed.integrations.PubMedAPI.PubMedAPI import (
            PubMedAPIConfiguration,
            PubMedIntegration,
        )
        from naas_abi_marketplace.applications.pubmed.pipelines.PubMedPipeline import (
            PubMedPipeline,
            PubMedPipelineConfiguration,
        )

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        object_storage = ABIModule.get_instance().engine.services.object_storage

        @tool(description="Download a PDF from PubMed Central using it's PMCID")
        def download_pdf(pmcids: List[str]) -> str:
            def _download_and_store(pmcid: str) -> None:
                print(f"Downloading {pmcid}")
                integration = PubMedIntegration(PubMedAPIConfiguration())
                stream = integration.download_pubmed_central_pdf(pmcid)

                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(stream.read())
                    pdf_path = temp_file.name

                with open(pdf_path, "rb") as pdf_file:
                    object_storage.put_object(
                        "pubmed/pdfs", f"{pmcid}.pdf", pdf_file.read()
                    )

                os.remove(pdf_path)

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                list(executor.map(_download_and_store, pmcids))

            return "PDFs downloaded and saved."

        pipeline = PubMedPipeline(PubMedPipelineConfiguration())
        tools = pipeline.as_tools()
        tools = cast(list[Tool | BaseTool | Agent], [cast(BaseTool, t) for t in tools]) + [download_pdf]

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(
                thread_id=str(__import__("uuid").uuid4().hex)
            )

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
