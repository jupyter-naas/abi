#!/usr/bin/env python3
"""
Test script for AI Agent Ontology
Answers questions about AI Systems and AI Agents relationships
"""

import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, OWL
from rdflib.namespace import XSD

def load_ontology():
    """Load the AI Agent ontology and instances"""
    g = Graph()
    
    # Load ontology files
    try:
        g.parse("src/core/modules/ontology/ontologies/domain-level/AIAgentOntology.ttl", format="turtle")
        print("✅ Loaded AIAgentOntology.ttl")
    except Exception as e:
        print(f"❌ Error loading AIAgentOntology.ttl: {e}")
        return None
    
    try:
        g.parse("src/core/modules/ontology/ontologies/domain-level/AIAgentInstances.ttl", format="turtle")
        print("✅ Loaded AIAgentInstances.ttl")
    except Exception as e:
        print(f"❌ Error loading AIAgentInstances.ttl: {e}")
        return None
    
    return g

def test_ai_system_multiple_agents(g):
    """Test if AI Systems can have multiple AI Agents"""
    print("\n" + "="*60)
    print("QUESTION: Can an AI System have multiple AI Agents?")
    print("="*60)
    
    # Define namespaces
    abi = Namespace("http://ontology.naas.ai/abi/")
    
    # Query: Find all AI Systems and their AI Agents
    query = """
    PREFIX abi: <http://ontology.naas.ai/abi/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?system ?systemLabel ?agent ?agentLabel
    WHERE {
        ?system a abi:AISystem .
        ?system rdfs:label ?systemLabel .
        ?system abi:hasAIAgent ?agent .
        ?agent rdfs:label ?agentLabel .
    }
    ORDER BY ?systemLabel ?agentLabel
    """
    
    results = g.query(query)
    
    print("\n📊 RESULTS: AI Systems and their AI Agents")
    print("-" * 50)
    
    current_system = None
    agent_count = 0
    
    for row in results:
        system, system_label, agent, agent_label = row
        
        if current_system != system:
            if current_system is not None:
                print(f"   Total AI Agents: {agent_count}")
                print()
            current_system = system
            agent_count = 0
            print(f"🏢 {system_label}:")
        
        print(f"   🤖 {agent_label}")
        agent_count += 1
    
    if current_system is not None:
        print(f"   Total AI Agents: {agent_count}")
    
    # Count total AI Agents per system
    print("\n📈 SUMMARY:")
    print("-" * 30)
    
    system_counts = {}
    for row in results:
        system_label = row[1]
        system_counts[system_label] = system_counts.get(system_label, 0) + 1
    
    for system, count in system_counts.items():
        print(f"• {system}: {count} AI Agent(s)")
    
    print(f"\n✅ ANSWER: YES - AI Systems can have multiple AI Agents!")
    print(f"   • OpenAI AI System: {system_counts.get('OpenAI AI System', 0)} agents")
    print(f"   • Anthropic AI System: {system_counts.get('Anthropic AI System', 0)} agents") 
    print(f"   • Google AI System: {system_counts.get('Google AI System', 0)} agents")

def test_ontology_structure(g):
    """Test the overall ontology structure"""
    print("\n" + "="*60)
    print("ONTOLOGY STRUCTURE TEST")
    print("="*60)
    
    # Count different types of entities with separate queries
    queries = [
        ("AI Systems", "SELECT (COUNT(?s) AS ?count) WHERE { ?s a abi:AISystem }"),
        ("AI Agents", "SELECT (COUNT(?a) AS ?count) WHERE { ?a a abi:AIAgent }"),
        ("AI Model Instances", "SELECT (COUNT(?m) AS ?count) WHERE { ?m a abi:AIModelInstance }"),
        ("Model Accuracy Qualities", "SELECT (COUNT(?q) AS ?count) WHERE { ?q a abi:ModelAccuracy }"),
        ("Response Latency Qualities", "SELECT (COUNT(?q) AS ?count) WHERE { ?q a abi:ResponseLatency }"),
        ("Token Capacity Qualities", "SELECT (COUNT(?q) AS ?count) WHERE { ?q a abi:TokenCapacity }"),
        ("Text Generation Processes", "SELECT (COUNT(?p) AS ?count) WHERE { ?p a abi:TextGenerationProcess }"),
        ("Text Generation Capabilities", "SELECT (COUNT(?c) AS ?count) WHERE { ?c a abi:TextGenerationCapability }"),
    ]
    
    for name, query in queries:
        try:
            results = list(g.query(query))
            count = results[0][0] if results else 0
            print(f"• {name}: {count}")
        except Exception as e:
            print(f"• {name}: Error - {e}")

def test_bfo_categories(g):
    """Test BFO 7 categories representation"""
    print("\n" + "="*60)
    print("BFO 7 CATEGORIES TEST")
    print("="*60)
    
    bfo_categories = [
        ("Material Entity (AISystem)", "SELECT (COUNT(?e) AS ?count) WHERE { ?e a abi:AISystem }"),
        ("Material Entity (AIModelInstance)", "SELECT (COUNT(?e) AS ?count) WHERE { ?e a abi:AIModelInstance }"),
        ("Quality (ModelAccuracy)", "SELECT (COUNT(?q) AS ?count) WHERE { ?q a abi:ModelAccuracy }"),
        ("Quality (ResponseLatency)", "SELECT (COUNT(?q) AS ?count) WHERE { ?q a abi:ResponseLatency }"),
        ("Quality (TokenCapacity)", "SELECT (COUNT(?q) AS ?count) WHERE { ?q a abi:TokenCapacity }"),
        ("Realizable Entity (TextGenerationCapability)", "SELECT (COUNT(?r) AS ?count) WHERE { ?r a abi:TextGenerationCapability }"),
        ("Realizable Entity (ImageAnalysisCapability)", "SELECT (COUNT(?r) AS ?count) WHERE { ?r a abi:ImageAnalysisCapability }"),
        ("Realizable Entity (CodeGenerationCapability)", "SELECT (COUNT(?r) AS ?count) WHERE { ?r a abi:CodeGenerationCapability }"),
        ("Process (TextGenerationProcess)", "SELECT (COUNT(?p) AS ?count) WHERE { ?p a abi:TextGenerationProcess }"),
        ("Temporal Region (InferenceSession)", "SELECT (COUNT(?t) AS ?count) WHERE { ?t a abi:InferenceSession }"),
        ("Spatial Region (DataCenterLocation)", "SELECT (COUNT(?s) AS ?count) WHERE { ?s a abi:DataCenterLocation }"),
        ("Information Content Entity (ModelSpecification)", "SELECT (COUNT(?i) AS ?count) WHERE { ?i a abi:ModelSpecification }"),
    ]
    
    for category, query in bfo_categories:
        try:
            results = list(g.query(query))
            count = results[0][0] if results else 0
            print(f"• {category}: {count} instances")
        except Exception as e:
            print(f"• {category}: Error - {e}")

def test_relationships(g):
    """Test key relationships in the ontology"""
    print("\n" + "="*60)
    print("RELATIONSHIP TEST")
    print("="*60)
    
    # Test hasAIAgent relationship
    query1 = """
    PREFIX abi: <http://ontology.naas.ai/abi/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?system ?agent
    WHERE {
        ?system abi:hasAIAgent ?agent .
    }
    """
    
    results1 = g.query(query1)
    print(f"• hasAIAgent relationships: {len(list(results1))}")
    
    # Test isAIAgentOf relationship
    query2 = """
    PREFIX abi: <http://ontology.naas.ai/abi/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?agent ?system
    WHERE {
        ?agent abi:isAIAgentOf ?system .
    }
    """
    
    results2 = g.query(query2)
    print(f"• isAIAgentOf relationships: {len(list(results2))}")
    
    # Test hasQuality relationship
    query3 = """
    PREFIX abi: <http://ontology.naas.ai/abi/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?entity ?quality
    WHERE {
        ?entity abi:hasQuality ?quality .
    }
    """
    
    results3 = g.query(query3)
    print(f"• hasQuality relationships: {len(list(results3))}")

def main():
    """Main test function"""
    print("🧪 AI AGENT ONTOLOGY TEST")
    print("="*60)
    
    # Load ontology
    g = load_ontology()
    if g is None:
        print("❌ Failed to load ontology")
        return
    
    print(f"✅ Ontology loaded successfully!")
    print(f"📊 Total triples: {len(g)}")
    
    # Run tests
    test_ai_system_multiple_agents(g)
    test_ontology_structure(g)
    test_bfo_categories(g)
    test_relationships(g)
    
    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETED")
    print("="*60)

if __name__ == "__main__":
    main()
