from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from abi import logger
from pydantic import Field
from typing import Annotated, Optional, Dict, Any, List
from fastapi import APIRouter
from enum import Enum
from src.core.modules.wikidata.integrations.WikidataIntegration import WikidataIntegration


@dataclass
class WikidataQueryPipelineConfiguration(PipelineConfiguration):
    """Configuration for WikidataQueryPipeline.

    Attributes:
        wikidata_integration (WikidataIntegration): The Wikidata integration service to use
    """

    wikidata_integration: WikidataIntegration


class WikidataQueryPipelineParameters(PipelineParameters):
    sparql_query: Annotated[str, Field(
        description="SPARQL query to execute against Wikidata",
        example="""SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q5 .
  ?item wdt:P106 wd:Q82955 .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} LIMIT 10"""
    )]
    format: Optional[Annotated[str, Field(
        default="json",
        description="Response format (json, xml, csv, tsv)",
    )]] = "json"
    include_metadata: Optional[Annotated[bool, Field(
        default=True,
        description="Whether to include query metadata in the response",
    )]] = True
    enhance_results: Optional[Annotated[bool, Field(
        default=True,
        description="Whether to enhance results with additional entity information",
    )]] = True


class WikidataQueryPipeline(Pipeline):
    """Pipeline for executing SPARQL queries against Wikidata."""

    __configuration: WikidataQueryPipelineConfiguration

    def __init__(self, configuration: WikidataQueryPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: WikidataQueryPipelineParameters) -> Dict[str, Any]:  # type: ignore[override]
        """Execute SPARQL query against Wikidata and return formatted results.

        Args:
            parameters: Pipeline parameters containing the SPARQL query and options

        Returns:
            Dict containing query results, metadata, and enhanced information
        """
        try:
            logger.info("Executing SPARQL query against Wikidata")
            logger.debug(f"Query: {parameters.sparql_query}")

            # Validate the SPARQL query
            is_valid = self.__configuration.wikidata_integration.validate_sparql_query(parameters.sparql_query)
            if not is_valid:
                logger.warning("SPARQL query validation failed, but proceeding with execution")

            # Execute the SPARQL query
            raw_results = self.__configuration.wikidata_integration.execute_sparql_query(
                parameters.sparql_query,
                format=parameters.format
            )

            # Format the results
            if parameters.format == "json":
                formatted_results = self.__configuration.wikidata_integration.format_query_results(raw_results)
            else:
                formatted_results = raw_results

            # Enhance results with additional information if requested
            enhanced_results = formatted_results
            if parameters.enhance_results and parameters.format == "json":
                enhanced_results = self._enhance_results(formatted_results)

            # Build response
            response = {
                "results": enhanced_results,
                "raw_results": raw_results if parameters.include_metadata else None,
                "query": parameters.sparql_query,
                "format": parameters.format,
                "result_count": self._get_result_count(raw_results, parameters.format),
                "execution_time": None,  # Could be enhanced to track execution time
                "is_valid_query": is_valid,
            }

            if parameters.include_metadata:
                response["metadata"] = self._extract_metadata(raw_results, parameters.format)

            logger.info(f"Successfully executed SPARQL query, returned {response['result_count']} results")
            return response

        except Exception as e:
            logger.error(f"Error executing SPARQL query: {str(e)}")
            return {
                "error": str(e),
                "results": [],
                "query": parameters.sparql_query,
                "format": parameters.format,
                "result_count": 0,
                "is_valid_query": False,
            }

    def _enhance_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance query results with additional entity information.

        Args:
            results: Formatted query results

        Returns:
            Enhanced results with additional entity information
        """
        enhanced_results = []
        
        for result in results:
            enhanced_result = result.copy()
            
            # Look for Wikidata entities in the results
            for key, value in result.items():
                if isinstance(value, dict) and value.get("type") == "uri":
                    entity_id = value.get("entity_id")
                    if entity_id and entity_id.startswith("Q"):
                        # Get additional entity information
                        try:
                            entity_info = self.__configuration.wikidata_integration.get_entity_info(entity_id)
                            if entity_info:
                                enhanced_result[f"{key}_info"] = {
                                    "entity_id": entity_id,
                                    "description": entity_info.get("descriptions", {}).get("en", {}).get("value", ""),
                                    "aliases": [alias.get("value", "") for alias in entity_info.get("aliases", {}).get("en", [])],
                                    "sitelinks_count": len(entity_info.get("sitelinks", {})),
                                }
                        except Exception as e:
                            logger.debug(f"Could not enhance entity {entity_id}: {str(e)}")
                            
            enhanced_results.append(enhanced_result)
            
        return enhanced_results

    def _get_result_count(self, raw_results: Dict[str, Any], format: str) -> int:
        """Get the number of results from the raw query response.

        Args:
            raw_results: Raw query results
            format: Response format

        Returns:
            Number of results
        """
        if format == "json" and "results" in raw_results and "bindings" in raw_results["results"]:
            return len(raw_results["results"]["bindings"])
        return 0

    def _extract_metadata(self, raw_results: Dict[str, Any], format: str) -> Dict[str, Any]:
        """Extract metadata from query results.

        Args:
            raw_results: Raw query results
            format: Response format

        Returns:
            Metadata dictionary
        """
        metadata = {
            "format": format,
            "endpoint": "https://query.wikidata.org/sparql",  # Default endpoint
        }

        if format == "json" and "head" in raw_results:
            metadata["variables"] = raw_results["head"].get("vars", [])
            
        return metadata

    def as_tools(self) -> list[BaseTool]:
        """Convert pipeline to LangChain tools."""
        
        def pipeline_tool(sparql_query: str, format: str = "json", include_metadata: bool = True, enhance_results: bool = True):
            """Execute SPARQL query against Wikidata."""
            params = WikidataQueryPipelineParameters(
                sparql_query=sparql_query,
                format=format,
                include_metadata=include_metadata,
                enhance_results=enhance_results
            )
            return self.run(params)
            
        return [
            StructuredTool(
                name="execute_wikidata_sparql_query",
                description="Execute a SPARQL query against the Wikidata knowledge base",
                func=pipeline_tool,
                args_schema=WikidataQueryPipelineParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "wikidata_query",
        name: str = "Wikidata SPARQL Query",
        description: str = "Execute SPARQL queries against Wikidata",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        """Add API routes for the pipeline."""
        if tags is None:
            tags = ["wikidata", "sparql", "query"]

        @router.post(
            f"/{route_name}",
            name=name,
            description=description,
            tags=tags,
        )
        def execute_wikidata_query(parameters: WikidataQueryPipelineParameters):
            return self.run(parameters) 