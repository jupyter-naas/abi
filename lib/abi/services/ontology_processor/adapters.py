import logging
from pathlib import Path
from rdflib import Graph
from rdflib.exceptions import ParserError
import re

logger = logging.getLogger(__name__)

class FileSystemAdapter:
    def load_ontology(self, file_path: Path) -> Graph:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        graph = Graph()
        content = file_path.read_text(encoding='utf-8-sig')
        
        try:
            # Try parsing after basic cleaning
            cleaned_content = self._clean_ttl_content(content)
            graph.parse(data=cleaned_content, format='turtle')
            return graph
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {str(e)}")
            # Try more aggressive cleaning if basic cleaning fails
            try:
                cleaned_content = self._deep_clean_ttl(content)
                graph.parse(data=cleaned_content, format='turtle')
                return graph
            except Exception as e:
                logger.error(f"Failed to parse {file_path} even after deep cleaning: {str(e)}")
                raise

    def _clean_ttl_content(self, content: str) -> str:
        """Basic TTL cleaning"""
        lines = []
        for line in content.splitlines():
            # Remove BOM and whitespace
            line = line.strip().replace('\ufeff', '')
            
            if not line or line.startswith('#'):
                lines.append(line)
                continue
                
            # Ensure proper prefix declarations
            if line.startswith('@prefix'):
                if not line.endswith(' .'):
                    line = line.rstrip('.') + ' .'
            
            # Ensure proper spacing around dots
            elif line.endswith('.'):
                line = re.sub(r'\s+\.$', ' .', line)
            
            lines.append(line)
        
        return '\n'.join(lines)

    def _deep_clean_ttl(self, content: str) -> str:
        """More aggressive TTL cleaning for problematic files"""
        lines = []
        in_triple = False
        buffer = []
        
        for line in content.splitlines():
            line = line.strip().replace('\ufeff', '')
            
            if not line or line.startswith('#'):
                lines.append(line)
                continue
            
            # Handle prefix declarations
            if line.startswith('@prefix'):
                if in_triple:
                    lines.append(' '.join(buffer) + ' .')
                    buffer = []
                    in_triple = False
                lines.append(line if line.endswith(' .') else line.rstrip('.') + ' .')
                continue
            
            # Handle triple statements
            if line.endswith(' .'):
                if in_triple:
                    buffer.append(line.rstrip(' .'))
                    lines.append(' '.join(buffer) + ' .')
                    buffer = []
                    in_triple = False
                else:
                    lines.append(line)
            elif line.endswith(' ;'):
                buffer.append(line.rstrip(' ;'))
                in_triple = True
            else:
                buffer.append(line)
        
        # Handle any remaining buffer
        if buffer:
            lines.append(' '.join(buffer) + ' .')
        
        return '\n'.join(lines)

    def save_ontology(self, graph: Graph, output_path: Path):
        """Save the graph to a file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        graph.serialize(destination=str(output_path), format='turtle')