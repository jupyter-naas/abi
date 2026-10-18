---
sidebar_position: 6
---

# SPARQL Query Template System

## Overview
The TemplatableSparqlQueries system provides a declarative way to define reusable SPARQL queries in an ontology format. This approach allows for dynamic query generation and tool creation without writing extensive Python code. Instead of creating individual Python workflows for each SPARQL query that needs to accept arguments, the system automatically generates these workflows at runtime by loading query definitions from the triple store.

## How It Works

1. **Ontology Definition**: SPARQL queries and their arguments are defined in a TTL file using a specialized ontology
2. **Runtime Generation**: When the engine initializes, the `naas_abi_core.modules.templatablesparqlquery` module (loaded by default) reads all query definitions from the triple store's schema graph
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
@prefix intentMapping: <http://ontology.naas.ai/intentMapping/> .

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

### Step 3: Put the TTL File in Your Module
Place the file in your own module's `ontologies/` folder (the scaffold of `abi new module <name> --in-engine` already has `ontologies/queries/<Name>SparqlQueries.ttl`, with two example queries and their arguments). The engine loads every `*.ttl` under `ontologies/` into the triple store when it starts, so the queries are available once the module is loaded. Restart the engine after editing the file.

Constraints of the loader:
- A query is only loaded if it has at least one `intentMapping:hasArgument`.
- Every argument is a required string, checked against its `validationPattern` before the value goes into the template. Keep the pattern tight enough to block injection.
- The tool's name is the query's `rdfs:label`, and its description is `intentMapping:intentDescription`: the model chooses the tool from them.

### Step 4: Give the Tools to an Agent
Declare the module as a dependency, then ask it for the tools by name (leave the list empty to get them all):

```python
# my_module/__init__.py
dependencies = ModuleDependencies(
    modules=["naas_abi_core.modules.templatablesparqlquery"],
    services=[TripleStoreService],
)
```

```python
# inside an agent's New()
from my_module import ABIModule

sparql_module = ABIModule.get_instance().engine.modules[
    "naas_abi_core.modules.templatablesparqlquery"
]
tools += sparql_module.get_tools(["find_my_module_record_by_id"])
```

## Technical Implementation Details

The module creates the query workflows at runtime:

1. `TemplatableSparqlQueryLoader` queries the triple store for all instances of `intentMapping:TemplatableSparqlQuery`
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

Every argument is required, so an `{% if %}` on an optional value needs a `validationPattern` that accepts an empty string (for example `^[0-9]*$`); the agent then passes an empty value to skip the clause.

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
