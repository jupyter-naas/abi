# Templatable SPARQL Query Module

## Overview

### Description

The Templatable SPARQL Query Module provides a dynamic system for creating reusable SPARQL queries through ontology-based definitions. This module enables developers to define SPARQL query templates in RDF/TTL format with arguments and validation patterns, which are then automatically converted into executable workflows and tools at runtime.

This module enables:
- Dynamic SPARQL query generation from ontology definitions
- Automatic argument validation using regex patterns and formats
- Runtime tool creation for AI agents without writing Python boilerplate
- Template-based query execution using Jinja2 syntax
- Integration with knowledge graphs and triple stores

### Requirements

Triple Store Setup:
1. Ensure you have a running triple store service configured in your ABI instance
2. The module uses `services.triple_store_service` to query ontology definitions

### TL;DR

To get started with the Templatable SPARQL Query module:

1. Define your SPARQL queries in TTL format using the provided ontology
2. Load the TTL file into your triple store
3. The module automatically creates tools from your query definitions

Access tools using:
```python
from src.core.modules.templatablesparqlquery import get_tools
tools = get_tools()
```

### Structure

```
src/core/modules/templatablesparqlquery/

├── ontologies/                         
│   └── TemplatableSparqlQueryOntology.ttl
├── workflows/                     
│   ├── GenericWorkflow.py          
│   └── TemplatableSparqlQuery.py           
└── README.md                       
```

## Core Components

The module provides a declarative approach to SPARQL query definition and execution through ontology-based configuration.

### Workflows

#### Templatable SPARQL Query Workflow
Dynamically loads query definitions from the triple store and creates executable workflows with proper argument validation and Jinja2 template rendering.

**Capabilities:**
- Loads query definitions from triple store using SPARQL
- Creates Pydantic models for argument validation
- Renders SPARQL templates with user parameters
- Executes queries against the triple store
- Returns formatted results

**Use Cases:**
- Dynamic query generation without hardcoded Python workflows
- Reusable query templates with parameter validation
- AI agent tool creation from ontology definitions

#### Generic Workflow
A generic wrapper class that handles the execution of templated SPARQL queries with type-safe argument validation.

**Configuration:**

```python
from src.core.modules.templatablesparqlquery.workflows.GenericWorkflow import GenericWorkflow
from pydantic import BaseModel, Field

# Define argument model
class MyQueryArguments(BaseModel):
    department_id: str = Field(..., description="Department identifier", pattern="^[A-Z0-9]{3,}$")
    employee_name: str = Field(..., description="Employee name filter")

# Create workflow
workflow = GenericWorkflow[MyQueryArguments](
    name="find_employees",
    description="Find employees in a department",
    sparql_template=sparql_query_template,
    arguments_model=MyQueryArguments
)
```

#### Run
Execute workflows by calling the module's tool loading functions:
```python
from src.core.modules.templatablesparqlquery import get_tools
tools = get_tools()
# Tools are automatically created from ontology definitions
```

#### Testing
Currently no dedicated test files are present in the module structure.

### Ontologies

#### Templatable SPARQL Query Ontology

The core ontology defining the structure for templatable SPARQL queries and their arguments:

**Key Classes:**
- `abi:TemplatableSparqlQuery`: Represents a SPARQL query template with intent information
- `abi:QueryArgument`: Represents an argument for query templating

**Key Properties:**
- `abi:intentDescription`: Natural language description of query purpose
- `abi:sparqlTemplate`: The SPARQL query template with Jinja2 variables
- `abi:hasArgument`: Links queries to their arguments
- `abi:argumentName`: Argument name used in templates
- `abi:validationPattern`: Regex pattern for argument validation
- `abi:validationFormat`: Expected format description

#### Example Query Definition

```turtle
@prefix abi: <http://ontology.naas.ai/abi/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

abi:findEmployeesQuery a abi:TemplatableSparqlQuery ;
    rdfs:label "Find Employees"@en ;
    abi:intentDescription "Find all employees working in a specific department" ;
    abi:sparqlTemplate """
        SELECT ?employee ?name
        WHERE {
            ?employee :worksIn :{{ department_id }} ;
                    :hasName ?name .
            {% if employee_name %}
            FILTER(CONTAINS(LCASE(?name), LCASE("{{ employee_name }}")))
            {% endif %}
        }
    """ ;
    abi:hasArgument abi:departmentArg .

abi:departmentArg a abi:QueryArgument ;
    abi:argumentName "department_id" ;
    abi:argumentDescription "The unique identifier of the department" ;
    abi:validationPattern "^[A-Z0-9]{3,}$" ;
    abi:validationFormat "department_id" .
```

## How to Add New Queries

### Step 1: Define Query in TTL Format
Create or update a TTL file with your query definition using the templatable SPARQL query ontology.

### Step 2: Define Arguments
Specify all required arguments with proper validation patterns and descriptions.

### Step 3: Load into Triple Store
Ensure your TTL file is loaded into the triple store during application initialization.

### Step 4: Access Generated Tools
The module automatically creates tools from your definitions:

```python
from src.core.modules.templatablesparqlquery import get_tools
tools = get_tools()
```

## Dependencies

### Python Libraries
- `pydantic`: Data validation and serialization for argument models
- `rdflib`: RDF graph processing and SPARQL query execution
- `jinja2`: Template rendering for SPARQL queries
- `langchain_core`: Tool integration for AI agents
- `asyncio`: Asynchronous processing support

### Internal Modules
- `abi.utils.SPARQL`: SPARQL result processing utilities
- `src.services`: Triple store service integration

### External Services
- **Triple Store**: Required for storing and querying ontology definitions
- **Knowledge Graph**: Source data for SPARQL query execution

## Technical Implementation

The module uses a sophisticated runtime generation process:

1. **Query Discovery**: Scans the triple store for `TemplatableSparqlQuery` instances
2. **Argument Resolution**: Retrieves associated `QueryArgument` definitions
3. **Model Generation**: Creates Pydantic models with validation patterns
4. **Tool Creation**: Generates LangChain tools for AI agent integration
5. **Template Execution**: Uses Jinja2 to render SPARQL templates with parameters

This approach eliminates the need for writing repetitive Python code for similar query patterns, allowing developers to focus on query logic and ontology design.
