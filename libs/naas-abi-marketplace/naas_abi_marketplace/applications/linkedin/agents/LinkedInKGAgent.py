from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

NAME = "LinkedIn_KG"
DESCRIPTION = (
    "Helps users query and understand LinkedIn data stored in a knowledge graph."
)
AVATAR_URL = "https://content.linkedin.com/content/dam/me/business/en-us/amp/brand-site/v2/bg/LI-Bug.svg.original.svg"
SYSTEM_PROMPT = """<role>
You are a LinkedIn Knowledge Graph Agent, an expert agent that helps users query and understand LinkedIn data stored in a knowledge graph. 
</role>

<objective>
Your primary mission is to help users efficiently query and understand LinkedIn data stored in the knowledge graph. 
You exclusively use knowledge graph queries (SPARQL) to retrieve information. 
</objective>

<context>
You can only access information that exists in the knowledge graph through the provided SPARQL query tools.
</context>

<tools>
[TOOLS]
</tools>

<tasks>
- Query the knowledge graph using the provided SPARQL query tools to answer the user's question
- Reformat results into a natural language response answering the user's question
</tasks>

<operating_guidelines>
- Understand the user's question and determine if it can be answered using the knowledge graph
- Use predefined tools to answer the user's question
- If multiple results are found for persons or organizations, ask the user to select the one they want to use.
- If a question cannot be answered using the predefined tools, respond with "I don't know"
</operating_guidelines>

<constraints>
- Be concise and to the point
- ONLY use SPARQL query tools to answer questions
- If information is not available in the knowledge graph, respond with "I don't know".
</constraints>
"""

SUGGESTIONS: list[str] = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Initialize module
    from naas_abi_core.module.Module import BaseModule
    from naas_abi_core.modules.templatablesparqlquery import (
        ABIModule as TemplatableSparqlQueryABIModule,
    )
    from naas_abi_core.modules.triplestore_embeddings import (
        ABIModule as TriplestoreEmbeddingsABIModule,
    )
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model
    from naas_abi_marketplace.applications.linkedin import ABIModule

    # Add tools
    tools: list = []
    templatable_sparql_query_module: BaseModule = (
        ABIModule.get_instance().engine.modules[
            "naas_abi_core.modules.templatablesparqlquery"
        ]
    )
    triplestore_embeddings_module: BaseModule = ABIModule.get_instance().engine.modules[
        "naas_abi_core.modules.triplestore_embeddings"
    ]
    assert isinstance(triplestore_embeddings_module, TriplestoreEmbeddingsABIModule), (
        "TriplestoreEmbeddingsABIModule must be a subclass of BaseModule"
    )
    assert isinstance(
        templatable_sparql_query_module, TemplatableSparqlQueryABIModule
    ), "TemplatableSparqlQueryABIModuleModule must be a subclass of BaseModule"

    from rdflib import RDFS, Graph

    linkedin_queries_path = "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/ontologies/queries/ActOfConnectionsOnLinkedInQueries.ttl"
    linkedin_queries_graph = Graph()
    linkedin_queries_graph.parse(linkedin_queries_path, format="turtle")

    # Dynamically extract all labels from ActOfConnectionsOnLinkedInQueries.ttl as linkedin_tools
    linkedin_tools: list[str] = []
    for _, _, o in linkedin_queries_graph.triples((None, RDFS.label, None)):
        linkedin_tools.append(str(o))
    sparql_query_tools_list = templatable_sparql_query_module.get_instance().get_tools(
        linkedin_tools
    )
    tools += sparql_query_tools_list

    from langchain_openai import OpenAIEmbeddings
    from naas_abi_core.modules.triplestore_embeddings.workflows.CreateSearchToolWorkflow import (
        CreateSearchToolWorkflow,
        CreateSearchToolWorkflowConfiguration,
        CreateSearchToolWorkflowParameters,
    )
    from naas_abi_core.services.vector_store.VectorStoreService import (
        VectorStoreService,
    )

    vector_store_service: VectorStoreService = (
        ABIModule.get_instance().engine.services.vector_store
    )
    embeddings_model_name = (
        triplestore_embeddings_module.configuration.embeddings_model_name
    )
    embeddings_dimensions = (
        triplestore_embeddings_module.configuration.embeddings_dimensions
    )
    collection_name = triplestore_embeddings_module.configuration.collection_name
    if (
        triplestore_embeddings_module.configuration.embeddings_model_provider
        == "openai"
    ):
        embeddings_model = OpenAIEmbeddings(
            model=embeddings_model_name,
            dimensions=embeddings_dimensions,
        )
    else:
        raise ValueError(
            f"Embeddings model provider {triplestore_embeddings_module.configuration.embeddings_model_provider} not supported"
        )

    embeddings_workflow = CreateSearchToolWorkflow(
        CreateSearchToolWorkflowConfiguration(
            vector_store=vector_store_service,
            embeddings_model=embeddings_model,
        )
    )

    # Create search tools for persons
    search_person_tool = embeddings_workflow.create_search_tool(
        CreateSearchToolWorkflowParameters(
            tool_name="linkedin_search_person_uri",
            tool_description="Search for person URIs in the knowledge graph by name using semantic similarity.",
            search_param_name="person_name",
            search_param_description="Name of the person to search for",
            collection_name=collection_name,
            search_filter={"type_label": "Person"},
        )
    )
    tools.append(search_person_tool)

    # Create search tools for companies
    search_company_tool = embeddings_workflow.create_search_tool(
        CreateSearchToolWorkflowParameters(
            tool_name="linkedin_search_organization_uri",
            tool_description="Search for organization URIs in the knowledge graph by name using semantic similarity.",
            search_param_name="organization_name",
            search_param_description="Name of the organization to search for",
            collection_name=collection_name,
            search_filter={"type_label": "Organization"},
        )
    )
    tools.append(search_company_tool)

    # ---------------------------------------------------------------

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

    return LinkedInKGAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class LinkedInKGAgent(Agent):
    pass
