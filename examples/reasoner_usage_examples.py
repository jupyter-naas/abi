#!/usr/bin/env python3
"""
Examples demonstrating how to use the ReasonerService with your existing ABI system.

These examples show various use cases from basic consistency checking to
advanced ontology validation and automated reasoning integration.
"""

from abi.services.reasoner import ReasonerFactory, ReasoningType
from abi.services.reasoner.integrations.TripleStoreReasonerIntegration import TripleStoreReasonerIntegration
from abi.services.triple_store.TripleStoreService import TripleStoreService
from abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import TripleStoreService__SecondaryAdaptor__Filesystem
from rdflib import Graph, Namespace, RDF, RDFS, OWL
from rdflib.namespace import XSD
import tempfile
import os


def example_1_basic_reasoning():
    """Example 1: Basic reasoning with a simple ontology."""
    print("=== Example 1: Basic Reasoning ===")
    
    # Create a simple ontology
    g = Graph()
    ex = Namespace("http://example.org/")
    g.bind("ex", ex)
    
    # Add some classes and properties
    g.add((ex.Person, RDF.type, OWL.Class))
    g.add((ex.Student, RDF.type, OWL.Class))
    g.add((ex.Student, RDFS.subClassOf, ex.Person))
    g.add((ex.hasAge, RDF.type, OWL.DatatypeProperty))
    g.add((ex.hasAge, RDFS.domain, ex.Person))
    g.add((ex.hasAge, RDFS.range, XSD.integer))
    
    # Add an individual
    g.add((ex.john, RDF.type, ex.Student))
    g.add((ex.john, ex.hasAge, 20))
    
    print(f"Original ontology has {len(g)} triples")
    
    # Create reasoner service
    reasoner = ReasonerFactory.create_development_reasoner()
    
    # Perform reasoning
    try:
        inferred = reasoner.infer_triples(g)
        print(f"After reasoning: {len(inferred)} triples")
        print(f"New inferences: {len(inferred) - len(g)}")
        
        # Check consistency
        is_consistent = reasoner.check_consistency(g)
        print(f"Ontology is consistent: {is_consistent}")
        
    except Exception as e:
        print(f"Reasoning failed: {e}")
        print("Note: This requires owlready2 and Java runtime to be installed")


def example_2_bfo_ontology_reasoning():
    """Example 2: Reasoning with BFO-based ontology from your system."""
    print("\n=== Example 2: BFO Ontology Reasoning ===")
    
    # Load one of your existing ontologies
    g = Graph()
    try:
        # Try to load your MessageOntology
        ontology_path = "src/core/modules/ontology/ontologies/domain-level/MessageOntology.ttl"
        if os.path.exists(ontology_path):
            g.parse(ontology_path, format="turtle")
            print(f"Loaded MessageOntology with {len(g)} triples")
        else:
            print("MessageOntology not found, creating sample BFO ontology")
            # Create a sample BFO-style ontology
            bfo = Namespace("http://purl.obolibrary.org/obo/BFO_")
            ex = Namespace("http://example.org/")
            
            g.add((ex.Message, RDF.type, OWL.Class))
            g.add((ex.Message, RDFS.subClassOf, bfo["0000031"]))  # Generically Dependent Continuant
            g.add((ex.EmailMessage, RDF.type, OWL.Class))
            g.add((ex.EmailMessage, RDFS.subClassOf, ex.Message))
        
        # Create BFO-optimized reasoner
        reasoner = ReasonerFactory.create_bfo_optimized_reasoner(
            performance_profile="balanced",
            ontology_size="medium"
        )
        
        # Validate the ontology
        result = reasoner.validate_ontology(g)
        
        print(f"Validation completed in {result.reasoning_time:.2f} seconds")
        print(f"Ontology is consistent: {result.is_consistent}")
        print(f"Original triples: {len(g)}")
        print(f"Inferred triples: {len(result.inferred_graph)}")
        print(f"New inferences: {len(result.inferred_graph) - len(g)}")
        
        if result.warnings:
            print("Warnings:")
            for warning in result.warnings:
                print(f"  - {warning}")
        
        if not result.is_consistent:
            print("Inconsistencies found:")
            for inconsistency in result.inconsistencies:
                print(f"  - {inconsistency.value}")
        
    except Exception as e:
        print(f"BFO reasoning failed: {e}")
        print("Note: This requires owlready2 and Java runtime to be installed")


def example_3_triple_store_integration():
    """Example 3: Integration with TripleStoreService."""
    print("\n=== Example 3: Triple Store Integration ===")
    
    try:
        # Create temporary directory for file-based triple store
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up triple store
            file_adapter = TripleStoreService__SecondaryAdaptor__Filesystem(temp_dir)
            triple_store = TripleStoreService(file_adapter)
            
            # Set up reasoner
            reasoner = ReasonerFactory.create_development_reasoner()
            
            # Create integration
            integration = TripleStoreReasonerIntegration(
                triple_store=triple_store,
                reasoner_service=reasoner,
                auto_reasoning=True,
                reasoning_delay=1.0  # Quick response for demo
            )
            
            # Add some test data
            g = Graph()
            ex = Namespace("http://example.org/")
            g.add((ex.Person, RDF.type, OWL.Class))
            g.add((ex.Employee, RDF.type, OWL.Class))
            g.add((ex.Employee, RDFS.subClassOf, ex.Person))
            
            print("Inserting initial ontology...")
            triple_store.insert(g)
            
            # Wait a moment for auto-reasoning to trigger
            import time
            time.sleep(2)
            
            # Add an individual - this should trigger auto-reasoning
            individual_graph = Graph()
            individual_graph.add((ex.alice, RDF.type, ex.Employee))
            
            print("Adding individual (should trigger auto-reasoning)...")
            triple_store.insert(individual_graph)
            
            # Wait for reasoning to complete
            time.sleep(2)
            
            # Check final state
            final_graph = triple_store.get()
            print(f"Final triple store has {len(final_graph)} triples")
            
            # Get statistics
            stats = integration.get_integration_statistics()
            print(f"Reasoning operations: {stats['integration']['reasoning_operations']}")
            print(f"Auto inferences: {stats['integration']['auto_inferences']}")
            
            # Perform manual consistency check
            is_consistent = integration.check_ontology_consistency()
            print(f"Final consistency: {is_consistent}")
            
            # Cleanup
            integration.cleanup()
            
    except Exception as e:
        print(f"Integration example failed: {e}")


def example_4_advanced_reasoning_types():
    """Example 4: Different types of reasoning operations."""
    print("\n=== Example 4: Advanced Reasoning Types ===")
    
    # Create a more complex ontology
    g = Graph()
    ex = Namespace("http://example.org/")
    g.bind("ex", ex)
    
    # Classes with complex relationships
    g.add((ex.Animal, RDF.type, OWL.Class))
    g.add((ex.Mammal, RDF.type, OWL.Class))
    g.add((ex.Mammal, RDFS.subClassOf, ex.Animal))
    g.add((ex.Dog, RDF.type, OWL.Class))
    g.add((ex.Dog, RDFS.subClassOf, ex.Mammal))
    g.add((ex.Cat, RDF.type, OWL.Class))
    g.add((ex.Cat, RDFS.subClassOf, ex.Mammal))
    
    # Disjoint classes
    g.add((ex.Dog, OWL.disjointWith, ex.Cat))
    
    # Properties
    g.add((ex.hasOwner, RDF.type, OWL.ObjectProperty))
    g.add((ex.hasOwner, RDFS.domain, ex.Animal))
    g.add((ex.hasOwner, RDFS.range, ex.Person))
    
    # Individuals
    g.add((ex.fido, RDF.type, ex.Dog))
    g.add((ex.whiskers, RDF.type, ex.Cat))
    g.add((ex.john, RDF.type, ex.Person))
    g.add((ex.fido, ex.hasOwner, ex.john))
    
    print(f"Complex ontology has {len(g)} triples")
    
    reasoner = ReasonerFactory.create_development_reasoner()
    
    try:
        # Test different reasoning types
        reasoning_types = [
            ReasoningType.CONSISTENCY_CHECK,
            ReasoningType.CLASSIFICATION,
            ReasoningType.INSTANCE_REALIZATION,
            ReasoningType.FULL_INFERENCE
        ]
        
        for reasoning_type in reasoning_types:
            print(f"\nPerforming {reasoning_type.value}...")
            
            if reasoning_type == ReasoningType.CONSISTENCY_CHECK:
                is_consistent = reasoner.check_consistency(g)
                print(f"  Result: {'CONSISTENT' if is_consistent else 'INCONSISTENT'}")
            else:
                inferred = reasoner.infer_triples(g, reasoning_type)
                new_triples = len(inferred) - len(g)
                print(f"  New inferences: {new_triples}")
                
                if new_triples > 0:
                    print("  Sample new triples:")
                    count = 0
                    for triple in inferred:
                        if triple not in g:
                            print(f"    {triple}")
                            count += 1
                            if count >= 3:  # Show max 3 examples
                                break
        
        # Test inconsistency detection
        print("\nTesting inconsistency detection...")
        
        # Add contradictory information
        inconsistent_g = g + Graph()
        inconsistent_g.add((ex.fido, RDF.type, ex.Cat))  # fido is both Dog and Cat (disjoint!)
        
        is_consistent = reasoner.check_consistency(inconsistent_g)
        print(f"Inconsistent ontology detected: {not is_consistent}")
        
    except Exception as e:
        print(f"Advanced reasoning failed: {e}")


def example_5_performance_monitoring():
    """Example 5: Performance monitoring and cache optimization."""
    print("\n=== Example 5: Performance Monitoring ===")
    
    reasoner = ReasonerFactory.create_development_reasoner()
    
    # Create test ontology
    g = Graph()
    ex = Namespace("http://example.org/")
    
    # Add moderate complexity
    for i in range(10):
        class_uri = ex[f"Class{i}"]
        g.add((class_uri, RDF.type, OWL.Class))
        if i > 0:
            g.add((class_uri, RDFS.subClassOf, ex[f"Class{i-1}"]))
    
    print("Testing reasoning performance...")
    
    try:
        # Multiple reasoning operations to test caching
        for i in range(3):
            print(f"\nReasoning iteration {i+1}:")
            
            import time
            start_time = time.time()
            inferred = reasoner.infer_triples(g)
            end_time = time.time()
            
            print(f"  Time: {end_time - start_time:.3f} seconds")
            print(f"  Triples: {len(g)} -> {len(inferred)}")
        
        # Get performance statistics
        stats = reasoner.get_reasoning_statistics()
        print(f"\nPerformance Statistics:")
        print(f"  Total operations: {stats['total_operations']}")
        print(f"  Cache hits: {stats['cache_hits']}")
        print(f"  Cache misses: {stats['cache_misses']}")
        print(f"  Cache hit rate: {stats.get('cache_hit_rate_percent', 0):.1f}%")
        print(f"  Average reasoning time: {stats['average_reasoning_time']:.3f}s")
        
        # Test cache invalidation
        print(f"\nTesting cache invalidation...")
        result = reasoner.invalidate_reasoning_cache()
        print(f"Cache invalidation successful: {result}")
        
    except Exception as e:
        print(f"Performance monitoring failed: {e}")


def main():
    """Run all examples."""
    print("ABI Reasoner Service Examples")
    print("=" * 50)
    
    # Check if requirements are available
    try:
        import owlready2
        print("✓ Owlready2 available")
        java_available = True
    except ImportError:
        print("✗ Owlready2 not available")
        print("  Install with: pip install owlready2")
        java_available = False
    
    if java_available:
        import subprocess
        try:
            subprocess.run(["java", "-version"], capture_output=True, check=True)
            print("✓ Java runtime available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("✗ Java runtime not available")
            print("  Install Java 8+ for HermiT/Pellet reasoners")
            java_available = False
    
    print("\nRunning examples...\n")
    
    # Run examples
    example_1_basic_reasoning()
    example_2_bfo_ontology_reasoning()
    example_3_triple_store_integration()
    example_4_advanced_reasoning_types()
    example_5_performance_monitoring()
    
    print("\n" + "=" * 50)
    print("Examples completed!")
    
    if not java_available:
        print("\nNote: Some examples may have failed due to missing dependencies.")
        print("For full functionality, install:")
        print("  - pip install owlready2")
        print("  - Java 8+ runtime")


if __name__ == "__main__":
    main()
