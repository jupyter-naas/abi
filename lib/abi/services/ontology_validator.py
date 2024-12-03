from rdflib import Graph
from pathlib import Path
import sys

def validate_ttl_file(file_path: str) -> tuple[bool, str]:
    """Validate a single TTL file."""
    g = Graph()
    try:
        g.parse(file_path, format='turtle')
        return True, f"✓ {file_path} is valid"
    except Exception as e:
        return False, f"✗ {file_path} has error: {str(e)}"

def validate_all_ontologies(directory: str = "ontology/domain-level"):
    """Validate all TTL files in the specified directory."""
    path = Path(directory)
    all_valid = True
    
    for ttl_file in path.glob("*.ttl"):
        is_valid, message = validate_ttl_file(str(ttl_file))
        print(message)
        if not is_valid:
            all_valid = False
    
    return all_valid

if __name__ == "__main__":
    if not validate_all_ontologies():
        sys.exit(1) 