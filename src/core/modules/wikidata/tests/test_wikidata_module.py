"""
Tests for the Wikidata module components.

This module contains tests for:
- WikidataIntegration
- NaturalLanguageToSparqlWorkflow  
- WikidataQueryPipeline
- WikidataAgent
"""

import pytest
from unittest.mock import Mock, patch
from src.core.modules.wikidata.integrations.WikidataIntegration import (
    WikidataIntegration,
    WikidataIntegrationConfiguration,
)
from src.core.modules.wikidata.workflows.NaturalLanguageToSparqlWorkflow import (
    NaturalLanguageToSparqlWorkflow,
    NaturalLanguageToSparqlWorkflowConfiguration,
    NaturalLanguageToSparqlWorkflowParameters,
)
from src.core.modules.wikidata.pipelines.WikidataQueryPipeline import (
    WikidataQueryPipeline,
    WikidataQueryPipelineConfiguration,
    WikidataQueryPipelineParameters,
)
from src.core.modules.wikidata.agents.WikidataAgent import create_agent


class TestWikidataIntegration:
    """Test cases for WikidataIntegration."""

    def setup_method(self):
        """Setup test fixtures."""
        self.config = WikidataIntegrationConfiguration()
        self.integration = WikidataIntegration(self.config)

    def test_initialization(self):
        """Test WikidataIntegration initialization."""
        assert self.integration is not None
        assert self.integration.headers["User-Agent"] == self.config.user_agent
        assert self.integration.headers["Accept"] == "application/sparql-results+json"

    def test_validate_sparql_query_valid(self):
        """Test SPARQL query validation with valid queries."""
        valid_queries = [
            "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 . }",
            "ASK { wd:Q42 wdt:P31 wd:Q5 . }",
            "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o . }",
            "DESCRIBE wd:Q42",
        ]
        
        for query in valid_queries:
            assert self.integration.validate_sparql_query(query)

    def test_validate_sparql_query_invalid(self):
        """Test SPARQL query validation with invalid queries."""
        invalid_queries = [
            "INVALID QUERY",
            "SELECT ?item",  # Missing WHERE clause
            "",
        ]
        
        for query in invalid_queries:
            assert not self.integration.validate_sparql_query(query)

    def test_get_common_prefixes(self):
        """Test getting common Wikidata prefixes."""
        prefixes = self.integration.get_common_prefixes()
        
        assert "wd" in prefixes
        assert "wdt" in prefixes
        assert "rdfs" in prefixes
        assert prefixes["wd"] == "http://www.wikidata.org/entity/"
        assert prefixes["wdt"] == "http://www.wikidata.org/prop/direct/"

    def test_build_prefixed_query(self):
        """Test building a query with prefixes."""
        query_body = "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 . }"
        prefixed_query = self.integration.build_prefixed_query(query_body)
        
        assert "PREFIX wd:" in prefixed_query
        assert "PREFIX wdt:" in prefixed_query
        assert query_body in prefixed_query

    def test_format_query_results(self):
        """Test formatting SPARQL query results."""
        raw_results = {
            "head": {"vars": ["item", "itemLabel"]},
            "results": {
                "bindings": [
                    {
                        "item": {
                            "type": "uri",
                            "value": "http://www.wikidata.org/entity/Q42"
                        },
                        "itemLabel": {
                            "type": "literal",
                            "value": "Douglas Adams",
                            "xml:lang": "en"
                        }
                    }
                ]
            }
        }
        
        formatted = self.integration.format_query_results(raw_results)
        
        assert len(formatted) == 1
        assert formatted[0]["item"]["entity_id"] == "Q42"
        assert formatted[0]["itemLabel"]["value"] == "Douglas Adams"

    @patch('requests.get')
    def test_execute_sparql_query_success(self, mock_get):
        """Test successful SPARQL query execution."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"results": {"bindings": []}}
        mock_get.return_value = mock_response
        
        query = "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 . }"
        result = self.integration.execute_sparql_query(query)
        
        assert "results" in result
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_search_entities_success(self, mock_get):
        """Test successful entity search."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "search": [
                {
                    "id": "Q42",
                    "label": "Douglas Adams",
                    "description": "English writer and humorist"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        results = self.integration.search_entities("Douglas Adams")
        
        assert len(results) == 1
        assert results[0]["id"] == "Q42"
        assert results[0]["label"] == "Douglas Adams"


class TestNaturalLanguageToSparqlWorkflow:
    """Test cases for NaturalLanguageToSparqlWorkflow."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_integration = Mock(spec=WikidataIntegration)
        self.config = NaturalLanguageToSparqlWorkflowConfiguration(
            wikidata_integration=self.mock_integration
        )
        self.workflow = NaturalLanguageToSparqlWorkflow(self.config)

    def test_initialization(self):
        """Test workflow initialization."""
        assert self.workflow is not None

    def test_build_system_prompt(self):
        """Test system prompt building."""
        prompt = self.workflow._build_system_prompt()
        
        assert "SPARQL" in prompt
        assert "Wikidata" in prompt
        assert "PREFIX" in prompt

    def test_build_user_prompt(self):
        """Test user prompt building."""
        question = "Who are the Nobel Prize winners?"
        limit = 10
        prompt = self.workflow._build_user_prompt(question, limit)
        
        assert question in prompt
        assert f"LIMIT {limit}" in prompt

    def test_parse_model_response_structured(self):
        """Test parsing structured model response."""
        response = """SPARQL_QUERY:
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q5 .
  ?item wdt:P166 wd:Q38104 .
} LIMIT 10

EXPLANATION:
This query finds all humans who received the Nobel Prize in Physics."""
        
        query, explanation = self.workflow._parse_model_response(response)
        
        assert "SELECT ?item ?itemLabel" in query
        assert "Nobel Prize" in explanation

    def test_parse_model_response_code_block(self):
        """Test parsing model response with code blocks."""
        response = """```sparql
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q5 .
} LIMIT 10
```"""
        
        query, explanation = self.workflow._parse_model_response(response)
        
        assert "SELECT ?item ?itemLabel" in query

    @patch('src.core.modules.wikidata.workflows.NaturalLanguageToSparqlWorkflow.ChatOpenAI')
    def test_run_success(self, mock_openai):
        """Test successful workflow execution."""
        # Mock the language model response
        mock_response = Mock()
        mock_response.content = """SPARQL_QUERY:
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q5 .
} LIMIT 10

EXPLANATION:
This query finds humans."""
        
        mock_model = Mock()
        mock_model.invoke.return_value = mock_response
        mock_openai.return_value = mock_model
        
        # Mock integration methods
        self.mock_integration.validate_sparql_query.return_value = True
        self.mock_integration.build_prefixed_query.return_value = "PREFIXED QUERY"
        
        params = NaturalLanguageToSparqlWorkflowParameters(
            question="Who are some people?",
            limit=10
        )
        
        result = self.workflow.run(params)
        
        assert result["is_valid"]
        assert "PREFIXED QUERY" in result["sparql_query"]
        assert result["original_question"] == "Who are some people?"

    def test_as_tools(self):
        """Test converting workflow to tools."""
        tools = self.workflow.as_tools()
        
        assert len(tools) == 1
        assert tools[0].name == "convert_natural_language_to_sparql"


class TestWikidataQueryPipeline:
    """Test cases for WikidataQueryPipeline."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_integration = Mock(spec=WikidataIntegration)
        self.config = WikidataQueryPipelineConfiguration(
            wikidata_integration=self.mock_integration
        )
        self.pipeline = WikidataQueryPipeline(self.config)

    def test_initialization(self):
        """Test pipeline initialization."""
        assert self.pipeline is not None

    def test_get_result_count(self):
        """Test getting result count from raw results."""
        raw_results = {
            "results": {
                "bindings": [{"item": {"type": "uri", "value": "Q42"}}]
            }
        }
        
        count = self.pipeline._get_result_count(raw_results, "json")
        assert count == 1

    def test_extract_metadata(self):
        """Test extracting metadata from results."""
        raw_results = {
            "head": {"vars": ["item", "itemLabel"]}
        }
        
        metadata = self.pipeline._extract_metadata(raw_results, "json")
        
        assert metadata["format"] == "json"
        assert metadata["variables"] == ["item", "itemLabel"]

    def test_run_success(self):
        """Test successful pipeline execution."""
        # Mock integration methods
        self.mock_integration.validate_sparql_query.return_value = True
        self.mock_integration.execute_sparql_query.return_value = {
            "results": {"bindings": []}
        }
        self.mock_integration.format_query_results.return_value = []
        
        params = WikidataQueryPipelineParameters(
            sparql_query="SELECT ?item WHERE { ?item wdt:P31 wd:Q5 . }"
        )
        
        result = self.pipeline.run(params)
        
        assert result["is_valid_query"]
        assert result["result_count"] == 0
        assert "results" in result

    def test_as_tools(self):
        """Test converting pipeline to tools."""
        tools = self.pipeline.as_tools()
        
        assert len(tools) == 1
        assert tools[0].name == "execute_wikidata_sparql_query"


class TestWikidataAgent:
    """Test cases for WikidataAgent."""

    @patch('src.core.modules.wikidata.agents.WikidataAgent.secret')
    def test_create_agent(self, mock_secret):
        """Test creating a Wikidata agent."""
        mock_secret.get.return_value = "test-api-key"
        
        agent = create_agent()
        
        assert agent is not None
        assert agent.name == "Wikidata"
        assert len(agent.tools) > 0  # Should have tools from workflows and pipelines


class TestIntegration:
    """Integration tests for the complete Wikidata module."""

    def setup_method(self):
        """Setup integration test fixtures."""
        self.config = WikidataIntegrationConfiguration()
        self.integration = WikidataIntegration(self.config)

    @pytest.mark.integration
    @patch('requests.get')
    def test_end_to_end_query_execution(self, mock_get):
        """Test end-to-end query execution (mocked)."""
        # Mock the SPARQL endpoint response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "head": {"vars": ["item", "itemLabel"]},
            "results": {
                "bindings": [
                    {
                        "item": {
                            "type": "uri",
                            "value": "http://www.wikidata.org/entity/Q42"
                        },
                        "itemLabel": {
                            "type": "literal",
                            "value": "Douglas Adams"
                        }
                    }
                ]
            }
        }
        mock_get.return_value = mock_response
        
        query = """
        SELECT ?item ?itemLabel WHERE {
          ?item wdt:P31 wd:Q5 .
          ?item wdt:P106 wd:Q482980 .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        } LIMIT 10
        """
        
        # Execute query
        result = self.integration.execute_sparql_query(query)
        
        # Verify result structure
        assert "head" in result
        assert "results" in result
        assert len(result["results"]["bindings"]) == 1
        
        # Format results
        formatted = self.integration.format_query_results(result)
        assert len(formatted) == 1
        assert formatted[0]["item"]["entity_id"] == "Q42"

    @pytest.mark.integration
    def test_real_wikidata_query(self):
        """Test with a real Wikidata query (optional, requires network)."""
        # This test can be skipped in CI/CD environments
        pytest.skip("Requires network access to Wikidata")
        
        query = """
        SELECT ?item ?itemLabel WHERE {
          ?item wdt:P31 wd:Q5 .
          ?item wdt:P27 wd:Q30 .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        } LIMIT 1
        """
        
        try:
            result = self.integration.execute_sparql_query(query)
            assert "results" in result
        except Exception as e:
            pytest.skip(f"Network error: {e}")


if __name__ == "__main__":
    pytest.main([__file__]) 