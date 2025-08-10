"""
Ontology Test Suite for ABI Modular AI Agent Ontology

This module contains comprehensive tests for validating the modular ontology structure,
cross-module relationships, and real-world AI system complexity modeling.
"""

from .test_modular_ontology import (
    load_ontology_files,
    load_process_mapping_csv,
    test_modular_ontology_structure,
    test_bfo_categories_with_csv,
    test_process_complexity_analysis,
    test_cross_module_workflows,
    test_temporal_coordination,
    test_performance_metrics,
    test_advanced_relationships,
    run_comprehensive_test_suite
)

__all__ = [
    'load_ontology_files',
    'load_process_mapping_csv', 
    'test_modular_ontology_structure',
    'test_bfo_categories_with_csv',
    'test_process_complexity_analysis',
    'test_cross_module_workflows',
    'test_temporal_coordination',
    'test_performance_metrics',
    'test_advanced_relationships',
    'run_comprehensive_test_suite'
]
