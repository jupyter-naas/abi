import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from rdflib import Graph, Namespace

ABI = Namespace("http://naas.ai/ontology/abi#")
INTENT_MAPPING = Namespace("http://ontology.naas.ai/intentMapping/")


@dataclass
class AgentRecommendationConfiguration(WorkflowConfiguration):
    """Configuration for Agent Recommendation Workflow.

    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
        oxigraph_url (str): URL of the Oxigraph SPARQL endpoint
        queries_file_path (str): Path to the SPARQL queries TTL file
    """

    triple_store: ITripleStoreService
    oxigraph_url: str = "http://localhost:7878"
    queries_file_path: str = "src/core/modules/abi/ontologies/application-level/AgentRecommendationSparqlQueries.ttl"


class AgentRecommendationParameters(WorkflowParameters):
    """Parameters for Agent Recommendation Workflow execution.

    Attributes:
        intent_description (str): Natural language description of what the user wants
        min_intelligence_score (int): Minimum intelligence index (0-100)
        max_input_cost (float): Maximum input cost per million tokens
        max_results (int): Maximum number of recommendations to return
        provider_preference (str): Optional preferred provider name
    """

    intent_description: str
    min_intelligence_score: Optional[int] = 10
    max_input_cost: Optional[float] = None
    max_results: Optional[int] = 10
    provider_preference: Optional[str] = None


class AgentRecommendationWorkflow(Workflow):
    __configuration: AgentRecommendationConfiguration

    def __init__(self, configuration: AgentRecommendationConfiguration):
        self.__configuration = configuration
        self._load_queries()

    def _load_queries(self) -> None:
        """Load SPARQL queries from the TTL file."""
        self._queries = {}

        # Load the TTL file and parse query templates
        queries_file = Path(self.__configuration.queries_file_path)
        if not queries_file.exists():
            raise FileNotFoundError(f"Queries file not found: {queries_file}")

        # Parse the RDF graph to extract query templates
        graph = Graph()
        graph.parse(queries_file, format="turtle")

        # Extract templatable SPARQL queries
        for subject in graph.subjects(predicate=INTENT_MAPPING.intentDescription):
            query_id = str(subject).split("/")[-1].replace("Query", "")
            intent_desc = str(graph.value(subject, INTENT_MAPPING.intentDescription))
            sparql_template = str(graph.value(subject, INTENT_MAPPING.sparqlTemplate))

            self._queries[query_id] = {
                "intent_description": intent_desc,
                "sparql_template": sparql_template,
            }

    def run_workflow(self, parameters: WorkflowParameters) -> Dict[str, Any]:
        if not isinstance(parameters, AgentRecommendationParameters):
            raise ValueError("Parameters must be of type AgentRecommendationParameters")

        print(
            f"🔍 [AgentRecommendation] Processing intent: '{parameters.intent_description}'"
        )

        # Step 1: Match intent to appropriate query
        selected_query = self._match_intent_to_query(parameters.intent_description)
        print(
            f"📋 [AgentRecommendation] Matched query: {selected_query['intent_description']}"
        )

        # Step 2: Template the SPARQL query with parameters
        templated_query = self._template_query(selected_query, parameters)
        print("🔧 [AgentRecommendation] Templated SPARQL query:")
        print(templated_query)

        # Step 3: Execute the query against Oxigraph
        print("⚡ [AgentRecommendation] Executing SPARQL query against Oxigraph...")
        results = self._execute_sparql_query(templated_query)
        print(f"📊 [AgentRecommendation] Query returned {len(results)} raw results")

        # Step 4: Format recommendations for user
        recommendations = self._format_recommendations(results, parameters)
        print(
            f"✅ [AgentRecommendation] Formatted {len(recommendations)} recommendations"
        )

        return {
            "intent": parameters.intent_description,
            "query_used": selected_query["intent_description"],
            "recommendations": recommendations,
            "total_found": len(recommendations),
        }

    def _match_intent_to_query(self, intent_description: str) -> Dict[str, str]:
        """Match user intent to the most appropriate SPARQL query."""
        intent_lower = intent_description.lower()

        # Intent matching logic
        if any(
            word in intent_lower
            for word in ["business", "proposal", "professional", "document"]
        ):
            return self._queries["abi#findBusinessProposalAgents"]
        elif any(
            word in intent_lower
            for word in ["code", "programming", "development", "script"]
        ):
            return self._queries["abi#findCodingAgents"]
        elif any(
            word in intent_lower
            for word in ["math", "calculation", "equation", "statistics"]
        ):
            return self._queries["abi#findMathAgents"]
        elif any(word in intent_lower for word in ["fast", "quick", "speed", "rapid"]):
            return self._queries["abi#findFastestAgents"]
        elif any(word in intent_lower for word in ["cheap", "cost", "value", "budget"]):
            return self._queries["abi#findBestValueAgents"]
        else:
            # Default to business proposal for general requests
            return self._queries["abi#findBusinessProposalAgents"]

    def _template_query(
        self, query_info: Dict[str, str], parameters: AgentRecommendationParameters
    ) -> str:
        """Template the SPARQL query with user parameters."""
        template = query_info["sparql_template"]

        # Replace template variables
        replacements: Dict[str, Any] = {
            "min_intelligence_score": parameters.min_intelligence_score or 10,
            "max_results": parameters.max_results or 10,
            "min_coding_score": parameters.min_intelligence_score
            or 10,  # Use intelligence as fallback
            "min_math_score": parameters.min_intelligence_score
            or 10,  # Use intelligence as fallback
        }

        # Add optional parameters
        if parameters.max_input_cost:
            replacements["max_input_cost"] = parameters.max_input_cost

        if parameters.provider_preference:
            replacements["provider_name"] = parameters.provider_preference

        # Simple template replacement (for now - could use Jinja2 for more complex templating)
        for key, value in replacements.items():
            template = template.replace("{{ " + key + " }}", str(value))

        # Handle conditional blocks (basic implementation)
        template = self._handle_conditional_blocks(template, replacements)

        return template

    def _handle_conditional_blocks(
        self, template: str, replacements: Dict[str, Any]
    ) -> str:
        """Handle {% if %} conditional blocks in templates."""
        # Simple regex to find and process {% if variable %} blocks

        # Pattern to match {% if variable %} ... {% endif %}
        pattern = r"\{\%\s*if\s+(\w+)\s*\%\}(.*?)\{\%\s*endif\s*\%\}"

        def replace_conditional(match):
            variable = match.group(1)
            content = match.group(2)

            # Check if variable exists and has a truthy value in replacements
            if variable in replacements and replacements[variable]:
                return content
            else:
                return ""

        return re.sub(pattern, replace_conditional, template, flags=re.DOTALL)

    def _execute_sparql_query(self, sparql_query: str) -> List[Dict[str, Any]]:
        """Execute SPARQL query against Oxigraph."""
        try:
            response = requests.post(
                f"{self.__configuration.oxigraph_url}/query",
                headers={"Content-Type": "application/sparql-query"},
                data=sparql_query,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("results", {}).get("bindings", [])

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to execute SPARQL query: {e}")

    def _format_recommendations(
        self, results: List[Dict[str, Any]], parameters: AgentRecommendationParameters
    ) -> List[Dict[str, Any]]:
        """Format query results into user-friendly recommendations."""
        recommendations = []

        for result in results:
            recommendation = {
                "agent": self._extract_value(result, "agentLabel")
                or self._extract_value(result, "agent"),
                "model": self._extract_value(result, "model"),
                "provider": self._extract_value(result, "provider"),
                "costs": {
                    "input_per_million_tokens": float(
                        self._extract_value(result, "inputCost") or 0
                    ),
                    "output_per_million_tokens": float(
                        self._extract_value(result, "outputCost") or 0
                    ),
                    "currency": "USD",
                },
                "performance": {
                    "intelligence_index": float(
                        self._extract_value(result, "intelligenceIndex") or 0
                    ),
                    "coding_index": float(
                        self._extract_value(result, "codingIndex") or 0
                    ),
                    "math_index": float(self._extract_value(result, "mathIndex") or 0),
                    "output_speed": float(
                        self._extract_value(result, "outputSpeed") or 0
                    ),
                },
                "recommendation_reason": self._generate_recommendation_reason(
                    result, parameters.intent_description
                ),
            }

            recommendations.append(recommendation)

        return recommendations

    def _extract_value(self, result: Dict[str, Any], key: str) -> Optional[str]:
        """Extract value from SPARQL result binding."""
        if key in result and "value" in result[key]:
            return result[key]["value"]
        return None

    def _generate_recommendation_reason(
        self, result: Dict[str, Any], intent: str
    ) -> str:
        """Generate a human-readable reason for the recommendation."""
        intelligence = float(self._extract_value(result, "intelligenceIndex") or 0)
        coding = float(self._extract_value(result, "codingIndex") or 0)
        math = float(self._extract_value(result, "mathIndex") or 0)
        input_cost = float(self._extract_value(result, "inputCost") or 0)

        reasons = []

        if intelligence >= 80:
            reasons.append("high intelligence score")
        if coding >= 80:
            reasons.append("excellent coding capabilities")
        if math >= 80:
            reasons.append("strong mathematical reasoning")
        if input_cost <= 1.0:
            reasons.append("cost-effective pricing")

        if not reasons:
            reasons.append("good overall performance")

        return f"Recommended for {intent.lower()} due to {', '.join(reasons)}"

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow.

        Returns:
            list[BaseTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="recommend_ai_agents",
                description="Recommend AI agents based on user intent and requirements. Analyzes capabilities, performance, and costs to suggest the best agents for specific tasks like business proposals, coding, math, etc.",
                func=lambda **kwargs: self.run_workflow(
                    AgentRecommendationParameters(**kwargs)
                ),
                args_schema=AgentRecommendationParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None

    def get_configuration(self) -> AgentRecommendationConfiguration:
        """Get the workflow configuration."""
        return self.__configuration
