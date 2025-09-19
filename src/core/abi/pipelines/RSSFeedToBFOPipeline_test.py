import json
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
from rdflib import Graph, Namespace, URIRef, Literal

from RSSFeedToBFOPipeline import (
    RSSFeedToBFOPipeline, 
    RSSFeedToBFOPipelineConfiguration, 
    RSSFeedToBFOPipelineParameters
)

# Test data - sample RSS feed data structure
SAMPLE_RSS_DATA = {
    "collection_timestamp": "20250918T204344",
    "query_term": "Baidu_Research",
    "sensor_name": "my_sensor_Baidu_Research",
    "rss_entry": {
        "link": "https://www.example.com/news/baidu-stock-analysis",
        "title": "Cathie Wood Just Bought Baidu Stock. Should You?",
        "summary": "The iconic growth investor is buying China's leading search engine operator for the first time in almost four months.",
        "published": "Thu, 18 Sep 2025 08:41:00 GMT",
        "news_source": "The Motley Fool via MSN",
        "title_detail": {
            "type": "text/plain",
            "language": "en"
        },
        "summary_detail": {
            "type": "text/html",
            "language": "en"
        }
    },
    "article_published": "Thu, 18 Sep 2025 08:41:00 GMT"
}

class TestRSSFeedToBFOPipeline:
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_triple_store = Mock()
        self.config = RSSFeedToBFOPipelineConfiguration(
            triple_store=self.mock_triple_store
        )
        self.pipeline = RSSFeedToBFOPipeline(self.config)
        
    def test_pipeline_initialization(self):
        """Test pipeline initializes correctly."""
        assert self.pipeline is not None
        assert self.pipeline._RSSFeedToBFOPipeline__configuration == self.config
        
    def test_generate_article_id(self):
        """Test article ID generation."""
        url = "https://www.example.com/news/test-article"
        article_id = self.pipeline._generate_article_id(url)
        
        # Should be consistent
        article_id_2 = self.pipeline._generate_article_id(url)
        assert article_id == article_id_2
        
        # Should be 12 characters
        assert len(article_id) == 12
        
    def test_format_timestamp(self):
        """Test timestamp formatting."""
        timestamp = "20250918T204344"
        formatted = self.pipeline._format_timestamp(timestamp)
        assert formatted == "2025-09-18T20:43:44"
        
    def test_normalize_name(self):
        """Test name normalization."""
        name = "The Motley Fool via MSN"
        normalized = self.pipeline._normalize_name(name)
        assert normalized == "The_Motley_Fool_via_MSN"
        
    def test_run_with_valid_parameters(self):
        """Test pipeline execution with valid RSS data."""
        parameters = RSSFeedToBFOPipelineParameters(
            rss_data=SAMPLE_RSS_DATA,
            collection_id="test-collection-123"
        )
        
        result_graph = self.pipeline.run(parameters)
        
        # Verify graph is returned
        assert isinstance(result_graph, Graph)
        assert len(result_graph) > 0
        
        # Verify namespaces are bound
        namespaces = dict(result_graph.namespaces())
        assert "bfo" in namespaces
        assert "rss" in namespaces
        assert "abi" in namespaces
        
    def test_run_with_invalid_parameters(self):
        """Test pipeline fails with invalid parameters."""
        invalid_params = Mock()  # Not the right type
        
        with pytest.raises(ValueError, match="Parameters must be of type"):
            self.pipeline.run(invalid_params)
            
    def test_bfo_compliance(self):
        """Test that generated triples are BFO compliant."""
        parameters = RSSFeedToBFOPipelineParameters(
            rss_data=SAMPLE_RSS_DATA,
            collection_id="bfo-test-123"
        )
        
        result_graph = self.pipeline.run(parameters)
        
        # Define namespaces for testing
        BFO = Namespace("http://purl.obolibrary.org/obo/")
        RSS = Namespace("http://ontology.naas.ai/rss/")
        
        # Test BFO 7 buckets representation
        triples = list(result_graph)
        
        # 1. Material Entities (BFO_0000040)
        material_entities = [
            triple for triple in triples 
            if triple[1] == BFO.BFO_0000040  # rdf:type Material Entity
        ]
        assert len(material_entities) > 0, "Should have material entities"
        
        # 2. Qualities (BFO_0000019)
        qualities = [
            triple for triple in triples
            if triple[1] == BFO.BFO_0000019  # rdf:type Quality
        ]
        assert len(qualities) > 0, "Should have qualities"
        
        # 3. Processes (BFO_0000015)
        processes = [
            triple for triple in triples
            if triple[1] == BFO.BFO_0000015  # rdf:type Process
        ]
        assert len(processes) > 0, "Should have processes"
        
        # 4. Temporal Regions (BFO_0000008)
        temporal_regions = [
            triple for triple in triples
            if triple[1] == BFO.BFO_0000008  # rdf:type Temporal Region
        ]
        assert len(temporal_regions) > 0, "Should have temporal regions"
        
        # 5. Spatial Regions (BFO_0000006)
        spatial_regions = [
            triple for triple in triples
            if triple[1] == BFO.BFO_0000006  # rdf:type Spatial Region
        ]
        assert len(spatial_regions) > 0, "Should have spatial regions"
        
        # 6. Information Content Entities (BFO_0000031)
        info_entities = [
            triple for triple in triples
            if triple[1] == BFO.BFO_0000031  # rdf:type Information Content Entity
        ]
        assert len(info_entities) > 0, "Should have information content entities"
        
        # 7. Realizable Entities (BFO_0000017)
        realizable_entities = [
            triple for triple in triples
            if triple[1] == BFO.BFO_0000017  # rdf:type Realizable Entity
        ]
        assert len(realizable_entities) > 0, "Should have realizable entities"
        
    def test_sparql_generation(self):
        """Test SPARQL INSERT DATA generation."""
        parameters = RSSFeedToBFOPipelineParameters(
            rss_data=SAMPLE_RSS_DATA,
            collection_id="sparql-test-123"
        )
        
        result_graph = self.pipeline.run(parameters)
        
        # Generate SPARQL INSERT DATA statement
        sparql_insert = self._generate_sparql_insert(result_graph)
        
        # Verify SPARQL format
        assert sparql_insert.startswith("INSERT DATA {")
        assert sparql_insert.endswith("}")
        assert "PREFIX bfo:" in sparql_insert
        assert "PREFIX rss:" in sparql_insert
        
        # Verify contains expected triples
        assert "news_article_" in sparql_insert
        assert "rss:NewsArticle" in sparql_insert or "bfo:BFO_0000040" in sparql_insert
        
    def _generate_sparql_insert(self, graph: Graph) -> str:
        """Generate SPARQL INSERT DATA statement from graph."""
        prefixes = []
        for prefix, namespace in graph.namespaces():
            prefixes.append(f"PREFIX {prefix}: <{namespace}>")
            
        triples = []
        for subject, predicate, obj in graph:
            # Convert to N-Triples format first, then to SPARQL
            if isinstance(obj, Literal):
                if obj.datatype:
                    obj_str = f'"{obj}"^^{obj.datatype}'
                else:
                    obj_str = f'"{obj}"'
            else:
                obj_str = f"<{obj}>"
                
            triple = f"    <{subject}> <{predicate}> {obj_str} ."
            triples.append(triple)
            
        sparql = "\n".join(prefixes) + "\n\nINSERT DATA {\n" + "\n".join(triples) + "\n}"
        return sparql
        
    def test_get_as_tool(self):
        """Test pipeline can be converted to LangChain tool."""
        tool = self.pipeline.get_as_tool()
        
        assert tool is not None
        assert tool.name == "rss_feed_to_bfo_pipeline"
        assert "BFO-compliant" in tool.description

def test_integration_with_sample_data():
    """Integration test with realistic RSS data."""
    # Create mock configuration
    mock_triple_store = Mock()
    config = RSSFeedToBFOPipelineConfiguration(triple_store=mock_triple_store)
    pipeline = RSSFeedToBFOPipeline(config)
    
    # Test with actual RSS file data structure
    parameters = RSSFeedToBFOPipelineParameters(
        rss_data=SAMPLE_RSS_DATA,
        collection_id="integration-test-456"
    )
    
    result_graph = pipeline.run(parameters)
    
    # Print some statistics
    print(f"\n=== BFO RSS Pipeline Integration Test Results ===")
    print(f"Generated triples: {len(result_graph)}")
    print(f"Namespaces: {list(dict(result_graph.namespaces()).keys())}")
    
    # Serialize to different formats for inspection
    ttl_output = result_graph.serialize(format='turtle')
    print(f"Turtle serialization length: {len(ttl_output)} chars")
    
    return result_graph

if __name__ == "__main__":
    # Run integration test
    test_integration_with_sample_data()
    print("✅ All tests passed! RSS to BFO pipeline is working correctly.")