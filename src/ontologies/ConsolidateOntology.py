from pathlib import Path
from rdflib import Graph, URIRef, RDFS
from abi import logger
import json

def consolidate_ontologies(ontologies_dir: str, output_file: str, mapping_file: str) -> None:
    """Consolidate all ontology files and save URI-label mapping to Python file.
    
    Args:
        ontologies_dir (str): Path to directory containing ontology files
        output_file (str): Path where consolidated ontology will be saved
        mapping_file (str): Path where URI-label mapping Python file will be saved
    """
    # Create consolidated graph
    consolidated = Graph()
    
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
            
    # Save consolidated ontology and mapping
    try:
        consolidated.serialize(destination=output_file, format="turtle")
        logger.info(f"Saved consolidated ontology to {output_file}")
        logger.info(f"Total triples: {len(consolidated)}")
        
        # Create URI-label mapping
        mapping = {}
        for s, p, o in consolidated.triples((None, RDFS.label, None)):
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
    project_root = Path(__file__).parent.parent.parent
    ontologies_dir = project_root / "src" / "ontologies"
    output_file = ontologies_dir / "ConsolidatedOntology.ttl"
    mapping_file = ontologies_dir / "mapping.py"
    
    consolidate_ontologies(str(ontologies_dir), str(output_file), str(mapping_file))