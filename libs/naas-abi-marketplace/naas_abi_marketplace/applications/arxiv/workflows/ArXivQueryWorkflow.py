import glob
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.utils.Graph import ABIGraph
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from pydantic import BaseModel, Field
from rdflib import Graph
from rdflib.query import ResultRow


@dataclass
class ArXivQueryWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for ArXivQueryWorkflow.

    Attributes:
        storage_path (str): Path to the ArXiv TTL files directory
    """

    storage_path: str = "storage/triplestore/application-level/arxiv"


class AuthorQueryParameters(BaseModel):
    """Parameters for querying paper authors.

    Attributes:
        paper_id (str, optional): ArXiv paper ID
        paper_title (str, optional): Title or part of the title of the paper
    """

    paper_id: Optional[str] = Field(None, description="ArXiv paper ID")
    paper_title: Optional[str] = Field(
        None, description="Title or part of the title of the paper"
    )


class PaperQueryParameters(BaseModel):
    """Parameters for querying papers.

    Attributes:
        author_name (str, optional): Name of the author
        category (str, optional): ArXiv category
    """

    author_name: Optional[str] = Field(None, description="Name of the author")
    category: Optional[str] = Field(None, description="ArXiv category")


class SchemaParameters(BaseModel):
    """Parameters for getting the ontology schema."""

    pass


class SparqlQueryParameters(BaseModel):
    """Parameters for executing a custom SPARQL query.

    Attributes:
        query (str): The SPARQL query to execute
    """

    query: str = Field(..., description="The SPARQL query to execute")


class ArXivQueryWorkflow(Workflow):
    """Workflow for querying ArXiv paper data in the knowledge graph.

    This workflow enables:
    - Finding authors of papers
    - Finding papers by author or category
    - Executing custom SPARQL queries
    """

    __configuration: ArXivQueryWorkflowConfiguration

    def __init__(self, configuration: ArXivQueryWorkflowConfiguration):
        self.__configuration = configuration

    def _load_graph(self) -> Graph:
        """Loads all TTL files from the storage path into a single graph.

        Returns:
            Graph: Combined graph from all TTL files
        """
        combined_graph = ABIGraph()

        if not os.path.exists(self.__configuration.storage_path):
            print(
                f"Warning: Storage path {self.__configuration.storage_path} does not exist"
            )
            return combined_graph

        # Get all TTL files in the storage directory
        ttl_files = glob.glob(os.path.join(self.__configuration.storage_path, "*.ttl"))

        if not ttl_files:
            print(f"Warning: No TTL files found in {self.__configuration.storage_path}")
            return combined_graph

        # Load each file into the combined graph
        for ttl_file in ttl_files:
            try:
                file_graph = Graph()
                file_graph.parse(ttl_file, format="turtle")
                for triple in file_graph:
                    combined_graph.add(triple)
            except Exception as e:
                print(f"Error loading {ttl_file}: {e}")

        return combined_graph

    def query_authors(self, parameters: AuthorQueryParameters) -> Dict[str, Any]:
        """Finds authors of a paper based on ID or title.

        Args:
            parameters: Query parameters with paper_id or paper_title

        Returns:
            Dict containing the authors of the paper
        """
        graph = self._load_graph()

        if not parameters.paper_id and not parameters.paper_title:
            return {"error": "You must provide either paper_id or paper_title"}

        # Build query based on provided parameters
        query = """
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?paper ?paperTitle ?author ?authorName
        WHERE {
            ?paper a abi:ArXivPaper ;
                  rdfs:label ?paperTitle ;
                  abi:hasAuthor ?author .
            ?author rdfs:label ?authorName .
        """

        # Add filters based on parameters
        if parameters.paper_id:
            query += f"""
            FILTER(CONTAINS(STR(?paper), "{parameters.paper_id}"))
            """

        if parameters.paper_title:
            query += f"""
            FILTER(CONTAINS(LCASE(?paperTitle), LCASE("{parameters.paper_title}")))
            """

        query += "}"

        results = graph.query(query)

        papers: Dict[str, Dict[str, Any]] = {}
        for row in results:
            # Type assertion for SPARQL result row
            if (
                isinstance(row, ResultRow)
                and hasattr(row, "paper")
                and hasattr(row, "paperTitle")
                and hasattr(row, "authorName")
            ):
                paper_uri = str(row.paper)
                paper_id = paper_uri.split("/")[-1]
                paper_title = str(row.paperTitle)
                author_name = str(row.authorName)

                if paper_id not in papers:
                    papers[paper_id] = {
                        "id": paper_id,
                        "title": paper_title,
                        "authors": [],
                    }

                authors_list: list[str] = papers[paper_id]["authors"]
                if author_name not in authors_list:
                    authors_list.append(author_name)

        return {"papers": list(papers.values())}

    def query_papers(self, parameters: PaperQueryParameters) -> Dict[str, Any]:
        """Finds papers by author name or category.

        Args:
            parameters: Query parameters with author_name or category

        Returns:
            Dict containing the matching papers
        """
        graph = self._load_graph()

        if not parameters.author_name and not parameters.category:
            return {"error": "You must provide either author_name or category"}

        # Build query based on provided parameters
        query = """
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?paper ?paperTitle ?pdfUrl
        WHERE {
            ?paper a abi:ArXivPaper ;
                  rdfs:label ?paperTitle .
            OPTIONAL { ?paper abi:url ?pdfUrl . }
        """

        # Add filters based on parameters
        if parameters.author_name:
            query += f"""
            ?paper abi:hasAuthor ?author .
            ?author rdfs:label ?authorName .
            FILTER(CONTAINS(LCASE(?authorName), LCASE("{parameters.author_name}")))
            """

        if parameters.category:
            query += f"""
            ?paper abi:hasCategory ?category .
            ?category rdfs:label ?categoryName .
            FILTER(CONTAINS(LCASE(?categoryName), LCASE("{parameters.category}")))
            """

        query += "}"

        results = graph.query(query)

        papers = []
        for row in results:
            # Type assertion for SPARQL result row
            if (
                isinstance(row, ResultRow)
                and hasattr(row, "paper")
                and hasattr(row, "paperTitle")
                and hasattr(row, "pdfUrl")
            ):
                paper_uri = str(row.paper)
                paper_id = paper_uri.split("/")[-1]
                paper_title = str(row.paperTitle)
                pdf_url = str(row.pdfUrl) if row.pdfUrl else None

                papers.append(
                    {"id": paper_id, "title": paper_title, "pdf_url": pdf_url}
                )

        return {"papers": papers}

    def get_schema(self, parameters: SchemaParameters) -> Dict[str, str]:
        """Gets the ArXiv ontology schema.

        Args:
            parameters: Schema parameters (unused)

        Returns:
            Dict[str, str]: The ArXiv ontology schema in turtle format or error message
        """
        ontology_path = "src/custom/modules/arxiv_agent/ontologies/ArXivOntology.ttl"

        if not os.path.exists(ontology_path):
            return {"error": f"Ontology file not found at {ontology_path}"}

        with open(ontology_path, "r") as f:
            return {"schema": f.read()}

    def execute_query(self, parameters: SparqlQueryParameters) -> Dict[str, Any]:
        """Executes a custom SPARQL query against the ArXiv knowledge graph.

        Args:
            parameters: Parameters containing the SPARQL query

        Returns:
            Dict: Query results
        """
        graph = self._load_graph()

        try:
            results = graph.query(parameters.query)

            # Convert results to a list of dictionaries
            result_list = []
            for row in results:
                row_dict = {}
                if (
                    isinstance(row, ResultRow) and results.vars
                ):  # Check if vars is not None
                    for var in results.vars:
                        if getattr(row, var) is not None:
                            row_dict[var] = str(getattr(row, var))
                result_list.append(row_dict)

            return {"results": result_list}
        except Exception as e:
            return {"error": f"Query execution failed: {str(e)}"}

    def get_frequent_authors(self) -> Dict[str, Any]:
        """Identifies authors who appear most frequently in the stored papers.

        Returns:
            Dict containing author names and their frequency counts
        """
        graph = self._load_graph()

        # Properly structured SPARQL query with explicit namespace declarations
        query = """
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?authorName (COUNT(?paper) as ?paperCount)
        WHERE {
            ?paper a abi:ArXivPaper ;
                  abi:hasAuthor ?author .
            ?author rdfs:label ?authorName .
        }
        GROUP BY ?authorName
        ORDER BY DESC(?paperCount)
        """

        try:
            results = graph.query(query)

            authors = []
            for row in results:
                # Type assertion for SPARQL result row
                if (
                    isinstance(row, ResultRow)
                    and hasattr(row, "authorName")
                    and hasattr(row, "paperCount")
                ):
                    authors.append(
                        {
                            "name": str(row.authorName),
                            "paper_count": int(row.paperCount),
                        }
                    )

            return {"authors": authors}
        except Exception as e:
            return {"error": f"Query execution failed: {str(e)}"}

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow.

        Returns:
            list[StructuredTool]: List of workflow tools
        """
        return [
            StructuredTool(
                name="query_arxiv_authors",
                description="Find the authors of a paper by paper ID or title",
                func=lambda **kwargs: self.query_authors(
                    AuthorQueryParameters(**kwargs)  # type: ignore
                ),
                args_schema=AuthorQueryParameters,
            ),
            StructuredTool(
                name="query_arxiv_papers",
                description="Find papers by author name or category",
                func=lambda **kwargs: self.query_papers(PaperQueryParameters(**kwargs)),
                args_schema=PaperQueryParameters,
            ),
            StructuredTool(
                name="get_arxiv_schema",
                description="Get the ArXiv ontology schema in turtle format",
                func=lambda **kwargs: self.get_schema(SchemaParameters(**kwargs)),
                args_schema=SchemaParameters,
            ),
            StructuredTool(
                name="execute_arxiv_query",
                description="Execute a custom SPARQL query against the ArXiv knowledge graph",
                func=lambda **kwargs: self.execute_query(
                    SparqlQueryParameters(**kwargs)
                ),
                args_schema=SparqlQueryParameters,
            ),
            StructuredTool(
                name="get_frequent_authors",
                description="Find which authors appear most frequently in your saved papers",
                func=lambda **kwargs: self.get_frequent_authors(),
                args_schema=BaseModel,
            ),
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
        """Adds API endpoints for this workflow to the given router.

        Args:
            router (APIRouter): FastAPI router to add endpoints to
            route_name (str): Name for the route
            name (str): Name for the API
            description (str): Description for the API
            description_stream (str): Description for streaming
            tags (list[str]): Tags for the API
        """

        @router.post("/arxiv/query-authors")
        def query_authors(parameters: AuthorQueryParameters):
            return self.query_authors(parameters)

        @router.post("/arxiv/query-papers")
        def query_papers(parameters: PaperQueryParameters):
            return self.query_papers(parameters)

        @router.post("/arxiv/schema")
        def get_schema(parameters: SchemaParameters):
            return self.get_schema(parameters)

        @router.post("/arxiv/query")
        def execute_query(parameters: SparqlQueryParameters):
            return self.execute_query(parameters)


if __name__ == "__main__":
    # For testing the workflow directly
    workflow = ArXivQueryWorkflow(ArXivQueryWorkflowConfiguration())

    # Example: Find authors of a paper by title
    test_result = workflow.query_authors(
        AuthorQueryParameters(paper_title="scaling", paper_id="2206.11097")
    )
    print("Authors query result:", test_result)
