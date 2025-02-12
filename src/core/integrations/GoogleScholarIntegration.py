from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from typing import Optional, List
from scholarly import scholarly
from abi import logger

LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Google_Scholar_logo.svg/2048px-Google_Scholar_logo.svg.png"

@dataclass
class GoogleScholarConfiguration(IntegrationConfiguration):
    """Configuration for Google Scholar integration.
    
    Note: Google Scholar doesn't require authentication for basic searches,
    but we keep the configuration class for consistency.
    """
    pass

class GoogleScholarIntegration(Integration):
    """Google Scholar integration for performing academic searches.
    
    This class provides methods to search Google Scholar and get academic publication results.
    """

    __configuration: GoogleScholarConfiguration

    def __init__(self, configuration: GoogleScholarConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def search_publications(
        self,
        query: str,
        limit: int = 10
    ) -> List[dict]:
        """Search for academic publications on Google Scholar.
        
        Args:
            query (str): Search query
            limit (int): Maximum number of results to return. Defaults to 10
            
        Returns:
            List[dict]: List of publication results with title, authors, year, citations, etc.
        """
        try:
            if not query:
                logger.error("Empty search query provided")
                return []
                
            search_query = scholarly.search_pubs(query)
            results = []
            
            for i, pub in enumerate(search_query):
                if i >= limit:
                    break
                try:
                    results.append({
                        "title": pub.get("bib", {}).get("title"),
                        "authors": pub.get("bib", {}).get("author", []),
                        "year": pub.get("bib", {}).get("pub_year"),
                        "venue": pub.get("bib", {}).get("venue"),
                        "citations": pub.get("num_citations", 0),
                        "url": pub.get("pub_url"),
                        "abstract": pub.get("bib", {}).get("abstract", ""),
                        "keywords": pub.get("bib", {}).get("keywords", [])
                    })
                except Exception as e:
                    logger.warning(f"Error processing publication result: {e}")
                    continue
                
            return results
            
        except Exception as e:
            logger.error(f"Error searching Google Scholar: {e}")
            return []

    def search_author(
        self,
        author_name: str
    ) -> Optional[dict]:
        """Search for an author profile on Google Scholar.
        
        Args:
            author_name (str): Name of the author to search for
            
        Returns:
            Optional[dict]: Author profile data if found, None otherwise
        """
        try:
            search_query = scholarly.search_author(author_name)
            author = next(search_query, None)
            
            if author:
                return {
                    "name": author.get("name"),
                    "affiliation": author.get("affiliation"),
                    "interests": author.get("interests", []),
                    "citations": author.get("citedby", 0),
                    "h_index": author.get("hindex", 0),
                    "i10_index": author.get("i10index", 0)
                }
            return None
            
        except Exception as e:
            logger.error(f"Error searching Google Scholar author: {e}")
            return None

    @staticmethod
    def as_tools(configuration: GoogleScholarConfiguration):
        """Convert Google Scholar integration into LangChain tools."""
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, Field
        
        integration = GoogleScholarIntegration(configuration)
        
        class SearchPublicationsSchema(BaseModel):
            query: str = Field(..., description="Search query for publications")
            limit: int = Field(10, description="Maximum number of results to return")

        class SearchAuthorSchema(BaseModel):
            author_name: str = Field(..., description="Name of the author to search for")

        return [
            StructuredTool(
                name="googlescholar_search_publications",
                description="Search for academic publications on Google Scholar",
                func=lambda **kwargs: integration.search_publications(**kwargs),
                args_schema=SearchPublicationsSchema
            ),
            StructuredTool(
                name="googlescholar_search_author",
                description="Search for an author profile on Google Scholar",
                func=lambda **kwargs: integration.search_author(**kwargs),
                args_schema=SearchAuthorSchema
            )
        ] 