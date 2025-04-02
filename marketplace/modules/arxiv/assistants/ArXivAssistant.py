from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret, config
from src.custom.modules.arxiv_agent.integrations.ArXivIntegration import ArXivIntegration, ArXivIntegrationConfiguration
from src.custom.modules.arxiv_agent.pipelines.ArXivPaperPipeline import ArXivPaperPipeline, ArXivPaperPipelineConfiguration
from abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import TripleStoreService__SecondaryAdaptor__Filesystem
from abi.services.triple_store.TripleStoreService import TripleStoreService
from src.custom.modules.arxiv_agent.workflows.ArXivQueryWorkflow import ArXivQueryWorkflow, ArXivQueryWorkflowConfiguration

NAME = "ArXiv Assistant"
SLUG = "arxiv-assistant"
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

class ArXivAssistant(Agent):
    """Assistant for interacting with ArXiv papers."""
    pass

def create_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None
) -> Agent:
    """Creates an ArXiv assistant agent.
    
    Args:
        agent_shared_state (AgentSharedState, optional): Shared state for the agent
        agent_configuration (AgentConfiguration, optional): Configuration for the agent
            
    Returns:
        Agent: The configured ArXiv assistant agent
    """
    # Initialize model
    model = ChatOpenAI(
        model="gpt-4",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Initialize tools
    tools = []
    
    # Initialize ontology store
    triple_store = TripleStoreService(
        TripleStoreService__SecondaryAdaptor__Filesystem(
            store_path=config.triple_store_path
        )
    )

    # Add ArXiv integration and pipeline tools
    arxiv_integration_config = ArXivIntegrationConfiguration()
    tools += ArXivIntegration.as_tools(arxiv_integration_config)

    arxiv_pipeline = ArXivPaperPipeline(
        ArXivPaperPipelineConfiguration(
            arxiv_integration_config=arxiv_integration_config,
            triple_store=triple_store,
            storage_base_path="storage/triplestore/application-level/arxiv",
            pdf_storage_path="datastore/application-level/arxiv"
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
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )

    # Use provided shared state or create new
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return ArXivAssistant(
        name="arxiv_assistant",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 