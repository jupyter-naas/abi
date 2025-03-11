from pathlib import Path
from rdflib import Graph, URIRef, RDFS, RDF, OWL
from abi import logger
import json

def consolidate_ontologies(ontologies_dir: str, output_file: str, mapping_file: str) -> None:
    """Consolidate all ontology files and save URI-label mapping to Python file.
    Only keeps classes, data properties, object properties, and annotation properties.
    
    Args:
        ontologies_dir (str): Path to directory containing ontology files
        output_file (str): Path where consolidated ontology will be saved
        mapping_file (str): Path where URI-label mapping Python file will be saved
    """
    # Create consolidated graph
    consolidated = Graph()
    filtered = Graph()
    
    # Set CCO prefix
    filtered.bind('cco', 'https://www.commoncoreontologies.org/')
    filtered.bind('abi', 'http://ontology.naas.ai/abi/')
    filtered.bind('bfo', 'http://purl.obolibrary.org/obo/')
    
    # Get all .ttl files recursively
    ontologies_path = Path(ontologies_dir)
    ttl_files = list(ontologies_path.rglob("*.ttl"))
    
    logger.info(f"Found {len(ttl_files)} ontology files")
    
    # Load each ontology file
    for ttl_file in ttl_files:
        if "__OntologyTemplate__" in str(ttl_file) or "ConsolidatedOntology" in str(ttl_file):
            continue
        try:
            logger.info(f"Loading {ttl_file}")
            g = Graph()
            g.parse(ttl_file, format="turtle")
            consolidated += g
        except Exception as e:
            logger.error(f"Error loading {ttl_file}: {e}")
    
    # Filter for desired types
    desired_types = {
        OWL.Class,
        OWL.DatatypeProperty,
        OWL.ObjectProperty,
        OWL.AnnotationProperty
    }
    
    # Add all triples where subject is of desired type
    for s, p, o in consolidated.triples((None, RDF.type, None)):
        if o in desired_types:
            # Add the type triple
            filtered.add((s, p, o))
            # Add all triples where this subject is involved
            for s2, p2, o2 in consolidated.triples((s, None, None)):
                filtered.add((s2, p2, o2))
            for s2, p2, o2 in consolidated.triples((None, None, s)):
                filtered.add((s2, p2, o2))
            
    # Save filtered ontology and mapping
    try:
        filtered.serialize(destination=output_file, format="turtle")
        logger.info(f"Saved filtered ontology to {output_file}")
        logger.info(f"Total triples: {len(filtered)}")
        
        # Create URI-label mapping
        mapping = {}
        for s, p, o in filtered.triples((None, RDFS.label, None)):
            if isinstance(s, URIRef):
                mapping[str(s)] = str(o)
                
        # Save mapping as Python file
        with open(mapping_file, 'w', encoding='utf-8') as f:
            f.write("MAPPING_URL_LABEL = {\n")
            for uri, label in mapping.items():
                f.write(f"    '{uri}': '{label}',\n")
            f.write("}\n")
            
        logger.info(f"Saved URI-label mapping to {mapping_file}")
        logger.info(f"Total mapped URIs: {len(mapping)}")
    except Exception as e:
        logger.error(f"Error saving files: {e}")

if __name__ == "__main__":
    # Define paths relative to project root
    ontologies_dir = Path(__file__).parent
    output_file = ontologies_dir / "ConsolidatedOntology.ttl"
    mapping_file = ontologies_dir / "mapping.py"
    
    consolidate_ontologies(str(ontologies_dir), str(output_file), str(mapping_file))