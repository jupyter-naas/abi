from enum import Enum
from fastapi import APIRouter
from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters, Graph
from src.marketplace.applications.pubmed.integrations.PubMedAPI import (
    PubMedIntegration,
    PubMedAPIConfiguration,
    PubMedPaperSummary,
)
from typing import List, Optional, Literal
from pydantic import Field
from abi import logger
from langchain_core.tools import BaseTool, StructuredTool

class PubMedPipelineConfiguration(PipelineConfiguration):
    pass

# class PubMedPipelineParameters(PipelineParameters):
#     """
#     Parameters for running the PubMedPipeline.

#     Attributes:
#         query (str): The query to search for in PubMed.
#         start_date (str): The start date to search for in PubMed.
#         end_date (Optional[str]): The end date to search for in PubMed. If not provided, searches up to the present.
#         downloadable_only (bool): Whether to only return papers that are downloadable from PubMedCentral.
#         max_results (int): The maximum number of results to return.
#     """
#     query: Annotated[str, Field(
#         description="The query to search for in PubMed"
#     )]
#     start_date: Annotated[str, Field(
#         description="The start date to search for in PubMed"
#     )]
#     end_date: Optional[str] = Field(
#         description="The end date to search for in PubMed",
#         default=None
#     )
#     sort: Annotated[str, Field(
#         description=(
#             "The sort method to use. Accepted values: "
#             "'pub_date' (descending by publication date), "
#             "'Author' (ascending by first author), "
#             "'JournalName' (ascending by journal name), "
#             "'relevance' (default, 'Best Match' on PubMed web)"
#         ),
#         default="pub_date"
#     )]
#     downloadable_only: Annotated[bool, Field(
#         description="Whether to only return papers that are downloadable from PubMedCentral",
#         default=False
#     )]
#     max_results: Annotated[int, Field(
#         description="The maximum number of results to return",
#         default=100
#     )]


class PubMedPipelineParameters(PipelineParameters):
    """
    Parameters for running the PubMedPipeline.

    Attributes:
        query (str): The query to search for in PubMed.
        start_date (str): The start date to search for in PubMed.
        end_date (Optional[str]): The end date to search for in PubMed. If not provided, searches up to the present.
        downloadable_only (bool): Whether to only return papers that are downloadable from PubMedCentral.
        max_results (int): The maximum number of results to return.
    """
    query: str = Field(description="The query to search for in PubMed")
    start_date: str = Field(description="The start date to search for in PubMed")
    end_date: str | None = Field(
        default=None, description="The end date to search for in PubMed"
    )
    sort: Literal['pub_date', 'Author', 'JournalName', 'relevance'] = Field(
        default='pub_date',
        description="Sort: 'pub_date', 'Author', 'JournalName', or 'relevance' (Best Match)"
    )
    downloadable_only: bool = Field(
        default=False, description="Only return papers downloadable from PubMedCentral"
    )
    max_results: int = Field(
        default=100, ge=1, le=10_000, description="Maximum number of results to return"
    )
class PubMedPipeline(Pipeline):
    
    __configuration: PubMedPipelineConfiguration
    
    def __init__(self, configuration: PubMedPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__pubmed_integration = PubMedIntegration(PubMedAPIConfiguration())
    
    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, PubMedPipelineParameters):
            raise ValueError("Parameters must be of type PubMedPipelineParameters")
       
        logger.info(f"Running PubMedPipeline with query: {parameters.query}")
        results: List[PubMedPaperSummary] = self.__pubmed_integration.search_date_range(
            parameters.query,
            start_date=parameters.start_date,
            end_date=parameters.end_date,
            sort=parameters.sort,
            max_results=parameters.max_results,
        )
        logger.info(f"Found {len(results)} results")
       
        graph = Graph()
       
        for result in results:
            if parameters.downloadable_only is True:
                if result.downloadUrl is not None:
                    graph += result.rdf()
            else:
                graph += result.rdf()
        
        return graph 
    
    def as_api(self, router: APIRouter, route_name: str = "", name: str = "", description: str = "", description_stream: str = "", tags: List[str | Enum] | None = ...) -> None:
        pass
    
    def as_tools(self) -> List[BaseTool]:
        
        return [
            StructuredTool(
                name="search_downloadable_pubmed_papers",
                description="Search PubMed for papers within a given date range.",
                func=lambda **kwargs: self.run(
                    PubMedPipelineParameters(**kwargs)
                ).serialize(format="turtle"),
                args_schema=PubMedPipelineParameters,
            )
        ]
    
if __name__ == "__main__":
    import click
    import rich
    
    @click.command()
    @click.option("--query", type=str, required=True)
    @click.option("--start-date", type=str, required=True, help="Start date (YYYY-MM-DD or YYYY/MM/DD)")
    @click.option("--end-date", type=str, required=False, default=None, help="End date (defaults to today)")
    def main(query: str, start_date: str, end_date: Optional[str]):
        pipeline = PubMedPipeline(PubMedPipelineConfiguration())
        graph = pipeline.run(
            PubMedPipelineParameters(
                query=query,
                start_date=start_date,
                end_date=end_date
            )
        )
        with open("pubmed_output.ttl", "w", encoding="utf-8") as f:
            f.write(graph.serialize(format="turtle"))
        rich.print("[green]Graph serialized to pubmed_output.ttl[/green]")
    main()