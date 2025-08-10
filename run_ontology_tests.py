#!/usr/bin/env python3
"""
Simple runner script for ontology tests
Run with: python run_ontology_tests.py
"""

import sys
import os

# Add the src directory to the path so we can import the ontology tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from core.modules.ontology.tests import run_comprehensive_test_suite
    
    if __name__ == "__main__":
        success = run_comprehensive_test_suite()
        sys.exit(0 if success else 1)
        
except ImportError as e:
    print(f"❌ Error importing ontology tests: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error running ontology tests: {e}")
    sys.exit(1)
