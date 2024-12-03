from pathlib import Path
import rdflib
from pyvis.network import Network
from rdflib import Namespace
import logging

class OntologyVisualizer:
    def __init__(self, ontology_path: str = "ontology/consolidated_ontology.ttl"):
        self.graph = rdflib.Graph()
        self.logger = logging.getLogger(__name__)
        self.ontology_path = Path(ontology_path)
        
        # Initialize pyvis network
        self.net = Network(
            height="750px",
            width="100%",
            bgcolor="#ffffff",
            font_color="#000000"
        )
        
        # Configure physics
        self.net.force_atlas_2based()
        self.net.show_buttons(filter_=['physics'])
        
        # Define color scheme for different namespaces
        self.namespace_colors = {
            'bfo': '#4287f5',    # Blue
            'cco': '#f5d142',    # Yellow
            'domain': '#f58442', # Orange
            'application': '#42f554'  # Green
        }

    def get_node_color(self, uri: str) -> str:
        """Determine node color based on its namespace"""
        if 'purl.obolibrary.org/obo/bfo' in uri:
            return self.namespace_colors['bfo']
        elif 'commoncoreontologies.org' in uri:
            return self.namespace_colors['cco']
        elif 'ontology.naas.ai/abi' in uri:
            # Check if it's a domain or application level concept
            if any(domain_term in uri.lower() for domain_term in 
                  ['person', 'organization', 'asset', 'post', 'idea', 'growth']):
                return self.namespace_colors['domain']
            return self.namespace_colors['application']
        return '#97c2fc'  # Default color for other nodes

    def load_ontology(self):
        """Load the consolidated ontology file"""
        try:
            self.graph.parse(str(self.ontology_path), format='turtle')
            self.logger.info(f"Successfully loaded ontology from {self.ontology_path}")
        except Exception as e:
            self.logger.error(f"Error loading ontology: {str(e)}")
            raise

    def create_visualization(self, max_nodes: int = 100):
        """Create the visualization with node limit"""
        # Modified query to get predicate labels from the ontology
        query = """
        SELECT DISTINCT ?subject ?predicate ?object ?slabel ?plabel ?olabel
        WHERE {
            ?subject ?predicate ?object .
            OPTIONAL { ?subject rdfs:label ?slabel }
            OPTIONAL { ?predicate rdfs:label ?plabel }
            OPTIONAL { ?object rdfs:label ?olabel }
            FILTER(isIRI(?subject) && isIRI(?object))
        }
        LIMIT %d
        """ % max_nodes

        try:
            # Execute query
            results = self.graph.query(query)
            
            # Track added nodes to avoid duplicates
            added_nodes = set()
            
            # Common predicate mappings
            predicate_mappings = {
                'http://www.w3.org/1999/02/22-rdf-syntax-ns#type': 'is_a',
                'http://www.w3.org/2000/01/rdf-schema#subClassOf': 'is_subclass_of',
                'http://www.w3.org/2002/07/owl#equivalentClass': 'equivalent_to'
            }
            
            # Add nodes and edges
            for row in results:
                s, p, o = str(row[0]), str(row[1]), str(row[2])
                s_label = str(row[3]) if row[3] else s.split('/')[-1]
                p_label = str(row[4]) if row[4] else p.split('/')[-1]
                o_label = str(row[5]) if row[5] else o.split('/')[-1]
                
                # Add nodes if not already added
                if s not in added_nodes:
                    self.net.add_node(s, 
                                    label=s_label, 
                                    title=s,
                                    color=self.get_node_color(s))
                    added_nodes.add(s)
                
                if o not in added_nodes:
                    self.net.add_node(o, 
                                    label=o_label, 
                                    title=o,
                                    color=self.get_node_color(o))
                    added_nodes.add(o)
                
                # Add edge with label from ontology
                self.net.add_edge(s, o, label=p_label, title=p)
            
            # Add legend
            legend_html = """
            <div style="position: absolute; top: 10px; right: 10px; background-color: white; padding: 10px; border-radius: 5px; border: 1px solid #ccc;">
                <div style="margin-bottom: 5px;"><span style="display: inline-block; width: 20px; height: 20px; background-color: #4287f5; margin-right: 5px;"></span>BFO</div>
                <div style="margin-bottom: 5px;"><span style="display: inline-block; width: 20px; height: 20px; background-color: #f5d142; margin-right: 5px;"></span>CCO</div>
                <div style="margin-bottom: 5px;"><span style="display: inline-block; width: 20px; height: 20px; background-color: #f58442; margin-right: 5px;"></span>Domain</div>
                <div><span style="display: inline-block; width: 20px; height: 20px; background-color: #42f554; margin-right: 5px;"></span>Application</div>
            </div>
            """
            
            # Add the legend to the visualization
            self.net.html = legend_html + self.net.html
            
            self.logger.info(f"Added {len(added_nodes)} nodes to visualization")
            
        except Exception as e:
            self.logger.error(f"Error creating visualization: {str(e)}")
            raise

    def save_visualization(self, output_path: str = "assets/static/ontology_graph.html"):
        """Save the visualization to HTML file"""
        try:
            self.net.save_graph(output_path)
            self.logger.info(f"Visualization saved to {output_path}")
        except Exception as e:
            self.logger.error(f"Error saving visualization: {str(e)}")
            raise