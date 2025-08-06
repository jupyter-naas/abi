from typing import Dict, List, Any
from abi.integration.integration import (
    Integration,
    IntegrationConnectionError,
    IntegrationConfiguration,
)
from dataclasses import dataclass
import requests
import json
from abi import logger


@dataclass
class WikidataIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Wikidata integration.

    Attributes:
        sparql_endpoint (str): SPARQL endpoint URL for Wikidata
        user_agent (str): User agent string for requests
        timeout (int): Request timeout in seconds
    """

    sparql_endpoint: str = "https://query.wikidata.org/sparql"
    user_agent: str = "ABI-WikidataAgent/1.0 (https://naas.ai/abi) Python/requests"
    timeout: int = 30


class WikidataIntegration(Integration):
    """Wikidata integration class for interacting with Wikidata SPARQL endpoint.

    This class provides methods to interact with Wikidata's SPARQL endpoint.
    It handles query execution, rate limiting, and response formatting.

    Attributes:
        __configuration (WikidataIntegrationConfiguration): Configuration instance
            containing necessary settings for Wikidata API access.
    """

    __configuration: WikidataIntegrationConfiguration

    def __init__(self, configuration: WikidataIntegrationConfiguration):
        """Initialize Wikidata client with configuration."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.headers = {
            "User-Agent": self.__configuration.user_agent,
            "Accept": "application/sparql-results+json",
        }

    def execute_sparql_query(self, query: str, format: str = "json") -> Dict[str, Any]:
        """Execute a SPARQL query against Wikidata.

        Args:
            query (str): The SPARQL query to execute
            format (str): Response format ('json', 'xml', 'csv', 'tsv')

        Returns:
            Dict[str, Any]: Query results in the specified format

        Raises:
            IntegrationConnectionError: If the query fails
        """
        params = {
            "query": query,
            "format": format,
        }

        try:
            logger.info(f"Executing SPARQL query: {query[:100]}...")
            
            response = requests.get(
                self.__configuration.sparql_endpoint,
                params=params,
                headers=self.headers,
                timeout=self.__configuration.timeout,
            )
            
            response.raise_for_status()
            
            if format == "json":
                return response.json()
            else:
                return {"raw_response": response.text}
                
        except requests.exceptions.Timeout:
            raise IntegrationConnectionError("Wikidata query timed out")
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Wikidata query failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise IntegrationConnectionError(f"Failed to parse Wikidata response: {str(e)}")

    def search_entities(self, search_term: str, language: str = "en", limit: int = 10) -> List[Dict[str, Any]]:
        """Search for entities using Wikidata's search API.

        Args:
            search_term (str): Term to search for
            language (str): Language code for search
            limit (int): Maximum number of results

        Returns:
            List[Dict[str, Any]]: List of matching entities
        """
        search_url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": search_term,
            "language": language,
            "limit": limit,
            "format": "json",
        }

        try:
            response = requests.get(
                search_url,
                params=params,
                headers={"User-Agent": self.__configuration.user_agent},
                timeout=self.__configuration.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("search", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Entity search failed: {str(e)}")
            return []

    def get_entity_info(self, entity_id: str, language: str = "en") -> Dict[str, Any]:
        """Get detailed information about a Wikidata entity.

        Args:
            entity_id (str): Wikidata entity ID (e.g., 'Q42')
            language (str): Language code for labels/descriptions

        Returns:
            Dict[str, Any]: Entity information
        """
        api_url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "languages": language,
            "format": "json",
        }

        try:
            response = requests.get(
                api_url,
                params=params,
                headers={"User-Agent": self.__configuration.user_agent},
                timeout=self.__configuration.timeout,
            )
            response.raise_for_status()
            data = response.json()
            entities = data.get("entities", {})
            return entities.get(entity_id, {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Entity info retrieval failed: {str(e)}")
            return {}

    def format_query_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format SPARQL query results into a more readable format.

        Args:
            results (Dict[str, Any]): Raw SPARQL results

        Returns:
            List[Dict[str, Any]]: Formatted results
        """
        if "results" not in results or "bindings" not in results["results"]:
            return []

        formatted_results = []
        for binding in results["results"]["bindings"]:
            row = {}
            for var, value in binding.items():
                if value["type"] == "uri":
                    # Extract entity ID from URI for Wikidata entities
                    if "wikidata.org/entity/" in value["value"]:
                        entity_id = value["value"].split("/")[-1]
                        row[var] = {
                            "value": value["value"],
                            "entity_id": entity_id,
                            "type": "uri"
                        }
                    else:
                        row[var] = {
                            "value": value["value"],
                            "type": "uri"
                        }
                elif value["type"] == "literal":
                    row[var] = {
                        "value": value["value"],
                        "type": "literal",
                        "datatype": value.get("datatype"),
                        "xml:lang": value.get("xml:lang")
                    }
                else:
                    row[var] = {
                        "value": value["value"],
                        "type": value["type"]
                    }
            formatted_results.append(row)

        return formatted_results

    def validate_sparql_query(self, query: str) -> bool:
        """Validate SPARQL query syntax.

        Args:
            query (str): SPARQL query to validate

        Returns:
            bool: True if query is valid, False otherwise
        """
        # Basic validation - check for required keywords
        query_upper = query.upper()
        
        # Must contain SELECT, ASK, CONSTRUCT, or DESCRIBE
        if not any(keyword in query_upper for keyword in ["SELECT", "ASK", "CONSTRUCT", "DESCRIBE"]):
            return False
            
        # Must contain WHERE clause for most queries
        if "SELECT" in query_upper and "WHERE" not in query_upper:
            return False
            
        return True

    def get_common_prefixes(self) -> Dict[str, str]:
        """Get common prefixes used in Wikidata SPARQL queries.

        Returns:
            Dict[str, str]: Dictionary of prefix names and their URIs
        """
        return {
            "wd": "http://www.wikidata.org/entity/",
            "wdt": "http://www.wikidata.org/prop/direct/",
            "wikibase": "http://wikiba.se/ontology#",
            "p": "http://www.wikidata.org/prop/",
            "ps": "http://www.wikidata.org/prop/statement/",
            "pq": "http://www.wikidata.org/prop/qualifier/",
            "pr": "http://www.wikidata.org/prop/reference/",
            "prv": "http://www.wikidata.org/prop/reference/value/",
            "psv": "http://www.wikidata.org/prop/statement/value/",
            "pqv": "http://www.wikidata.org/prop/qualifier/value/",
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "bd": "http://www.bigdata.com/rdf#",
            "hint": "http://www.bigdata.com/queryHints#",
        }

    def build_prefixed_query(self, query_body: str) -> str:
        """Build a complete SPARQL query with common prefixes.

        Args:
            query_body (str): The main query body without prefixes

        Returns:
            str: Complete SPARQL query with prefixes
        """
        prefixes = self.get_common_prefixes()
        prefix_lines = [f"PREFIX {name}: <{uri}>" for name, uri in prefixes.items()]
        
        return "\n".join(prefix_lines) + "\n\n" + query_body 