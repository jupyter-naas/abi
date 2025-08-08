"""
SPARQL INSERT Operations for RDF Graphs

This module demonstrates how to insert new triples into an empty RDF graph
using SPARQL INSERT statements with rdflib.
"""

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, FOAF, XSD
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SPARQLInserter:
    """Class to handle SPARQL INSERT operations on RDF graphs."""
    
    def __init__(self):
        """Initialize with an empty graph and define namespaces."""
        self.graph = Graph()
        
        # Define custom namespaces
        self.EX = Namespace("http://example.org/")
        self.PERSON = Namespace("http://example.org/person/")
        self.ORG = Namespace("http://example.org/organization/")
        
        # Bind namespaces to the graph for cleaner serialization
        self.graph.bind("ex", self.EX)
        self.graph.bind("person", self.PERSON)
        self.graph.bind("org", self.ORG)
        self.graph.bind("foaf", FOAF)
    
    def insert_basic_triples(self):
        """Insert basic triples using SPARQL INSERT DATA."""
        query = """
        PREFIX ex: <http://example.org/>
        PREFIX person: <http://example.org/person/>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        INSERT DATA {
            person:john a foaf:Person ;
                        foaf:name "John Doe" ;
                        foaf:age 30 ;
                        foaf:email "john.doe@example.com" .
            
            person:jane a foaf:Person ;
                        foaf:name "Jane Smith" ;
                        foaf:age 28 ;
                        foaf:email "jane.smith@example.com" .
        }
        """
        
        logger.info("Inserting basic person triples...")
        self.graph.update(query)
        logger.info(f"Graph now contains {len(self.graph)} triples")
    
    def insert_with_variables(self):
        """Insert triples using SPARQL INSERT WHERE with variables."""
        # First, let's add some base data to work with
        base_query = """
        PREFIX ex: <http://example.org/>
        PREFIX org: <http://example.org/organization/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        INSERT DATA {
            org:acme_corp rdfs:label "ACME Corporation" ;
                         ex:industry "Technology" .
            
            org:global_inc rdfs:label "Global Inc" ;
                          ex:industry "Finance" .
        }
        """
        self.graph.update(base_query)
        
        # Now insert new triples based on existing data
        query = """
        PREFIX ex: <http://example.org/>
        PREFIX org: <http://example.org/organization/>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        INSERT {
            ?org ex:hasEmployee ?employee .
            ?employee foaf:workplaceHomepage ?org .
        }
        WHERE {
            ?org rdfs:label ?orgName .
            BIND(IRI(CONCAT(STR(?org), "/employee1")) AS ?employee)
        }
        """
        
        logger.info("Inserting triples with variables...")
        self.graph.update(query)
        logger.info(f"Graph now contains {len(self.graph)} triples")
    
    def insert_complex_data(self):
        """Insert complex structured data with relationships."""
        query = """
        PREFIX ex: <http://example.org/>
        PREFIX person: <http://example.org/person/>
        PREFIX org: <http://example.org/organization/>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        
        INSERT DATA {
            # Projects
            ex:project1 a ex:Project ;
                       rdfs:label "AI Research Project" ;
                       ex:startDate "2024-01-01"^^xsd:date ;
                       ex:budget 100000.00 ;
                       ex:status "active" .
            
            ex:project2 a ex:Project ;
                       rdfs:label "Web Development Project" ;
                       ex:startDate "2024-02-15"^^xsd:date ;
                       ex:budget 50000.00 ;
                       ex:status "planning" .
            
            # Relationships
            person:john ex:worksOn ex:project1 ;
                       ex:role "Lead Researcher" ;
                       ex:employedBy org:acme_corp .
            
            person:jane ex:worksOn ex:project2 ;
                       ex:role "Frontend Developer" ;
                       ex:employedBy org:global_inc .
            
            # Project assignments
            ex:project1 ex:assignedTo person:john ;
                       ex:managedBy org:acme_corp .
            
            ex:project2 ex:assignedTo person:jane ;
                       ex:managedBy org:global_inc .
        }
        """
        
        logger.info("Inserting complex structured data...")
        self.graph.update(query)
        logger.info(f"Graph now contains {len(self.graph)} triples")
    
    def insert_with_blank_nodes(self):
        """Insert triples using blank nodes for complex structures."""
        query = """
        PREFIX ex: <http://example.org/>
        PREFIX person: <http://example.org/person/>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        INSERT DATA {
            person:john ex:hasAddress [
                ex:street "123 Main St" ;
                ex:city "Springfield" ;
                ex:state "IL" ;
                ex:zipCode "62701" ;
                ex:country "USA"
            ] .
            
            person:jane ex:hasAddress [
                ex:street "456 Oak Ave" ;
                ex:city "Portland" ;
                ex:state "OR" ;
                ex:zipCode "97201" ;
                ex:country "USA"
            ] .
            
            # Contact information using blank nodes
            person:john ex:hasContact [
                ex:phoneNumber "+1-555-0123" ;
                ex:linkedIn "https://linkedin.com/in/johndoe" ;
                ex:twitter "@johndoe"
            ] .
        }
        """
        
        logger.info("Inserting triples with blank nodes...")
        self.graph.update(query)
        logger.info(f"Graph now contains {len(self.graph)} triples")
    
    def insert_conditional_data(self):
        """Insert data conditionally based on existing triples."""
        query = """
        PREFIX ex: <http://example.org/>
        PREFIX person: <http://example.org/person/>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        INSERT {
            ?person ex:isExperienced true .
            ?person ex:seniority "Senior" .
        }
        WHERE {
            ?person a foaf:Person ;
                   foaf:age ?age .
            FILTER(?age >= 30)
        }
        """
        
        logger.info("Inserting conditional data...")
        self.graph.update(query)
        logger.info(f"Graph now contains {len(self.graph)} triples")
    
    def query_graph(self, query_type="all"):
        """Query the graph to show inserted data."""
        if query_type == "all":
            # Query all triples
            query = """
            SELECT ?subject ?predicate ?object
            WHERE {
                ?subject ?predicate ?object .
            }
            ORDER BY ?subject ?predicate
            """
        elif query_type == "persons":
            # Query only person data
            query = """
            PREFIX foaf: <http://xmlns.com/foaf/0.1/>
            
            SELECT ?person ?name ?age ?email
            WHERE {
                ?person a foaf:Person ;
                       foaf:name ?name .
                OPTIONAL { ?person foaf:age ?age }
                OPTIONAL { ?person foaf:email ?email }
            }
            ORDER BY ?name
            """
        elif query_type == "projects":
            # Query project data
            query = """
            PREFIX ex: <http://example.org/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?project ?label ?status ?assignee
            WHERE {
                ?project a ex:Project ;
                        rdfs:label ?label .
                OPTIONAL { ?project ex:status ?status }
                OPTIONAL { ?project ex:assignedTo ?assignee }
            }
            ORDER BY ?label
            """
        
        logger.info(f"Executing {query_type} query...")
        results = self.graph.query(query)
        
        print(f"\n=== {query_type.upper()} QUERY RESULTS ===")
        for i, row in enumerate(results, 1):
            print(f"{i:2d}. {' | '.join(str(cell) for cell in row)}")
        
        return results
    
    def export_graph(self, format="turtle", filename=None):
        """Export the graph to a file or print to console."""
        if filename:
            logger.info(f"Exporting graph to {filename} in {format} format...")
            self.graph.serialize(destination=filename, format=format)
        else:
            print(f"\n=== GRAPH SERIALIZATION ({format.upper()}) ===")
            print(self.graph.serialize(format=format))
    
    def get_graph_stats(self):
        """Get statistics about the graph."""
        stats = {
            "total_triples": len(self.graph),
            "subjects": len(set(self.graph.subjects())),
            "predicates": len(set(self.graph.predicates())),
            "objects": len(set(self.graph.objects()))
        }
        
        print("\n=== GRAPH STATISTICS ===")
        for key, value in stats.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        
        return stats


def main():
    """Main function to demonstrate SPARQL INSERT operations."""
    print("=== SPARQL INSERT Operations Demo ===\n")
    
    # Create inserter instance
    inserter = SPARQLInserter()
    
    # Demonstrate different INSERT operations
    print("Starting with an empty graph...")
    inserter.get_graph_stats()
    
    # Step 1: Basic inserts
    print("\n" + "="*50)
    inserter.insert_basic_triples()
    inserter.query_graph("persons")
    
    # Step 2: Insert with variables
    print("\n" + "="*50)
    inserter.insert_with_variables()
    
    # Step 3: Complex structured data
    print("\n" + "="*50)
    inserter.insert_complex_data()
    inserter.query_graph("projects")
    
    # Step 4: Blank nodes
    print("\n" + "="*50)
    inserter.insert_with_blank_nodes()
    
    # Step 5: Conditional inserts
    print("\n" + "="*50)
    inserter.insert_conditional_data()
    
    # Final statistics and export
    print("\n" + "="*50)
    inserter.get_graph_stats()
    
    # Show final graph structure
    inserter.export_graph("turtle")
    
    # Optional: Save to file
    # inserter.export_graph("turtle", "inserted_data.ttl")
    # inserter.export_graph("xml", "inserted_data.rdf")


if __name__ == "__main__":
    main()
