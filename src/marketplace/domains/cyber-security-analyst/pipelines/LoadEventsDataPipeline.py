"""
Load Events Data Pipeline

Loads cyber security events from YAML and transforms to RDF triples using D3FEND-CCO ontology.
"""

from pathlib import Path
from rdflib import Graph, Namespace, Literal, RDF, RDFS
from rdflib.namespace import XSD
import yaml
from abi import logger

# Define namespaces
CSE = Namespace("https://abi.cyber-security-events.org/ontology/")
D3F = Namespace("http://d3fend.mitre.org/ontologies/d3fend.owl#")
BFO = Namespace("http://purl.obolibrary.org/obo/")


def load_events_to_graph(events_file_path: str) -> Graph:
    """
    Load cyber security events from YAML and transform to RDF graph.
    
    Args:
        events_file_path: Path to events.yaml file
    
    Returns:
        Graph: RDF graph with cyber security events as triples
    """
    graph = Graph()
    
    # Bind namespaces
    graph.bind("cse", CSE)
    graph.bind("d3f", D3F)
    graph.bind("bfo", BFO)
    
    # Load YAML
    events_path = Path(events_file_path)
    if not events_path.exists():
        logger.error(f"Events file not found: {events_path}")
        return graph
    
    with open(events_path, 'r') as f:
        data = yaml.safe_load(f)
    
    if not data or 'events' not in data:
        logger.error("No events found in YAML file")
        return graph
    
    events = data['events']
    logger.info(f"Loading {len(events)} cyber security events into knowledge graph")
    
    # Transform each event to RDF triples
    for event_data in events:
        event_uri = CSE[event_data['id']]
        
        # Core event properties
        graph.add((event_uri, RDF.type, CSE.CyberSecurityEvent))
        graph.add((event_uri, RDFS.label, Literal(event_data['name'])))
        graph.add((event_uri, CSE.eventName, Literal(event_data['name'])))
        graph.add((event_uri, CSE.eventDate, Literal(event_data['date'], datatype=XSD.date)))
        graph.add((event_uri, CSE.severity, Literal(event_data['severity'])))
        graph.add((event_uri, CSE.category, Literal(event_data['category'])))
        graph.add((event_uri, CSE.description, Literal(event_data['description'])))
        
        # Affected sectors
        if 'affected_sectors' in event_data:
            for sector in event_data['affected_sectors']:
                graph.add((event_uri, CSE.affectedSector, Literal(sector)))
        
        # Attack vectors
        if 'attack_vectors' in event_data:
            for vector in event_data['attack_vectors']:
                vector_uri = CSE[f"attack_vector_{vector}"]
                graph.add((event_uri, CSE.attackVector, vector_uri))
                graph.add((vector_uri, RDF.type, D3F.AttackVector))
                graph.add((vector_uri, RDFS.label, Literal(vector.replace('_', ' ').title())))
        
        # D3FEND defensive techniques
        if 'd3fend_techniques' in event_data:
            for technique in event_data['d3fend_techniques']:
                technique_uri = D3F[technique]
                graph.add((event_uri, CSE.defensiveTechnique, technique_uri))
                graph.add((technique_uri, RDF.type, D3F.DefensiveTechnique))
                graph.add((technique_uri, RDFS.label, Literal(technique)))
        
        # Impact (if present)
        if 'impact' in event_data:
            graph.add((event_uri, CSE.impact, Literal(event_data['impact'])))
        
        # Sources
        if 'sources' in event_data:
            for i, source in enumerate(event_data['sources']):
                source_uri = CSE[f"{event_data['id']}_source_{i}"]
                graph.add((event_uri, CSE.hasSource, source_uri))
                graph.add((source_uri, RDF.type, CSE.Source))
                if 'url' in source:
                    graph.add((source_uri, CSE.sourceURL, Literal(source['url'], datatype=XSD.anyURI)))
                if 'title' in source:
                    graph.add((source_uri, CSE.sourceTitle, Literal(source['title'])))
    
    logger.info(f"✅ Loaded {len(events)} events ({len(graph)} triples) into knowledge graph")
    return graph


def load_events_to_triplestore(events_file_path: str, triple_store_service) -> int:
    """
    Load events from YAML into the triplestore.
    
    Args:
        events_file_path: Path to events.yaml
        triple_store_service: Triplestore service to insert data into
    
    Returns:
        int: Number of triples inserted
    """
    graph = load_events_to_graph(events_file_path)
    
    if len(graph) == 0:
        logger.warning("No triples to insert")
        return 0
    
    # Insert into triplestore
    try:
        triple_store_service.insert(graph)
        logger.info(f"✅ Successfully inserted {len(graph)} triples into Oxigraph")
        return len(graph)
    except Exception as e:
        logger.error(f"❌ Failed to insert triples: {e}")
        return 0
