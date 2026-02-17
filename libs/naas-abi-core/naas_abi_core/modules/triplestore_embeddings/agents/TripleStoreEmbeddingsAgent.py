from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

NAME = "TripleStore Embeddings Agent"
DESCRIPTION = (
    "Helps users query and understand data stored in triple store and vector store."
)
AVATAR_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Rdf_logo.svg/1200px-Rdf_logo.svg.png"
SYSTEM_PROMPT = """<role>
You are a TripleStore Embeddings Agent, an expert agent that helps users query and understand data stored in triple store and vector store. 
</role>

<objective>
Your primary mission is to help users efficiently query and understand data stored in triple store and vector store. 
You exclusively use triple store and vector store queries to retrieve information. 
</objective>

<context>
You can only access information that exists in the triple store and vector store through the provided tools.
</context>

<tools>
[TOOLS]
</tools>

<tasks>
- Query the knowledge graph using the provided SPARQL query tools to answer the user's question
- Query the vector store using the provided vector store query tools to answer the user's question
- Reformat results into a natural language response answering the user's question
</tasks>

<operating_guidelines>
- Look for tools that can answer the user's question
- Use tool to answer the user's question
- If a question cannot be answered using the tools, respond with "I don't know"
</operating_guidelines>

<constraints>
- Be concise and to the point
- ONLY use triple store and vector store query tools to answer questions
- If information is not available in the triple store and vector store, respond with "I don't know".
</constraints>
"""

SUGGESTIONS: list[str] = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Initialize module
    from langchain_core.tools import tool
    from langchain_openai import OpenAIEmbeddings
    from naas_abi_core.modules.triplestore_embeddings import ABIModule
    from naas_abi_core.services.vector_store.VectorStoreService import (
        VectorStoreService,
    )
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model

    module: ABIModule = ABIModule.get_instance()

    # Add tools
    tools: list = []

    vector_store_service: VectorStoreService = module.engine.services.vector_store
    collection_name = module.configuration.collection_name
    embeddings_dimensions = module.configuration.embeddings_dimensions
    if module.configuration.embeddings_model_provider == "openai":
        embeddings_model = OpenAIEmbeddings(
            model=module.configuration.embeddings_model_name,
            dimensions=embeddings_dimensions,
        )
    else:
        raise ValueError(
            f"Embeddings model provider {module.configuration.embeddings_model_provider} not supported"
        )

    @tool(return_direct=True)
    def get_collection_size(collection_name: str) -> str:
        """Get the size of a collection in the vector store."""
        size = vector_store_service.get_collection_size(collection_name)
        return f"The collection '{collection_name}' contains {size} documents."

    tools.append(get_collection_size)

    @tool(return_direct=True)
    def list_collections() -> str:
        """List all collections in the vector store."""
        collections = vector_store_service.list_collections()
        collections_text = "\n".join([f"- {collection}" for collection in collections])
        return (
            f"The vector store contains the following collections:\n{collections_text}"
        )

    tools.append(list_collections)

    @tool(return_direct=True)
    def delete_collection(collection_name: str) -> str:
        """Delete a collection in the vector store."""
        vector_store_service.delete_collection(collection_name)
        return f"The collection '{collection_name}' has been deleted."

    tools.append(delete_collection)

    # Search tools for vector store
    from naas_abi_core.modules.triplestore_embeddings.workflows.CreateSearchToolWorkflow import (
        CreateSearchToolWorkflow,
        CreateSearchToolWorkflowConfiguration,
        CreateSearchToolWorkflowParameters,
    )

    workflow = CreateSearchToolWorkflow(
        CreateSearchToolWorkflowConfiguration(
            vector_store=vector_store_service,
            embeddings_model=embeddings_model,
        )
    )
    search_person_tool = workflow.create_search_tool(
        CreateSearchToolWorkflowParameters(
            tool_name="search_person_uri",
            tool_description="Search for a person URI by name",
            search_param_name="person_name",
            search_param_description="Name of the person to search for",
            collection_name=collection_name,
            search_filter={"type_label": "Person"},
        )
    )
    tools.append(search_person_tool)

    search_label = workflow.create_search_tool(
        CreateSearchToolWorkflowParameters(
            tool_name="search_label",
            tool_description="Search for a label by name",
            search_param_name="label_name",
            search_param_description="Name of the label to search for",
        )
    )
    tools.append(search_label)

    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=system_prompt,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return TripleStoreEmbeddingsAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class TripleStoreEmbeddingsAgent(Agent):
    """
    Command to run the agent:
        uv run abi chat naas_abi_core.modules.triplestore_embeddings TripleStoreEmbeddingsAgent
    """

    pass
