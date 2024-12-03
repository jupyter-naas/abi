import os
import logging
from pathlib import Path
from ontology_processor import OntologyProcessorService, FileSystemAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Get the project root directory
    project_root = Path(__file__).parent.parent.parent
    
    # Configure paths
    ontology_dir = project_root / "ontology" / "domain-level"
    output_dir = project_root / "ontology" / "output"
    output_file = output_dir / "combined_ontology.ttl"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get all .ttl files from the domain-level directory
    domain_files = list(ontology_dir.glob("*.ttl"))
    
    if not domain_files:
        logger.error(f"No TTL files found in {ontology_dir}")
        return

    try:
        # Initialize services
        storage = FileSystemAdapter()
        ontology_service = OntologyProcessorService(storage)

        # Process ontology files
        ontology_service.process_domain_ontology(
            domain_files=domain_files,
            output_file=output_file
        )
        logger.info(f"Successfully processed ontology files to {output_file}")
    except Exception as e:
        logger.error(f"Failed to process ontology files: {str(e)}")
        raise

if __name__ == "__main__":
    main() 