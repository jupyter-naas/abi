from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import requests
import xml.etree.ElementTree as ET
import time

@dataclass
class ArXivIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for ArXiv integration.
    
    Attributes:
        base_url (str): Base URL for the ArXiv API. Defaults to "http://export.arxiv.org/api/query"
        request_interval (float): Time to wait between API requests in seconds. Defaults to 3.0
    """
    base_url: str = "http://export.arxiv.org/api/query"
    request_interval: float = 3.0

class ArXivIntegration(Integration):
    """ArXivIntegration class for interacting with ArXiv.org API.
    
    This class provides methods to interact with ArXiv.org's API endpoints.
    It handles search queries and fetching paper metadata.
    
    Attributes:
        __configuration (ArXivIntegrationConfiguration): Configuration instance
            containing necessary settings for ArXiv API.
    
    Example:
        >>> config = ArXivIntegrationConfiguration()
        >>> integration = ArXivIntegration(config)
        >>> results = integration.search("large language models", max_results=5)
    """

    __configuration: ArXivIntegrationConfiguration

    def __init__(self, configuration: ArXivIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__ns = {'arxiv': 'http://arxiv.org/schemas/atom'}
        self.__last_request_time = 0

    def _rate_limit(self):
        """Enforces rate limiting for API requests."""
        current_time = time.time()
        elapsed = current_time - self.__last_request_time
        
        if elapsed < self.__configuration.request_interval:
            time.sleep(self.__configuration.request_interval - elapsed)
            
        self.__last_request_time = time.time()

    def search(self, query: str, max_results: int = 10, 
               start: int = 0, sort_by: str = "relevance", 
               sort_order: str = "descending") -> List[Dict[str, Any]]:
        """Search for papers on ArXiv based on the given query.
        
        Args:
            query (str): Search query string
            max_results (int, optional): Maximum number of results to return. Defaults to 10.
            start (int, optional): Index of the first result to return. Defaults to 0.
            sort_by (str, optional): Field to sort by. Defaults to "relevance".
            sort_order (str, optional): Sort order. Defaults to "descending".
            
        Returns:
            List[Dict[str, Any]]: List of papers matching the query
        """
        self._rate_limit()
        
        params = {
            'search_query': query,
            'start': start,
            'max_results': max_results,
            'sortBy': sort_by,
            'sortOrder': sort_order
        }
        
        response = requests.get(self.__configuration.base_url, params=params)
        response.raise_for_status()
        
        return self._parse_response(response.text)
    
    def get_paper_by_id(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific paper by its ArXiv ID.
        
        Args:
            paper_id (str): ArXiv ID of the paper (e.g., "2303.08774")
            
        Returns:
            Optional[Dict[str, Any]]: Paper metadata or None if not found
        """
        self._rate_limit()
        
        params = {
            'id_list': paper_id
        }
        
        response = requests.get(self.__configuration.base_url, params=params)
        response.raise_for_status()
        
        results = self._parse_response(response.text)
        return results[0] if results else None
    
    def _parse_response(self, xml_text: str) -> List[Dict[str, Any]]:
        """Parse the XML response from ArXiv API.
        
        Args:
            xml_text (str): XML response text
            
        Returns:
            List[Dict[str, Any]]: List of parsed paper metadata
        """
        root = ET.fromstring(xml_text)
        entries = root.findall('.//entry', self.__ns)
        
        results = []
        for entry in entries:
            paper = {
                'id': self._get_text(entry, './id'),
                'arxiv_id': self._get_text(entry, './id').split('/')[-1],
                'title': self._get_text(entry, './title'),
                'summary': self._get_text(entry, './summary'),
                'published': self._get_text(entry, './published'),
                'updated': self._get_text(entry, './updated'),
                'authors': [
                    {'name': self._get_text(author, './name')} 
                    for author in entry.findall('./author', self.__ns)
                ],
                'categories': [
                    {'term': cat.get('term')} 
                    for cat in entry.findall('./category', self.__ns)
                ],
                'pdf_url': self._get_pdf_link(entry)
            }
            results.append(paper)
            
        return results
    
    def _get_text(self, element, xpath: str) -> str:
        """Extract text from an XML element.
        
        Args:
            element: XML element
            xpath (str): XPath to the target element
            
        Returns:
            str: Text content of the element or empty string if not found
        """
        el = element.find(xpath, self.__ns)
        return el.text.strip() if el is not None and el.text else ""
    
    def _get_pdf_link(self, entry) -> str:
        """Extract PDF link from entry.
        
        Args:
            entry: Entry XML element
            
        Returns:
            str: PDF URL or empty string if not found
        """
        for link in entry.findall('./link', self.__ns):
            if link.get('title') == 'pdf':
                return link.get('href', '')
        return "" 