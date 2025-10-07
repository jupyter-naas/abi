"""
Ontology Generation Pipeline

Combines D3FEND and CCO ontologies with cyber security event data
to create a comprehensive knowledge graph for SPARQL queries.
"""
# type: ignore

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD

class OntologyGenerationPipeline:
    """Pipeline for generating comprehensive cyber security ontologies."""
    
    def __init__(self, 
                 events_yaml_path: str = "events.yaml",
                 storage_base_path: str = "/Users/jrvmac/abi/storage/datastore/cyber",
                 d3fend_ontology_path: str = "ontologies/d3fend.ttl",
                 d3fend_cco_mapping_path: str = "ontologies/mappings/d3fend-cco.ttl"):
        """Initialize the ontology generation pipeline."""
        self.events_yaml_path = events_yaml_path
        self.storage_base_path = Path(storage_base_path)
        self.d3fend_ontology_path = d3fend_ontology_path
        self.d3fend_cco_mapping_path = d3fend_cco_mapping_path
        
        # Create namespaces
        self.CSE = Namespace("https://abi.cyber-security-events.org/ontology/")
        self.D3FEND = Namespace("http://d3fend.mitre.org/ontologies/d3fend.owl#")
        self.CCO = Namespace("http://www.ontologyrepository.com/CommonCoreOntologies/")
        self.STIX = Namespace("http://stix.mitre.org/stixCommon#")
        
        # Initialize main graph
        self.graph = Graph()
        self.bind_namespaces()
    
    def bind_namespaces(self):
        """Bind namespaces to the graph."""
        self.graph.bind("cse", self.CSE)
        self.graph.bind("d3fend", self.D3FEND)
        self.graph.bind("cco", self.CCO)
        self.graph.bind("stix", self.STIX)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("owl", OWL)
    
    def load_base_ontologies(self):
        """Load D3FEND and CCO ontologies."""
        print("📚 Loading base ontologies...")
        
        # Load D3FEND ontology
        if Path(self.d3fend_ontology_path).exists():
            try:
                self.graph.parse(self.d3fend_ontology_path, format="turtle")
                print(f"✅ Loaded D3FEND ontology: {len(self.graph)} triples")
            except Exception as e:
                print(f"⚠️  Warning: Could not load D3FEND ontology: {e}")
        
        # Load D3FEND-CCO mappings
        if Path(self.d3fend_cco_mapping_path).exists():
            try:
                self.graph.parse(self.d3fend_cco_mapping_path, format="turtle")
                print(f"✅ Loaded D3FEND-CCO mappings: {len(self.graph)} triples")
            except Exception as e:
                print(f"⚠️  Warning: Could not load D3FEND-CCO mappings: {e}")
    
    def load_events_data(self) -> List[Dict[str, Any]]:
        """Load events from YAML file."""
        try:
            with open(self.events_yaml_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                return data.get('events', [])
        except Exception as e:
            print(f"❌ Error loading events: {e}")
            return []
    
    def create_event_ontology_classes(self):
        """Create ontology classes for cyber security events."""
        print("🏗️  Creating event ontology classes...")
        
        # Main classes
        classes = {
            "CyberSecurityEvent": "A cyber security incident or attack",
            "AttackVector": "Method used to gain unauthorized access",
            "DefensiveTechnique": "Security measure to prevent or mitigate attacks",
            "AffectedSector": "Industry or sector impacted by cyber attack",
            "ThreatActor": "Entity responsible for cyber attack",
            "Vulnerability": "Security weakness that can be exploited",
            "Impact": "Consequence or damage from cyber attack",
            "Timeline": "Temporal sequence of cyber security events"
        }
        
        for class_name, description in classes.items():
            class_uri = self.CSE[class_name]
            self.graph.add((class_uri, RDF.type, OWL.Class))
            self.graph.add((class_uri, RDFS.label, Literal(class_name)))
            self.graph.add((class_uri, RDFS.comment, Literal(description)))
    
    def create_event_properties(self):
        """Create properties for cyber security events."""
        print("🔗 Creating event properties...")
        
        # Object properties
        object_properties = {
            "hasAttackVector": "Links event to attack vector used",
            "hasDefensiveTechnique": "Links event to applicable defensive technique",
            "affectsSector": "Links event to affected industry sector",
            "hasImpact": "Links event to its impact or consequences",
            "usesVulnerability": "Links event to exploited vulnerability",
            "attributedTo": "Links event to threat actor",
            "followedBy": "Temporal relationship between events",
            "mitigatedBy": "Links attack vector to defensive technique"
        }
        
        for prop_name, description in object_properties.items():
            prop_uri = self.CSE[prop_name]
            self.graph.add((prop_uri, RDF.type, OWL.ObjectProperty))
            self.graph.add((prop_uri, RDFS.label, Literal(prop_name)))
            self.graph.add((prop_uri, RDFS.comment, Literal(description)))
        
        # Data properties
        data_properties = {
            "eventId": "Unique identifier for the event",
            "eventName": "Human-readable name of the event",
            "eventDate": "Date when the event occurred",
            "severity": "Severity level of the event",
            "category": "Category classification of the event",
            "description": "Detailed description of the event",
            "sourceUrl": "URL of information source about the event",
            "affectedCount": "Number of entities affected",
            "financialImpact": "Estimated financial damage"
        }
        
        for prop_name, description in data_properties.items():
            prop_uri = self.CSE[prop_name]
            self.graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))
            self.graph.add((prop_uri, RDFS.label, Literal(prop_name)))
            self.graph.add((prop_uri, RDFS.comment, Literal(description)))
    
    def add_event_instances(self, events: List[Dict[str, Any]]):
        """Add event instances to the ontology."""
        print(f"📝 Adding {len(events)} event instances...")
        
        for event in events:
            event_id = event.get('id', 'unknown')
            event_uri = self.CSE[f"event_{event_id}"]
            
            # Add event as instance of CyberSecurityEvent
            self.graph.add((event_uri, RDF.type, self.CSE.CyberSecurityEvent))
            
            # Add basic properties
            if event.get('id'):
                self.graph.add((event_uri, self.CSE.eventId, Literal(event['id'])))
            if event.get('name'):
                self.graph.add((event_uri, self.CSE.eventName, Literal(event['name'])))
            if event.get('date'):
                self.graph.add((event_uri, self.CSE.eventDate, Literal(event['date'], datatype=XSD.date)))
            if event.get('severity'):
                self.graph.add((event_uri, self.CSE.severity, Literal(event['severity'])))
            if event.get('category'):
                self.graph.add((event_uri, self.CSE.category, Literal(event['category'])))
            if event.get('description'):
                self.graph.add((event_uri, self.CSE.description, Literal(event['description'])))
            
            # Add attack vectors
            for vector in event.get('attack_vectors', []):
                vector_uri = self.CSE[f"attack_vector_{vector}"]
                self.graph.add((vector_uri, RDF.type, self.CSE.AttackVector))
                self.graph.add((vector_uri, RDFS.label, Literal(vector.replace('_', ' ').title())))
                self.graph.add((event_uri, self.CSE.hasAttackVector, vector_uri))
            
            # Add defensive techniques (D3FEND mapping)
            for technique in event.get('d3fend_techniques', []):
                technique_uri = self.D3FEND[technique]
                self.graph.add((technique_uri, RDF.type, self.CSE.DefensiveTechnique))
                self.graph.add((event_uri, self.CSE.hasDefensiveTechnique, technique_uri))
            
            # Add affected sectors
            for sector in event.get('affected_sectors', []):
                sector_uri = self.CSE[f"sector_{sector}"]
                self.graph.add((sector_uri, RDF.type, self.CSE.AffectedSector))
                self.graph.add((sector_uri, RDFS.label, Literal(sector.replace('_', ' ').title())))
                self.graph.add((event_uri, self.CSE.affectsSector, sector_uri))
            
            # Add sources
            for source in event.get('sources', []):
                if source.get('url'):
                    self.graph.add((event_uri, self.CSE.sourceUrl, Literal(source['url'])))
    
    def add_d3fend_mappings(self, events: List[Dict[str, Any]]):
        """Add D3FEND defensive technique mappings."""
        print("🛡️  Adding D3FEND defensive mappings...")
        
        # Attack vector to defensive technique mappings
        mappings = {
            "supply_chain_compromise": ["D3-SWID", "D3-HBPI", "D3-CSPP"],
            "phishing": ["D3-EMAC", "D3-CSPP", "D3-ANCI"],
            "ransomware": ["D3-BDI", "D3-DNSL", "D3-FBA"],
            "credential_stuffing": ["D3-ANCI", "D3-MFA", "D3-CSPP"],
            "lateral_movement": ["D3-NTF", "D3-CSPP", "D3-RTSD"],
            "data_exfiltration": ["D3-CSPP", "D3-ANCI", "D3-BDI"]
        }
        
        for event in events:
            for attack_vector in event.get('attack_vectors', []):
                if attack_vector in mappings:
                    attack_vector_uri = self.CSE[f"attack_vector_{attack_vector}"]
                    
                    for technique_id in mappings[attack_vector]:
                        technique_uri = self.D3FEND[technique_id]
                        self.graph.add((attack_vector_uri, self.CSE.mitigatedBy, technique_uri))
    
    def generate_comprehensive_ontology(self) -> str:
        """Generate the complete cyber security ontology."""
        print("🚀 Generating comprehensive cyber security ontology...")
        
        # Load base ontologies
        self.load_base_ontologies()
        
        # Create ontology structure
        self.create_event_ontology_classes()
        self.create_event_properties()
        
        # Load and process events
        events = self.load_events_data()
        if events:
            self.add_event_instances(events)
            self.add_d3fend_mappings(events)
        
        # Save the complete ontology
        output_path = self.storage_base_path / "cyber_security_ontology.ttl"
        self.storage_base_path.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.graph.serialize(format='turtle'))
        
        print(f"✅ Generated ontology with {len(self.graph)} triples")
        print(f"📁 Saved to: {output_path}")
        
        return str(output_path)
    
    def generate_sparql_queries(self) -> Dict[str, str]:
        """Generate useful SPARQL queries for the ontology."""
        queries = {
            "all_events": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?event ?name ?date ?severity ?category WHERE {
                    ?event a cse:CyberSecurityEvent ;
                           cse:eventName ?name ;
                           cse:eventDate ?date ;
                           cse:severity ?severity ;
                           cse:category ?category .
                }
                ORDER BY DESC(?date)
            """,
            
            "events_by_severity": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                
                SELECT ?severity (COUNT(?event) as ?count) WHERE {
                    ?event a cse:CyberSecurityEvent ;
                           cse:severity ?severity .
                }
                GROUP BY ?severity
                ORDER BY DESC(?count)
            """,
            
            "attack_vectors_and_defenses": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                PREFIX d3fend: <http://d3fend.mitre.org/ontologies/d3fend.owl#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?attack_vector ?defense_technique WHERE {
                    ?attack_vector a cse:AttackVector ;
                                   cse:mitigatedBy ?defense_technique .
                    ?defense_technique a cse:DefensiveTechnique .
                }
            """,
            
            "sector_impact_analysis": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?sector ?sector_label (COUNT(?event) as ?incident_count) WHERE {
                    ?event a cse:CyberSecurityEvent ;
                           cse:affectsSector ?sector .
                    ?sector rdfs:label ?sector_label .
                }
                GROUP BY ?sector ?sector_label
                ORDER BY DESC(?incident_count)
            """,
            
            "timeline_analysis": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                
                SELECT ?date ?event_name ?severity ?category WHERE {
                    ?event a cse:CyberSecurityEvent ;
                           cse:eventDate ?date ;
                           cse:eventName ?event_name ;
                           cse:severity ?severity ;
                           cse:category ?category .
                }
                ORDER BY ?date
            """,
            
            "critical_events_with_defenses": """
                PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
                PREFIX d3fend: <http://d3fend.mitre.org/ontologies/d3fend.owl#>
                
                SELECT ?event_name ?attack_vector ?defense_technique WHERE {
                    ?event a cse:CyberSecurityEvent ;
                           cse:severity "critical" ;
                           cse:eventName ?event_name ;
                           cse:hasAttackVector ?attack_vector_uri .
                    ?attack_vector_uri rdfs:label ?attack_vector ;
                                       cse:mitigatedBy ?defense_technique .
                }
            """
        }
        
        # Save queries to file
        queries_path = self.storage_base_path / "sparql_queries.json"
        with open(queries_path, 'w', encoding='utf-8') as f:
            json.dump(queries, f, indent=2)
        
        print(f"📋 Generated {len(queries)} SPARQL queries")
        print(f"📁 Saved to: {queries_path}")
        
        return queries


def main():
    """Main function to run the ontology generation pipeline."""
    print("🧠 CYBER SECURITY ONTOLOGY GENERATION PIPELINE")
    print("=" * 60)
    
    pipeline = OntologyGenerationPipeline()
    
    # Generate comprehensive ontology
    ontology_path = pipeline.generate_comprehensive_ontology()
    
    # Generate SPARQL queries
    queries = pipeline.generate_sparql_queries()
    
    print("\n🎉 Ontology generation completed!")
    print(f"📊 Ontology: {ontology_path}")
    print(f"🔍 SPARQL Queries: {len(queries)} queries available")
    print("💾 Storage: /Users/jrvmac/abi/storage/datastore/cyber/")


if __name__ == "__main__":
    main()
