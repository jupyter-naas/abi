from abc import ABC, abstractmethod
from rdflib import Graph
from typing import List

class OntologyNotFoundError(Exception):
    pass

class IOntologyStorePort(ABC):
    
    @abstractmethod
    def store(self, name: str, ontology: Graph):
        pass
    
    @abstractmethod
    def get(self, name: str) -> Graph:
        pass
    
    @abstractmethod
    def get_by_names(self, names: List[str]) -> List[Graph]:
        pass

    @abstractmethod
    def get_all(self) -> Graph:
        pass

    @abstractmethod
    def query(self, query: str) -> Graph:
        pass
    
    @abstractmethod
    def query_by_name(self, name: str, query: str) -> Graph:
        pass
    
    @abstractmethod
    def delete(self, name: str):
        pass
    
    @abstractmethod
    def list_ontologies(self) -> List[str]:
        pass

class IOntologyStore(ABC):
    
    __ontology_adaptor: IOntologyStorePort
    
    @abstractmethod
    def store(self, name: str, ontology: Graph, individual_filter: bool = True):
        """Store an ontology with the given name. If an ontology with the same name already exists, it will be replaced.
        
        Args:
            name (str): The name to store the ontology under
            ontology (Graph): The RDF graph containing the ontology to store
            individual_filter (bool, optional): Whether to filter out non-named individuals. Defaults to True.
        """
        pass

    @abstractmethod
    def insert(self, name: str, ontology: Graph, individual_filter: bool = True):
        """Insert to an ontology with the given name. If an ontology with the same name already exists, it will be merged with the new ontology.
        
        Args:
            name (str): The name to store the ontology under
            ontology (Graph): The RDF graph containing the ontology to add
            individual_filter (bool, optional): Whether to filter out non-named individuals. Defaults to True.
        """
        pass
    
    @abstractmethod
    def get(self, name: str) -> Graph:
        pass
    
    @abstractmethod
    def get_by_names(self, names: List[str]) -> List[Graph]:
        pass
    
    @abstractmethod
    def get_all(self) -> Graph:
        pass
    
    @abstractmethod
    def query(self, query: str) -> Graph:
        """Execute a SPARQL query on all ontologies.
        
        Args:
            query (str): The SPARQL query to execute
            
        Returns:
            Graph: The RDF graph containing the query results
        """
        pass
    
    @abstractmethod
    def query_by_name(self, name: str, query: str, commit: bool = False) -> Graph:
        """Execute a SPARQL query on a specific ontology.
        
        Args:
            name (str): The name of the ontology to query
            query (str): The SPARQL query to execute
            commit (bool, optional): Whether to commit any changes made by the query. Defaults to False.
            
        Returns:
            Graph: The RDF graph containing the query results
        """
        pass
    
    @abstractmethod
    def delete(self, name: str):
        pass
    
    @abstractmethod
    def list_ontologies(self) -> List[str]:
        pass
        
