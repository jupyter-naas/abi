from lib.abi.services.ontology_store.OntologyStorePorts import IOntologyStorePort, OntologyNotFoundError

from rdflib import Graph
from typing import List

class OntologyStoreService__SecondaryAdaptor__Filesystem(IOntologyStorePort):
    __store_path: str
    
    def __init__(self, store_path: str):
        self.__store_path = store_path
    
    def __merge_graphs(self, graphs: List[Graph]) -> Graph:
        merged_graph = Graph()
        for graph in graphs:
            merged_graph += graph
            
        return merged_graph
    
    ## File System Methods
    
    def store(self, name: str, ontology: Graph):
        import os
        import re
        
        # Validate filename is filesystem compliant
        if not re.match(r'^[\w\-. ]+$', name):
            raise ValueError(f"Invalid filename: {name}. Filename must only contain letters, numbers, spaces, hyphens, periods and underscores")
            
        file_path = os.path.join(self.__store_path, f"{name}.ttl")
        
        # Create directory if it doesn't exist
        os.makedirs(self.__store_path, exist_ok=True)
        
        # Get existing prefixes if file exists
        existing_prefixes = {}
        if os.path.exists(file_path):
            existing_graph = Graph()
            existing_graph.parse(file_path, format='turtle')
            existing_prefixes = dict(existing_graph.namespaces())
            
        # Update graph with existing prefixes
        for prefix, namespace in existing_prefixes.items():
            ontology.bind(prefix, namespace)
            
        # Serialize and save the graph
        ontology.serialize(destination=file_path, format='turtle')
    
    def delete(self, name: str):
        import os
        
        file_path = os.path.join(self.__store_path, f"{name}.ttl")
        os.remove(file_path)
    
    
    def list_ontologies(self) -> List[str]:
        import os
        
        return [name for name in os.listdir(self.__store_path) if name.endswith('.ttl')]
    
    ## Ontology Methods

    def get(self, name: str) -> Graph:
        import os
        
        file_path = os.path.join(self.__store_path, f"{name}.ttl")
        
        if not os.path.exists(file_path):
            raise OntologyNotFoundError(f"Ontology with name {name} not found")
        
        return Graph().parse(file_path, format='turtle')
        
    def get_by_names(self, names: List[str]) -> List[Graph]:
        ontologies = [self.get(name) for name in names]
            
        return self.__merge_graphs(ontologies)
    
    def get_all(self) -> Graph:
        import os
        
        file_paths = [os.path.join(self.__store_path, name) for name in os.listdir(self.__store_path)]
        ontologies = [Graph().parse(file_path, format='turtle') for file_path in file_paths]
        
        return self.__merge_graphs(ontologies)
    
    def query(self, query: str) -> Graph:
        aggregate_graph = self.get_all()
        
        return aggregate_graph.query(query)
    
    def query_by_name(self, name: str, query: str) -> Graph:
        ontology = self.get(name)

        return ontology.query(query)
    

