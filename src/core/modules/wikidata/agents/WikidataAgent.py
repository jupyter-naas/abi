from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from src import secret
from fastapi import APIRouter
from src.core.modules.wikidata.integrations.WikidataIntegration import (
    WikidataIntegration,
    WikidataIntegrationConfiguration,
)
from src.core.modules.wikidata.workflows.NaturalLanguageToSparqlWorkflow import (
    NaturalLanguageToSparqlWorkflow,
    NaturalLanguageToSparqlWorkflowConfiguration,
)
from src.core.modules.wikidata.pipelines.WikidataQueryPipeline import (
    WikidataQueryPipeline,
    WikidataQueryPipelineConfiguration,
)
from typing import Optional
from enum import Enum
from pydantic import SecretStr

NAME = "Wikidata"
MODEL = "gpt-4o"
TEMPERATURE = 0.3
DESCRIPTION = "Query Wikidata knowledge base using natural language. Convert natural language questions into SPARQL queries and execute them against Wikidata."
AVATAR_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/f/ff/Wikidata-logo.svg/1200px-Wikidata-logo.svg.png"
SYSTEM_PROMPT = """
You are a Wikidata Agent specialized in querying the Wikidata knowledge base using natural language.

Your capabilities include:
1. Converting natural language questions into SPARQL queries
2. Executing SPARQL queries against the Wikidata query service (https://query.wikidata.org/)
3. Interpreting and presenting results in a user-friendly format
4. Providing insights about entities, relationships, and properties from Wikidata

When users ask questions, you should:
- Understand the intent and identify relevant Wikidata entities and properties
- Generate appropriate SPARQL queries to retrieve the requested information
- Execute the queries against Wikidata
- Format and present the results clearly
- Provide additional context or explanations when helpful

You have access to tools for:
- Natural language to SPARQL conversion
- SPARQL query execution against Wikidata
- Result formatting and presentation

Always be clear about what you're querying and explain your approach when converting natural language to SPARQL.
"""
SUGGESTIONS = [
    {
        "label": "Who are the Nobel Prize winners in Physics?",
        "value": "Who are the Nobel Prize winners in Physics?",
    },
    {
        "label": "What are the capitals of European countries?",
        "value": "What are the capitals of European countries?",
    },
    {
        "label": "List all movies directed by Christopher Nolan",
        "value": "List all movies directed by Christopher Nolan",
    },
    {
        "label": "What programming languages were created by Google?",
        "value": "What programming languages were created by Google?",
    },
]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Init
    tools: list = []
    agents: list = []

    # Set model
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Initialize Wikidata integration
    wikidata_integration_config = WikidataIntegrationConfiguration()
    wikidata_integration = WikidataIntegration(wikidata_integration_config)

    # Initialize workflows and pipelines
    # Natural Language to SPARQL conversion workflow
    nl_to_sparql_config = NaturalLanguageToSparqlWorkflowConfiguration(
        wikidata_integration=wikidata_integration
    )
    nl_to_sparql_workflow = NaturalLanguageToSparqlWorkflow(nl_to_sparql_config)
    tools += nl_to_sparql_workflow.as_tools()

    # SPARQL query execution pipeline
    query_pipeline_config = WikidataQueryPipelineConfiguration(
        wikidata_integration=wikidata_integration
    )
    query_pipeline = WikidataQueryPipeline(query_pipeline_config)
    tools += query_pipeline.as_tools()

    return WikidataAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class WikidataAgent(Agent):
    def as_api(
        self,
        router: APIRouter,
        route_name: str = NAME,
        name: str = NAME.capitalize().replace("_", " "),
        description: str = "API endpoints to call the Wikidata agent completion.",
        description_stream: str = "API endpoints to call the Wikidata agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        ) 