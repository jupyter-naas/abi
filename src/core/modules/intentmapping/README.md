# Intent Mapping Module

## Description

The Intent Mapping Module provides a framework for dynamically creating SPARQL query workflows based on ontological definitions. It enables the creation of templatable SPARQL queries with parameterized arguments, validation patterns, and intent descriptions.

Key Features:
- Dynamic workflow generation from ontological SPARQL query definitions
- Parameter validation with regex patterns and format specifications
- Jinja2 templating for SPARQL query parameterization
- Integration with ABI framework tools and workflows
- RDF-based query and argument definitions

## TL;DR

```python
from src.core.modules.intentmapping import get_tools

# Get all available intent mapping tools
tools = get_tools()

# Use specific tools by name
specific_tools = get_tools(["findEmployeesQuery", "getDepartmentInfo"])
```

## Overview

### Structure

```
src/core/modules/intentmapping/
├── __init__.py                                    # Module initialization and tool loading
├── GenericWorkflow.py                             # Generic workflow implementation
├── TemplatableSparqlQuery.py                      # SPARQL query templating logic
├── ontologies/                                    # RDF ontology definitions
│   └── IntentSparql.ttl                          # Intent mapping ontology
└── README.md                                      # This documentation
```

### Core Components

- **GenericWorkflow**: Generic workflow class that handles SPARQL query execution with parameter validation
- **TemplatableSparqlQuery**: Core logic for loading and processing templatable SPARQL queries from RDF store
- **IntentSparql Ontology**: RDF ontology defining the structure for templatable queries and arguments

## Workflows

### Generic Workflow

A generic workflow implementation that dynamically creates SPARQL query execution workflows:

1. **Dynamic Model Creation**: Generates Pydantic models based on ontological argument definitions
2. **Parameter Validation**: Validates input parameters using regex patterns and format specifications
3. **Template Rendering**: Uses Jinja2 templating to render SPARQL queries with parameters
4. **Query Execution**: Executes SPARQL queries against the triple store service
5. **Result Processing**: Converts SPARQL results to structured lists

```python
from src.core.modules.intentmapping.GenericWorkflow import GenericWorkflow

# Workflow is automatically created with validated parameters
# and integrated into the ABI tool system
```

## Ontology Structure

### TemplatableSparqlQuery

Defines the structure for templatable SPARQL queries:

- **intentDescription**: Natural language description of the query's purpose
- **sparqlTemplate**: Jinja2 template with SPARQL query and parameter placeholders
- **hasArgument**: Links to QueryArgument instances

### QueryArgument

Defines the structure for query parameters:

- **argumentName**: Parameter name used in the template
- **argumentDescription**: Description of what the argument represents
- **validationPattern**: Regex pattern for parameter validation
- **validationFormat**: Expected format (e.g., date, number, URI)

## Usage Examples

### Loading Tools

```python
from src.core.modules.intentmapping import get_tools

# Get all available tools
all_tools = get_tools()

# Get specific tools by name
employee_tools = get_tools(["findEmployeesQuery", "getEmployeeDetails"])
```

### Using Generated Tools

```python
# Tools are automatically available as LangChain StructuredTools
# with proper parameter validation and documentation

# Example: Using a generated tool
result = findEmployeesQuery.run({
    "department_id": "engineering",
    "employee_name": "john"
})
```

## Configuration

### Ontology Setup

1. **Define Queries**: Add TemplatableSparqlQuery instances to your RDF store
2. **Define Arguments**: Create QueryArgument instances with validation patterns
3. **Link Arguments**: Connect queries to their required arguments using hasArgument

### Example Ontology Entry

```turtle
intentMapping:findEmployeesQuery a intentMapping:TemplatableSparqlQuery ;
    rdfs:label "findEmployeesQuery"@en ;
    intentMapping:intentDescription "Find employees in a department with optional name filter" ;
    intentMapping:sparqlTemplate """
        SELECT ?employee ?name
        WHERE {
            ?employee :worksIn :{{ department_id }} ;
                    :hasName ?name .
            {% if employee_name %}
            FILTER(CONTAINS(LCASE(?name), LCASE("{{ employee_name }}")))
            {% endif %}
        }
    """ ;
    intentMapping:hasArgument intentMapping:departmentArg, intentMapping:nameArg .
```

## Dependencies

### Core Dependencies
- **abi**: Core ABI framework
- **rdflib**: RDF processing and SPARQL support
- **pydantic**: Data validation and model generation
- **jinja2**: Template rendering for SPARQL queries
- **langchain-core**: Tool integration

### Python Libraries
- **asyncio**: Asynchronous processing support
- **typing**: Type hints and generic support

## Security Features

1. **Parameter Validation**: Regex-based validation of all input parameters
2. **Template Safety**: Jinja2 templating with controlled variable access
3. **Query Isolation**: SPARQL queries run through controlled service interface
4. **Error Handling**: Comprehensive error capture and reporting

## Troubleshooting

### Common Issues

1. **Missing Ontology**: Ensure IntentSparql.ttl is loaded in your triple store
2. **Validation Errors**: Check regex patterns and format specifications in ontology
3. **Template Errors**: Verify Jinja2 syntax in sparqlTemplate definitions
4. **Service Connection**: Ensure triple store service is properly configured
5. **Parameter Mismatch**: Verify argument names match template placeholders
