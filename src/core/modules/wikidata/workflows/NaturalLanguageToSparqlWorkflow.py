from abi.workflow import Workflow, WorkflowConfiguration
from dataclasses import dataclass
from pydantic import Field
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from typing import Annotated, Optional, Dict, Any
from enum import Enum
from abi import logger
from src.core.modules.wikidata.integrations.WikidataIntegration import WikidataIntegration
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from src import secret
from pydantic import SecretStr


@dataclass
class NaturalLanguageToSparqlWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for NaturalLanguageToSparqlWorkflow."""
    wikidata_integration: WikidataIntegration


class NaturalLanguageToSparqlWorkflowParameters(WorkflowParameters):
    """Parameters for NaturalLanguageToSparqlWorkflow."""
    question: Annotated[str, Field(
        ...,
        description="Natural language question to convert to SPARQL query",
        example="Who are the Nobel Prize winners in Physics?",
    )]
    include_explanations: Optional[Annotated[bool, Field(
        default=True,
        description="Whether to include explanations of the SPARQL query generation process",
    )]] = True
    limit: Optional[Annotated[int, Field(
        default=10,
        description="Maximum number of results to return in the query",
        ge=1,
        le=1000,
    )]] = 10


class NaturalLanguageToSparqlWorkflow(Workflow):
    """Workflow for converting natural language questions to SPARQL queries."""

    __configuration: NaturalLanguageToSparqlWorkflowConfiguration

    def __init__(self, configuration: NaturalLanguageToSparqlWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: NaturalLanguageToSparqlWorkflowParameters) -> Dict[str, Any]:  # type: ignore[override]
        """Convert natural language question to SPARQL query.

        Args:
            parameters: Workflow parameters containing the question and options

        Returns:
            Dict containing the SPARQL query, explanation, and metadata
        """
        try:
            logger.info(f"Converting natural language question to SPARQL: {parameters.question}")

            # Initialize the language model
            model = ChatOpenAI(
                model="gpt-4o",
                temperature=0.1,
                api_key=SecretStr(secret.get("OPENAI_API_KEY"))
            )

            # Create the system prompt for SPARQL generation
            system_prompt = self._build_system_prompt()
            
            # Create the user prompt with the specific question
            user_prompt = self._build_user_prompt(parameters.question, parameters.limit)

            # Generate SPARQL query using the language model
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = model.invoke(messages)
            response_content = response.content

            # Parse the response to extract SPARQL query and explanation
            sparql_query, explanation = self._parse_model_response(response_content)

            # Validate the generated SPARQL query
            is_valid = self.__configuration.wikidata_integration.validate_sparql_query(sparql_query)

            # Build prefixed query
            if is_valid:
                prefixed_query = self.__configuration.wikidata_integration.build_prefixed_query(sparql_query)
            else:
                prefixed_query = sparql_query

            result = {
                "sparql_query": prefixed_query,
                "raw_query": sparql_query,
                "explanation": explanation if parameters.include_explanations else None,
                "is_valid": is_valid,
                "original_question": parameters.question,
                "limit": parameters.limit,
            }

            logger.info(f"Successfully generated SPARQL query for question: {parameters.question}")
            return result

        except Exception as e:
            logger.error(f"Error converting natural language to SPARQL: {str(e)}")
            return {
                "error": str(e),
                "sparql_query": None,
                "explanation": None,
                "is_valid": False,
                "original_question": parameters.question,
            }

    def _build_system_prompt(self) -> str:
        """Build the system prompt for SPARQL generation."""
        return """You are an expert in converting natural language questions to SPARQL queries for Wikidata.

Your task is to convert natural language questions into valid SPARQL queries that can be executed against the Wikidata knowledge base.

Key guidelines:
1. Use common Wikidata prefixes (wd:, wdt:, rdfs:, etc.) - don't include PREFIX declarations in your response
2. Focus on the main SELECT clause and WHERE patterns
3. Use appropriate Wikidata properties and entities
4. Include LIMIT clause when specified
5. Use rdfs:label to get human-readable names
6. Add OPTIONAL clauses for additional information when relevant
7. Use proper SPARQL syntax and best practices

Common Wikidata patterns:
- wd:Q... for entities (e.g., wd:Q5 for human)
- wdt:P... for properties (e.g., wdt:P31 for "instance of")
- rdfs:label for getting labels
- SERVICE wikibase:label { bd:serviceParam wikibase:language "en" } for automatic labeling

Format your response as:
SPARQL_QUERY:
[The SPARQL query without PREFIX declarations]

EXPLANATION:
[Brief explanation of the query logic and key properties used]

Example entities and properties:
- Q5: human
- Q6256: country  
- Q515: city
- P31: instance of
- P17: country
- P106: occupation
- P569: date of birth
- P570: date of death
- P166: award received
"""

    def _build_user_prompt(self, question: str, limit: int) -> str:
        """Build the user prompt with the specific question."""
        return f"""Convert this natural language question to a SPARQL query for Wikidata:

Question: {question}

Please include a LIMIT {limit} clause in your query.

Remember:
- Don't include PREFIX declarations
- Use proper Wikidata entity and property notation
- Include rdfs:label for readable results
- Make the query efficient and accurate"""

    def _parse_model_response(self, response: str) -> tuple[str, str]:
        """Parse the model response to extract SPARQL query and explanation."""
        try:
            # Split response into sections
            sections = response.split("EXPLANATION:")
            
            if len(sections) == 2:
                sparql_section = sections[0]
                explanation = sections[1].strip()
            else:
                sparql_section = response
                explanation = "No explanation provided"

            # Extract SPARQL query
            if "SPARQL_QUERY:" in sparql_section:
                sparql_query = sparql_section.split("SPARQL_QUERY:")[1].strip()
            else:
                # Fallback: try to find query between code blocks
                if "```sparql" in response:
                    sparql_query = response.split("```sparql")[1].split("```")[0].strip()
                elif "```" in response:
                    sparql_query = response.split("```")[1].strip()
                else:
                    sparql_query = sparql_section.strip()

            return sparql_query, explanation

        except Exception as e:
            logger.error(f"Error parsing model response: {str(e)}")
            return response, "Error parsing explanation"

    def as_tools(self) -> list[BaseTool]:
        """Convert workflow to LangChain tools."""
        
        def workflow_tool(question: str, include_explanations: bool = True, limit: int = 10):
            """Convert natural language question to SPARQL query."""
            params = NaturalLanguageToSparqlWorkflowParameters(
                question=question,
                include_explanations=include_explanations,
                limit=limit
            )
            return self.run(params)
        
        return [
            StructuredTool(
                name="convert_natural_language_to_sparql",
                description="Convert a natural language question to a SPARQL query for Wikidata",
                func=workflow_tool,
                args_schema=NaturalLanguageToSparqlWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "natural_language_to_sparql",
        name: str = "Natural Language to SPARQL",
        description: str = "Convert natural language questions to SPARQL queries",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        """Add API routes for the workflow."""
        if tags is None:
            tags = ["wikidata", "sparql", "nlp"]

        @router.post(
            f"/{route_name}",
            name=name,
            description=description,
            tags=tags,
        )
        def convert_nl_to_sparql(parameters: NaturalLanguageToSparqlWorkflowParameters):
            return self.run(parameters) 