from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

NAME = "ArXivAgent"
DESCRIPTION = "Search and analyze research papers from ArXiv"
AVATAR_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/ArXiv_web.svg/1200px-ArXiv_web.svg.png"
SYSTEM_PROMPT = """You are an ArXiv research assistant. You can help users search for papers, get paper details, and analyze research trends.
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


def create_agent(
    agent_shared_state: AgentSharedState | None = None,
    agent_configuration: AgentConfiguration | None = None,
) -> Agent:
    """Creates an ArXiv assistant agent.

    Args:
        agent_shared_state (AgentSharedState, optional): Shared state for the agent
        agent_configuration (AgentConfiguration, optional): Configuration for the agent

    Returns:
        Agent: The configured ArXiv assistant agent
    """
    # Initialize module
    from naas_abi_marketplace.applications.arxiv import ABIModule
    module = ABIModule.get_instance()
    triple_store = module.engine.services.triple_store

    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model

    # Initialize tools
    tools: list = []
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

    # Add ArXiv integration and pipeline tools
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

    # Add ArXiv query workflow
    arxiv_query_workflow = ArXivQueryWorkflow(
        ArXivQueryWorkflowConfiguration(
            storage_path="storage/triplestore/application-level/arxiv"
        )
    )
    tools += arxiv_query_workflow.as_tools()

    # Use provided configuration or create default
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return ArXivAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class ArXivAgent(Agent):
    """Agent for interacting with ArXiv papers."""
    pass
