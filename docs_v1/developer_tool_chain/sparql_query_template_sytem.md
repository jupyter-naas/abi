# SPARQL Query Template System

## Overview
The TemplatableSparqlQueries system provides a declarative way to define reusable SPARQL queries in an ontology format. T
his approach allows for dynamic query generation and tool creation without writing extensive Python code.

## Structure

### Basic Components
1. **Query Definition**: Each query is defined as an instance of `intentMapping:TemplatableSparqlQuery`
2. **Query Arguments**: Arguments are defined as instances of `intentMapping:QueryArgument`
3. **Template Variables**: Variables in queries are defined using `{{ variable_name }}` syntax

### Key Properties
- `intentMapping:intentDescription`: Describes the purpose of the query
- `intentMapping:sparqlTemplate`: Contains the actual SPARQL query template
- `intentMapping:hasArgument`: Links to the query's arguments
- `intentMapping:validationPattern`: Regex pattern for argument validation
- `intentMapping:validationFormat`: Human-readable format description

## How to Add a New Query

### Step 1: Define the Query
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

### Step 3: Register tool in Agent

Add templatable SPARQL query tools to the agent by adding the following code to the `Agent` class:

```python
from src.core.modules.intentmapping import get_tools
tools.extend(get_tools())
```

You can find the `Agent` class in `src/core/modules/ontology/agents/OntologyAgent.py`.


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
