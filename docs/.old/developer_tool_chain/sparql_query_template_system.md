# SPARQL Query Template System

## Overview
The TemplatableSparqlQueries system provides a declarative way to define reusable SPARQL queries in an ontology format. This approach allows for dynamic query generation and tool creation without writing extensive Python code. Instead of creating individual Python workflows for each SPARQL query that needs to accept arguments, the system automatically generates these workflows at runtime by loading query definitions from the triple store.

## How It Works

1. **Ontology Definition**: SPARQL queries and their arguments are defined in a TTL file using a specialized ontology
2. **Runtime Generation**: When ABI initializes, it loads all query definitions from the triple store
3. **Dynamic Tool Creation**: Each query is transformed into a function with proper argument validation
4. **Agent Integration**: These functions are made available as tools for the agent to use

This approach drastically reduces the need to write boilerplate code for similar query workflows, allowing developers to focus on defining the queries themselves.

## Structure

### Basic Components
1. **Query Definition**: Each query is defined as an instance of `intentMapping:TemplatableSparqlQuery`
2. **Query Arguments**: Arguments are defined as instances of `intentMapping:QueryArgument`
3. **Template Variables**: Variables in queries are defined using Jinja2 template syntax `{{ variable_name }}`

### Key Properties
- `intentMapping:intentDescription`: Describes the purpose of the query
- `intentMapping:sparqlTemplate`: Contains the actual SPARQL query template with Jinja2 syntax
- `intentMapping:hasArgument`: Links to the query's arguments
- `intentMapping:validationPattern`: Regex pattern for argument validation
- `intentMapping:validationFormat`: Human-readable format description

## How to Add a New Query

### Step 1: Define the Query in a TTL File
```turtle
intentMapping:newQueryName a intentMapping:TemplatableSparqlQuery ;
    rdfs:label "newQueryName"@en ;
    intentMapping:intentDescription "Description of what the query does" ;
    intentMapping:sparqlTemplate """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ...
        WHERE {
            ...
            FILTER(... "{{ argument_name }}" ...)
            ...
        }
    """ ;
    intentMapping:hasArgument intentMapping:newQueryArgument .
```

### Step 2: Define Arguments
```turtle
intentMapping:newQueryArgument a intentMapping:QueryArgument ;
    intentMapping:argumentName "argument_name" ;
    intentMapping:argumentDescription "Description of the argument" ;
    intentMapping:validationPattern "^[regex-pattern]$" ;
    intentMapping:validationFormat "human_readable_format" .
```

### Step 3: Ensure Your TTL File is Loaded Into the Triple Store
Your TTL file should be placed in the `ontologies` directory of your own module, not in the core intentmapping module. Make sure your TTL file is either:
- Included in the `src/your_module/ontologies` directory
- Loaded into the triple store during your module's initialization

The TTL file will be loaded into the triple store during application startup, making your queries available at runtime.

### Step 4: Register Templatable SPARQL Tools with the Agent
The intentmapping module automatically makes tools available at runtime. Add them to your agent with:

```python
from src.core.modules.intentmapping import get_tools
tools.extend(get_tools())
```

You can find the `Agent` class in `src/core/ontology/agents/OntologyAgent.py`.

## Technical Implementation Details

The system uses the following process to create query workflows at runtime:

1. The `intentmapping` module queries the triple store for all instances of `intentMapping:TemplatableSparqlQuery`
2. For each query, it gathers all associated arguments and their validation rules
3. It dynamically creates Pydantic models for argument validation based on these rules
4. It wraps each query in a `GenericWorkflow` class that handles:
   - Argument validation using the Pydantic model
   - Query templating using Jinja2
   - Execution of the SPARQL query through the triple store service
   - Returning the results
5. Each workflow exposes itself as a LangChain tool that can be used by agents

## Advanced Features

### Jinja2 Template Support
The `sparqlTemplate` property supports full Jinja2 syntax, allowing for:

```turtle
intentMapping:sparqlTemplate """
    SELECT ?item ?name
    WHERE {
        ?item rdf:type :Product ;
              :hasName ?name .
        {% if min_price %}
        ?item :hasPrice ?price .
        FILTER(?price >= {{ min_price }})
        {% endif %}
    }
"""
```

### Multiple Arguments
Queries can accept multiple arguments by linking to multiple argument definitions:

```turtle
intentMapping:hasArgument intentMapping:arg1, intentMapping:arg2, intentMapping:arg3 .
```

## Best Practices

1. **Naming Conventions**
   - Use descriptive names for queries (e.g., `searchPersonQuery`) as it will be used by the agent to select the correct query
   - Add a precise description of the query purpose as it will be used by the agent to select the correct query
   - End query names with "Query"
   - End argument names with "Arg"

2. **Validation Patterns**
   - Always include validation patterns for arguments
   - Use appropriate regex patterns for the data type
   - Include clear format descriptions

3. **Query Structure**
   - Include relevant PREFIX declarations
   - Use DISTINCT when appropriate
   - Include comments explaining query logic
   - Order results meaningfully

4. **Performance**
   - Use appropriate filters
   - Include score thresholds
   - Consider adding LIMIT clauses for large result sets

## Roadmap

### Automatic API Endpoint Generation
In upcoming releases, templatable SPARQL queries will also be automatically exposed as API endpoints:

1. **Runtime API Registration**: When the API starts, all templatable SPARQL queries will be registered as HTTP endpoints
2. **Third-Party Access**: These endpoints will be accessible to any third-party application with proper authentication
3. **Consistent Interface**: The same validation rules defined in the TTL files will be applied to API requests
4. **Documentation**: Swagger/OpenAPI documentation will be automatically generated for all query endpoints

This feature will allow you to create both agent tools and API endpoints from a single TTL definition, eliminating the need to maintain separate code paths for different interfaces to the same functionality.

