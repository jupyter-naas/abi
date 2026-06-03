from __future__ import annotations

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class ArXivAgent(Agent):
    """Agent for interacting with ArXiv papers."""

    name: str = "ArXivAgent"
    description: str = "Search and analyze research papers from ArXiv"
    avatar_url: str = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/ArXiv_web.svg/1200px-ArXiv_web.svg.png"
    system_prompt: str = """You are an ArXiv research assistant. You can help users search for papers, get paper details, and analyze research trends.
You have access to the following tools:
- search_arxiv_papers: Search for papers on ArXiv
- get_arxiv_paper: Get metadata for a specific paper
- arxiv_paper_pipeline: Add papers to the knowledge graph and download PDFs
- query_arxiv_authors: Find the authors of a paper in the knowledge graph
- query_arxiv_papers: Find papers by author or category in the knowledge graph
- execute_arxiv_query: Run a custom SPARQL query on the knowledge graph

When users ask about papers, first search for relevant papers using search_arxiv_papers.
Then you can get detailed information about specific papers using get_arxiv_paper.
Use arxiv_paper_pipeline to add important papers to the knowledge graph for future reference.
Use the query tools to search for information in papers you've already added to the knowledge graph."""

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
    ) -> ArXivAgent:
        from naas_abi_core.engine.context import get_default_model_registry

        from naas_abi_marketplace.applications.arxiv import ABIModule
        from naas_abi_marketplace.applications.arxiv.integrations.ArXivIntegration import (
            ArXivIntegration,
            ArXivIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.arxiv.pipelines.ArXivPaperPipeline import (
            ArXivPaperPipeline,
            ArXivPaperPipelineConfiguration,
        )
        from naas_abi_marketplace.applications.arxiv.workflows.ArXivQueryWorkflow import (
            ArXivQueryWorkflow,
            ArXivQueryWorkflowConfiguration,
        )

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        module = ABIModule.get_instance()
        triple_store = module.engine.services.triple_store

        tools: list = []

        arxiv_integration_config = ArXivIntegrationConfiguration()
        tools += ArXivIntegration.as_tools(arxiv_integration_config)

        arxiv_pipeline = ArXivPaperPipeline(
            ArXivPaperPipelineConfiguration(
                arxiv_integration_config=arxiv_integration_config,
                triple_store=triple_store,
                storage_base_path="storage/triplestore/application-level/arxiv",
                pdf_storage_path="datastore/application-level/arxiv",
            )
        )
        tools += arxiv_pipeline.as_tools()

        arxiv_query_workflow = ArXivQueryWorkflow(
            ArXivQueryWorkflowConfiguration(
                storage_path="storage/triplestore/application-level/arxiv"
            )
        )
        tools += arxiv_query_workflow.as_tools()

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
