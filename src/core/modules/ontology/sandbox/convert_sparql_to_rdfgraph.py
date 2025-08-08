"""
SPARQL to RDF Graph Converter

This module provides utilities to convert various SPARQL statements and queries
into RDF graphs using rdflib.
"""

import re
from typing import Optional, Union, Dict, Any
from rdflib import Graph, Literal, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SPARQLToRDFConverter:
    """Converts SPARQL statements to RDF graphs."""
    
    def __init__(self):
        """Initialize the converter with common namespaces."""
        self.namespaces = {
            'rdf': RDF,
            'rdfs': RDFS,
            'owl': OWL,
            'xsd': XSD
        }
    
    def extract_rdf_from_insert_data(self, sparql_query: str) -> Graph:
        """
        Extract RDF triples from a SPARQL INSERT DATA statement.
        
        Args:
            sparql_query: SPARQL query containing INSERT DATA
            
        Returns:
            Graph: RDF graph containing the extracted triples
        """
        graph = Graph()
        
        # Bind common namespaces
        for prefix, namespace in self.namespaces.items():
            graph.bind(prefix, namespace)
        
        # Extract PREFIX declarations
        prefix_pattern = r'PREFIX\s+(\w+):\s*<([^>]+)>'
        prefixes = re.findall(prefix_pattern, sparql_query, re.IGNORECASE)
        
        # Bind extracted prefixes to the graph
        for prefix, uri in prefixes:
            namespace = Namespace(uri)
            graph.bind(prefix, namespace)
            self.namespaces[prefix] = namespace
        
        # Extract the data block from INSERT DATA
        insert_data_pattern = r'INSERT\s+DATA\s*\{(.*?)\}(?:\s*$|\s*;|\s*WHERE)'
        match = re.search(insert_data_pattern, sparql_query, re.DOTALL | re.IGNORECASE)
        
        if not match:
            logger.warning("No INSERT DATA block found in SPARQL query")
            return graph
        
        data_block = match.group(1).strip()
        
        # Create a temporary graph to parse the RDF data
        # We need to reconstruct the prefixes and data as valid Turtle
        turtle_content = ""
        
        # Add prefix declarations
        for prefix, uri in prefixes:
            turtle_content += f"@prefix {prefix}: <{uri}> .\n"
        
        turtle_content += "\n" + data_block
        
        try:
            # Parse the Turtle content
            graph.parse(data=turtle_content, format="turtle")
            logger.info(f"Successfully extracted {len(graph)} triples from INSERT DATA")
        except Exception as e:
            logger.error(f"Failed to parse extracted RDF data: {e}")
            logger.debug(f"Attempted to parse: {turtle_content}")
        
        return graph
    
    def execute_sparql_insert(self, sparql_query: str, target_graph: Optional[Graph] = None) -> Graph:
        """
        Execute a SPARQL INSERT statement on a graph.
        
        Args:
            sparql_query: SPARQL INSERT query
            target_graph: Target graph (creates new if None)
            
        Returns:
            Graph: Updated graph with inserted triples
        """
        if target_graph is None:
            target_graph = Graph()
        
        # Bind common namespaces
        for prefix, namespace in self.namespaces.items():
            target_graph.bind(prefix, namespace)
        
        try:
            # Execute the SPARQL update
            target_graph.update(sparql_query)
            logger.info(f"Successfully executed SPARQL INSERT. Graph now contains {len(target_graph)} triples")
        except Exception as e:
            logger.error(f"Failed to execute SPARQL INSERT: {e}")
        
        return target_graph
    
    def sparql_construct_to_graph(self, sparql_query: str, source_graph: Optional[Graph] = None) -> Graph:
        """
        Execute a SPARQL CONSTRUCT query and return the resulting graph.
        
        Args:
            sparql_query: SPARQL CONSTRUCT query
            source_graph: Source graph to query (creates empty if None)
            
        Returns:
            Graph: Graph containing constructed triples
        """
        if source_graph is None:
            source_graph = Graph()
        
        try:
            result_graph = source_graph.query(sparql_query)
            logger.info(f"CONSTRUCT query returned {len(result_graph)} triples")
            return result_graph
        except Exception as e:
            logger.error(f"Failed to execute SPARQL CONSTRUCT: {e}")
            return Graph()
    
    def convert(self, sparql_query: str, method: str = "auto", target_graph: Optional[Graph] = None) -> Graph:
        """
        Convert SPARQL to RDF graph using the appropriate method.
        
        Args:
            sparql_query: SPARQL query or statement
            method: Conversion method ("auto", "insert_data", "insert", "construct")
            target_graph: Target graph for INSERT operations
            
        Returns:
            Graph: Resulting RDF graph
        """
        sparql_query = sparql_query.strip()
        
        if method == "auto":
            if "INSERT DATA" in sparql_query.upper():
                method = "insert_data"
            elif "INSERT" in sparql_query.upper():
                method = "insert"
            elif "CONSTRUCT" in sparql_query.upper():
                method = "construct"
            else:
                logger.warning("Could not determine SPARQL type, defaulting to insert_data")
                method = "insert_data"
        
        if method == "insert_data":
            return self.extract_rdf_from_insert_data(sparql_query)
        elif method == "insert":
            return self.execute_sparql_insert(sparql_query, target_graph)
        elif method == "construct":
            return self.sparql_construct_to_graph(sparql_query, target_graph)
        else:
            raise ValueError(f"Unknown conversion method: {method}")


def main():
    """Demonstrate SPARQL to RDF conversion."""
    converter = SPARQLToRDFConverter()
    
    # Example 1: INSERT DATA statement
    sparql_insert_data = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX bfo: <http://purl.obolibrary.org/obo/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX abi: <http://ontology.naas.ai/abi/>

    INSERT DATA {
        abi:0c418524-fde3-4818-a961-931bde03df53 a bfo:BFO_0000015, owl:NamedIndividual ;
            rdfs:label "Act of X"@en ;
            rdfs:comment "An example entity in the ABI ontology"@en .
    }
    """
    
    print("=== Converting SPARQL INSERT DATA to RDF Graph ===")
    graph1 = converter.convert(sparql_insert_data)
    print(f"Extracted {len(graph1)} triples:")
    print(graph1.serialize(format="turtle"))
    print("\n" + "="*60 + "\n")
    
    # Example 2: Regular INSERT statement (requires execution on a graph)
    sparql_insert = """
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX ex: <http://example.org/>
    
    INSERT DATA {
        ex:alice a foaf:Person ;
                 foaf:name "Alice Smith" ;
                 foaf:age 30 .
    }
    """
    
    print("=== Executing SPARQL INSERT on empty graph ===")
    graph2 = converter.convert(sparql_insert, method="insert")
    print(f"Graph contains {len(graph2)} triples:")
    print(graph2.serialize(format="turtle"))


if __name__ == "__main__":
    main()