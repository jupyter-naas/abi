from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
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
) -> IntentAgent:
    # Initialize module
    from naas_abi_core.module.Module import BaseModule
    from naas_abi_core.modules.templatablesparqlquery import (
        ABIModule as TemplatableSparqlQueryABIModule,
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
    assert isinstance(
        templatable_sparql_query_module, TemplatableSparqlQueryABIModule
    ), "TemplatableSparqlQueryABIModuleModule must be a subclass of BaseModule"

    linkedin_tools = [
        "linkedin_count_connections_by_person",
        "linkedin_search_connections_by_person",
        "linkedin_search_connections_by_organization",
        "linkedin_search_connections_by_job_position",
        "linkedin_search_person_info",
    ]
    sparql_query_tools_list = TemplatableSparqlQueryABIModule.get_instance().get_tools(
        linkedin_tools
    )
    tools += sparql_query_tools_list

    # Set intents
    intents: list = [
        Intent(
            intent_value="Who is connected with {person}?",
            intent_type=IntentType.TOOL,
            intent_target="linkedin_search_connections_by_person_name",
        ),
        Intent(
            intent_value="How many connections does {person} have?",
            intent_type=IntentType.TOOL,
            intent_target="linkedin_count_connections_by_person",
        ),
        Intent(
            intent_value="What do you know about {person}?",
            intent_type=IntentType.TOOL,
            intent_target="linkedin_get_connection_information",
        ),
        Intent(
            intent_value="What is {person}'s email address?",
            intent_type=IntentType.TOOL,
            intent_target="linkedin_search_email_address_by_person_uri",
        ),
    ]

    from typing import Any, Dict, List

    import numpy as np
    from langchain_core.tools import StructuredTool
    from naas_abi_core.services.agent.beta.Embeddings import embeddings
    from naas_abi_core.services.vector_store.VectorStoreService import (
        VectorStoreService,
    )
    from pydantic import BaseModel, Field

    vector_store_service: VectorStoreService = (
        ABIModule.get_instance().engine.services.vector_store
    )

    def create_search_tool(
        collection_name: str,
        search_param_name: str,
        tool_name: str,
        tool_description: str,
        entity_type_label: str,
    ) -> StructuredTool:
        """Create a search tool for entities in a collection.

        Args:
            collection_name: Name of the vector store collection
            search_param_name: Name of the search parameter (e.g., "person_name", "company_name")
            tool_name: Name of the search tool to create
            tool_description: Description of the search tool
            entity_type_label: Label for the entity type for logging

        Returns:
            A StructuredTool for searching entities by name
        """

        # Create search schema dynamically
        class SearchSchema(BaseModel):
            __annotations__ = {
                search_param_name: str,
                "k": int,
            }
            # Annotate the search_param_name field
            locals()[search_param_name] = Field(
                description=f"The name of the {entity_type_label} to search for"
            )
            # Annotate the "k" field with bounds and default.
            k: int = Field(
                default=10,
                ge=1,
                le=20,
                description="Number of results to return (default: 10)",
            )

        # Create search function that accepts the dynamic parameter name
        def search_entity(**kwargs) -> List[Dict[str, Any]]:
            """Search for entity URIs by name using vector similarity search.

            Args:
                **kwargs: Must contain the search_param_name and optionally 'k'

            Returns:
                List of dictionaries containing entity URI, label, and similarity score
            """
            try:
                # Extract the name parameter using the search_param_name
                name = kwargs.get(search_param_name, "")
                k = kwargs.get("k", 10)

                if not name:
                    return [{"error": f"{search_param_name} is required"}]

                # Generate embedding for the query
                query_embedding = embeddings(name)
                query_vector = np.array(query_embedding)

                # Search in vector store
                search_results = vector_store_service.search_similar(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    k=k,
                    include_metadata=True,
                )

                # Format results
                results = []
                for result in search_results:
                    if result.metadata:
                        results.append(
                            {
                                "uri": result.metadata.get("uri", ""),
                                "label": result.metadata.get("label", ""),
                                "score": float(result.score),
                            }
                        )

                return results
            except Exception as e:
                return [{"error": str(e)}]

        # Create and return the search tool
        search_tool = StructuredTool(
            name=tool_name,
            description=tool_description,
            func=search_entity,
            args_schema=SearchSchema,
        )

        return search_tool

    # Create search tools for persons
    persons_collection_name = "linkedin_persons"
    search_person_tool = create_search_tool(
        collection_name=persons_collection_name,
        tool_name="linkedin_search_person_uri",
        tool_description="Search for person URIs (entities of type cco:ont00001262) in the knowledge graph by name using semantic similarity. Use this tool when you need to find the URI of a person by their name.",
        search_param_name="person_name",
        entity_type_label="person",
    )
    tools.append(search_person_tool)

    # Create search tools for companies
    companies_collection_name = "linkedin_companies"
    search_company_tool = create_search_tool(
        collection_name=companies_collection_name,
        tool_name="linkedin_search_company_uri",
        tool_description="Search for company URIs (entities of type cco:ont00001180) in the knowledge graph by name using semantic similarity. Use this tool to find a company URI by its name.",
        search_param_name="company_name",
        entity_type_label="company",
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
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class LinkedInKGAgent(IntentAgent):
    pass
