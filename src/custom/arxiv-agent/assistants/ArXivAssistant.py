from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret, config
from src.integrations.ArXivIntegration import ArXivIntegration, ArXivIntegrationConfiguration
from src.pipelines.arxiv.ArXivPaperPipeline import ArXivPaperPipeline, ArXivPaperPipelineConfiguration
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService

NAME = "ArXiv Assistant"
DESCRIPTION = "Search and analyze research papers from ArXiv"
SYSTEM_PROMPT = """You are an ArXiv research assistant. You can help users search for papers, get paper details, and analyze research trends.
You have access to the following tools:
- search_arxiv_papers: Search for papers on ArXiv
- get_arxiv_paper: Get metadata for a specific paper
- arxiv_paper_pipeline: Add papers to the knowledge graph

When users ask about papers, first search for relevant papers using search_arxiv_papers. Then you can get detailed information about specific papers using get_arxiv_paper.
Use arxiv_paper_pipeline to add important papers to the knowledge graph for future reference."""

class ArXivAssistant(Agent):
    """Assistant for interacting with ArXiv papers."""
    pass

def create_arxiv_agent(
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
    ontology_store = OntologyStoreService(
        OntologyStoreService__SecondaryAdaptor__Filesystem(
            store_path=config.ontology_store_path
        )
    )

    # Add ArXiv integration and pipeline tools
    arxiv_integration_config = ArXivIntegrationConfiguration()
    tools += ArXivIntegration.as_tools(arxiv_integration_config)

    arxiv_pipeline = ArXivPaperPipeline(
        ArXivPaperPipelineConfiguration(
            arxiv_integration_config=arxiv_integration_config,
            ontology_store=ontology_store
        )
    )
    tools += arxiv_pipeline.as_tools()

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