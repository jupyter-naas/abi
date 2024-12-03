from pathlib import Path
import rdflib
from typing import Dict, List
import logging
from enum import Enum

class OntologyLevel(Enum):
    TOP = "top-level"
    MID = "mid-level"
    DOMAIN = "domain-level"
    APPLICATION = "application-level"

class OntologyManager:
    def __init__(self, base_path: str = "ontology"):
        self.base_path = Path(base_path)
        self.graph = rdflib.Graph()
        self.logger = logging.getLogger(__name__)
        
        # Create hierarchical directory structure
        self.paths = {
            OntologyLevel.TOP: self.base_path / "top-level",
            OntologyLevel.MID: self.base_path / "mid-level",
            OntologyLevel.DOMAIN: self.base_path / "domain-level",
            OntologyLevel.APPLICATION: self.base_path / "application-level"
        }
        self._create_directories()
        self._load_all_ontologies()

    def _create_directories(self):
        """Create hierarchical directory structure"""
        for path in self.paths.values():
            path.mkdir(parents=True, exist_ok=True)

    def _load_all_ontologies(self):
        """Load all TTL files from all levels"""
        # Load in order: TOP -> MID -> DOMAIN -> APPLICATION
        for level in OntologyLevel:
            path = self.paths[level]
            for ttl_file in path.glob("*.ttl"):
                try:
                    self.graph.parse(str(ttl_file), format='turtle')
                    self.logger.info(f"Loaded {ttl_file.name} from {level.value}")
                except Exception as e:
                    self.logger.error(f"Failed to load {ttl_file.name}: {str(e)}")

    def get_ontologies_by_level(self, level: OntologyLevel) -> List[str]:
        """List all ontologies in a specific level"""
        path = self.paths[level]
        return [f.stem for f in path.glob("*.ttl")]

    def export_level_structure(self) -> Dict:
        """Export the current ontology level structure"""
        return {
            level.value: self.get_ontologies_by_level(level)
            for level in OntologyLevel
        }

    def query_ontology(self, sparql_query: str) -> List[Dict]:
        """Execute SPARQL query against the loaded ontologies"""
        try:
            results = self.graph.query(sparql_query)
            return [dict(row) for row in results]
        except Exception as e:
            self.logger.error(f"Query failed: {str(e)}")
            return []
