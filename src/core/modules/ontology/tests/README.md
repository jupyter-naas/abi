# Ontology Test Suite

This directory contains comprehensive tests for validating the ABI Modular AI Agent Ontology.

## Test Structure

- `test_modular_ontology.py` - Main test suite with comprehensive validation
- `__init__.py` - Module exports for easy importing
- `README.md` - This documentation

## Running the Tests

### Option 1: Using the runner script (Recommended)
```bash
# From project root
python run_ontology_tests.py
```

### Option 2: Direct execution
```bash
# From project root
python src/core/modules/ontology/tests/test_modular_ontology.py
```

### Option 3: Import and run programmatically
```python
from src.core.modules.ontology.tests import run_comprehensive_test_suite

success = run_comprehensive_test_suite()
```

## Test Coverage

The test suite validates:

### 1. Modular Ontology Structure
- Module-specific namespaces and instances
- Cross-module relationships and collaborations
- Agent collaboration priorities and patterns

### 2. BFO 7 Categories Validation
- Maps CSV data to BFO foundational categories
- Validates ontological rigor and completeness
- Ensures proper categorization of AI entities

### 3. Process Complexity Analysis
- Analyzes process types (MODEL_CORE, WORKFLOW, TOOL)
- Validates supporting model distributions
- Intelligence score statistics and rankings

### 4. Cross-Module Workflows
- Tests research with safety validation scenarios
- Validates multimodal content creation workflows
- Demonstrates real-world AI system complexity

### 5. Temporal Coordination
- Validates process sequences and triggers
- Tests workflow orchestration patterns
- Ensures proper temporal relationships

### 6. Performance Metrics
- Speed vs cost tradeoff analysis
- Model performance comparisons
- Optimal process identification

### 7. Advanced Relationships
- System composition and hierarchy
- Load balancing configurations
- Agent role distributions

## Data Sources

The test suite uses:
- **Base Ontology**: `AIAgentOntology.ttl`
- **Module Ontologies**: ChatGPT and Claude instances
- **CSV Data**: Granular BFO Process Mapping (62 processes)

## Expected Results

Successful test execution should show:
- ✅ 800+ total triples loaded
- ✅ Multiple module instances validated
- ✅ Cross-module collaborations identified
- ✅ 100% BFO category coverage
- ✅ Performance metrics optimized
- ✅ Advanced relationships demonstrated

## Troubleshooting

### Import Errors
- Ensure you're running from the project root directory
- Check that all ontology files exist and are valid Turtle syntax
- Verify CSV file path is correct

### Ontology Loading Errors
- Check Turtle syntax in ontology files
- Ensure all prefixes are properly defined
- Validate RDF/OWL structure

### CSV Data Issues
- Verify CSV file exists and is readable
- Check column names match expected format
- Ensure numeric data is properly formatted

## Contributing

When adding new tests:
1. Follow the existing function naming pattern
2. Add comprehensive error handling
3. Include descriptive output and metrics
4. Update the `__init__.py` exports
5. Document new test coverage in this README
