#!/usr/bin/env python3
"""
Wikidata Module Demonstration

This script demonstrates how to use the ABI Wikidata module to:
1. Convert natural language questions to SPARQL queries
2. Execute SPARQL queries against Wikidata
3. Process and display results

Prerequisites:
- Set OPENAI_API_KEY environment variable
- Ensure network access to Wikidata
"""

import os
import sys

# Add the project root to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../.."))

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


def setup_components():
    """Initialize all Wikidata module components."""
    print("🔧 Initializing Wikidata module components...")
    
    # Initialize Wikidata integration
    integration_config = WikidataIntegrationConfiguration()
    integration = WikidataIntegration(integration_config)
    
    # Initialize natural language to SPARQL workflow
    nl_workflow_config = NaturalLanguageToSparqlWorkflowConfiguration(
        wikidata_integration=integration
    )
    nl_workflow = NaturalLanguageToSparqlWorkflow(nl_workflow_config)
    
    # Initialize query pipeline
    query_pipeline_config = WikidataQueryPipelineConfiguration(
        wikidata_integration=integration
    )
    query_pipeline = WikidataQueryPipeline(query_pipeline_config)
    
    print("✅ Components initialized successfully!")
    return integration, nl_workflow, query_pipeline


def demo_direct_sparql_query(integration: WikidataIntegration):
    """Demonstrate direct SPARQL query execution."""
    print("\n📋 Demo 1: Direct SPARQL Query Execution")
    print("=" * 50)
    
    # Example SPARQL query to find Nobel Prize winners in Physics
    query = """
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX wikibase: <http://wikiba.se/ontology#>
    PREFIX bd: <http://www.bigdata.com/rdf#>
    
    SELECT ?person ?personLabel ?year WHERE {
      ?person wdt:P31 wd:Q5 .
      ?person wdt:P166 wd:Q38104 .
      ?person wdt:P166 ?award .
      ?award wdt:P585 ?year .
      FILTER(?year >= "2010-01-01"^^xsd:dateTime)
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    } 
    ORDER BY DESC(?year)
    LIMIT 5
    """
    
    print(f"Executing SPARQL query:\n{query}")
    
    try:
        results = integration.execute_sparql_query(query)
        formatted_results = integration.format_query_results(results)
        
        print("\n✅ Query executed successfully!")
        print(f"📊 Found {len(formatted_results)} results:")
        
        for i, result in enumerate(formatted_results, 1):
            person_name = result.get("personLabel", {}).get("value", "Unknown")
            year = result.get("year", {}).get("value", "Unknown")
            print(f"  {i}. {person_name} ({year})")
            
    except Exception as e:
        print(f"❌ Error executing query: {str(e)}")


def demo_natural_language_to_sparql(nl_workflow: NaturalLanguageToSparqlWorkflow):
    """Demonstrate natural language to SPARQL conversion."""
    print("\n🗣️ Demo 2: Natural Language to SPARQL Conversion")
    print("=" * 55)
    
    test_questions = [
        "Who are the Nobel Prize winners in Physics from the last 10 years?",
        "What are the capitals of European countries?",
        "List movies directed by Christopher Nolan",
        "What programming languages were created by Google?",
    ]
    
    for question in test_questions:
        print(f"\n❓ Question: {question}")
        
        try:
            params = NaturalLanguageToSparqlWorkflowParameters(
                question=question,
                limit=5,
                include_explanations=True
            )
            
            result = nl_workflow.run(params)
            
            if result.get("is_valid"):
                print("✅ SPARQL query generated successfully!")
                print(f"📝 Generated Query:\n{result['raw_query']}")
                if result.get("explanation"):
                    print(f"💡 Explanation: {result['explanation']}")
            else:
                print(f"❌ Failed to generate valid query: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")


def demo_end_to_end_workflow(nl_workflow: NaturalLanguageToSparqlWorkflow, 
                           query_pipeline: WikidataQueryPipeline):
    """Demonstrate end-to-end natural language to results workflow."""
    print("\n🔄 Demo 3: End-to-End Natural Language Query")
    print("=" * 50)
    
    question = "Who are some famous physicists from Germany?"
    print(f"❓ Question: {question}")
    
    try:
        # Step 1: Convert natural language to SPARQL
        print("\n1️⃣ Converting to SPARQL...")
        nl_params = NaturalLanguageToSparqlWorkflowParameters(
            question=question,
            limit=5
        )
        
        sparql_result = nl_workflow.run(nl_params)
        
        if not sparql_result.get("is_valid"):
            print(f"❌ Failed to generate SPARQL: {sparql_result.get('error')}")
            return
            
        sparql_query = sparql_result["sparql_query"]
        print("✅ Generated SPARQL query")
        
        # Step 2: Execute SPARQL query
        print("\n2️⃣ Executing query against Wikidata...")
        query_params = WikidataQueryPipelineParameters(
            sparql_query=sparql_query,
            enhance_results=True
        )
        
        execution_result = query_pipeline.run(query_params)
        
        if execution_result.get("error"):
            print(f"❌ Query execution failed: {execution_result['error']}")
            return
            
        print("✅ Query executed successfully!")
        print(f"📊 Found {execution_result['result_count']} results:")
        
        # Step 3: Display results
        for i, result in enumerate(execution_result["results"], 1):
            name = "Unknown"
            description = ""
            
            # Extract name from various possible fields
            for field in ["personLabel", "itemLabel", "physicist", "person"]:
                if field in result and "value" in result[field]:
                    name = result[field]["value"]
                    break
                    
            # Look for enhanced information
            for key, value in result.items():
                if key.endswith("_info") and isinstance(value, dict):
                    description = value.get("description", "")
                    break
                    
            print(f"  {i}. {name}")
            if description:
                print(f"     📝 {description}")
                
    except Exception as e:
        print(f"❌ Error in end-to-end workflow: {str(e)}")


def demo_entity_search(integration: WikidataIntegration):
    """Demonstrate entity search capabilities."""
    print("\n🔍 Demo 4: Entity Search")
    print("=" * 30)
    
    search_terms = ["Albert Einstein", "France", "Python programming"]
    
    for term in search_terms:
        print(f"\n🔎 Searching for: {term}")
        
        try:
            results = integration.search_entities(term, limit=3)
            
            if results:
                print(f"✅ Found {len(results)} results:")
                for i, entity in enumerate(results, 1):
                    entity_id = entity.get("id", "Unknown")
                    label = entity.get("label", "Unknown")
                    description = entity.get("description", "No description")
                    print(f"  {i}. {label} ({entity_id})")
                    print(f"     📝 {description}")
            else:
                print("❌ No results found")
                
        except Exception as e:
            print(f"❌ Search error: {str(e)}")


def main():
    """Main demonstration function."""
    print("🌟 ABI Wikidata Module Demonstration")
    print("=" * 40)
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set. Natural language features will not work.")
        print("   Set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
    
    try:
        # Initialize components
        integration, nl_workflow, query_pipeline = setup_components()
        
        # Run demonstrations
        demo_direct_sparql_query(integration)
        
        if os.getenv("OPENAI_API_KEY"):
            demo_natural_language_to_sparql(nl_workflow)
            demo_end_to_end_workflow(nl_workflow, query_pipeline)
        else:
            print("\n⚠️  Skipping natural language demos (no OpenAI API key)")
        
        demo_entity_search(integration)
        
        print("\n🎉 Demonstration completed!")
        print("\nNext steps:")
        print("- Try your own questions with the Wikidata agent")
        print("- Explore the comprehensive ontology definitions")
        print("- Check out the test suite for more examples")
        
    except Exception as e:
        print(f"❌ Demo failed: {str(e)}")
        print("Check that all dependencies are installed and network is available.")


if __name__ == "__main__":
    main() 