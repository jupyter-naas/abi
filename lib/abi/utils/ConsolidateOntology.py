from pathlib import Path
from rdflib import Graph, URIRef, RDFS, RDF, OWL
from abi import logger

def consolidate_ontologies() -> None:
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
    
    # Get all .ttl files recursively from both directories
    core_path = "src/core"
    custom_path = "src/custom"
    ttl_files = list(Path(core_path).rglob("*.ttl")) + list(Path(custom_path).rglob("*.ttl"))
    
    logger.info(f"Found {len(ttl_files)} ontology files")
    
    # Load each ontology file
    for ttl_file in ttl_files:
        if "tests" in str(ttl_file):
            continue
        try:
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
                
    # Create URI-label mapping
    mapping = {}
    for s, p, o in filtered.triples((None, RDFS.label, None)):
        if isinstance(s, URIRef):
            mapping[str(s)] = str(o)

    # # Save ontology schemas to TTL file
    # filtered.serialize(destination="lib/abi/utils/ontology_schemas.ttl", format="turtle")

    # # Save mapping to Python file
    # with open("lib/abi/utils/mapping.py", "w") as f:
    #     f.write("# Auto-generated mapping from URI to labels\n")
    #     f.write("mapping = {\n")
    #     for uri, label in mapping.items():
    #         f.write(f"    '{uri}': '{label}',\n")
    #     f.write("}\n")
            
    return filtered, mapping