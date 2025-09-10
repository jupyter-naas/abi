# Wikidata Module

The Wikidata module provides natural language querying capabilities for the Wikidata knowledge base. It allows users to ask questions in natural language and automatically converts them to SPARQL queries that are executed against Wikidata's public SPARQL endpoint.

## Features

- **Natural Language Processing**: Convert natural language questions to SPARQL queries using GPT-4
- **SPARQL Query Execution**: Execute queries against Wikidata's public SPARQL endpoint
- **Result Enhancement**: Enrich query results with additional entity information
- **Comprehensive Coverage**: Support for various query types including people, organizations, countries, creative works, and more
- **Validation**: Built-in SPARQL query validation and error handling
- **Multiple Formats**: Support for JSON, XML, CSV, and TSV response formats

## Architecture

### Components

1. **WikidataAgent** (`agents/WikidataAgent.py`)
   - Main agent that orchestrates the natural language to SPARQL conversion and query execution
   - Integrates workflows and pipelines to provide a complete solution

2. **WikidataIntegration** (`integrations/WikidataIntegration.py`)
   - Handles communication with Wikidata's SPARQL endpoint
   - Provides entity search and information retrieval capabilities
   - Manages query formatting and result processing

3. **NaturalLanguageToSparqlWorkflow** (`workflows/NaturalLanguageToSparqlWorkflow.py`)
   - Converts natural language questions to SPARQL queries using GPT-4
   - Provides explanations of the generated queries
   - Validates query syntax

4. **WikidataQueryPipeline** (`pipelines/WikidataQueryPipeline.py`)
   - Executes SPARQL queries against Wikidata
   - Enhances results with additional entity information
   - Handles different response formats

5. **WikidataOntology** (`ontologies/WikidataOntology.ttl`)
   - Defines common Wikidata entities and properties
   - Provides mappings for natural language concepts

## Usage

### Basic Usage

```python
from src.core.modules.wikidata.agents.WikidataAgent import create_agent

# Create the Wikidata agent
agent = create_agent()

# Ask a natural language question
response = agent.invoke("Who are the Nobel Prize winners in Physics?")
```

### Direct Integration Usage

```python
from src.core.modules.wikidata.integrations.WikidataIntegration import (
    WikidataIntegration,
    WikidataIntegrationConfiguration
)

# Initialize integration
config = WikidataIntegrationConfiguration()
integration = WikidataIntegration(config)

# Execute a SPARQL query
query = """
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q5 .
  ?item wdt:P166 wd:Q38104 .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} LIMIT 10
"""

results = integration.execute_sparql_query(query)
```

### Workflow Usage

```python
from src.core.modules.wikidata.workflows.NaturalLanguageToSparqlWorkflow import (
    NaturalLanguageToSparqlWorkflow,
    NaturalLanguageToSparqlWorkflowConfiguration,
    NaturalLanguageToSparqlWorkflowParameters
)

# Initialize workflow
config = NaturalLanguageToSparqlWorkflowConfiguration(wikidata_integration=integration)
workflow = NaturalLanguageToSparqlWorkflow(config)

# Convert natural language to SPARQL
params = NaturalLanguageToSparqlWorkflowParameters(
    question="Who are the Nobel Prize winners in Physics?",
    limit=10
)

result = workflow.run(params)
print(result["sparql_query"])
```

## Examples

### Example Questions

The module can handle various types of questions:

1. **People Queries**
   - "Who are the Nobel Prize winners in Physics?"
   - "List all astronauts who have been to space"
   - "Who are the presidents of the United States?"

2. **Geographic Queries**
   - "What are the capitals of European countries?"
   - "List all cities in France with more than 100,000 inhabitants"
   - "What are the largest countries by area?"

3. **Creative Works**
   - "List all movies directed by Christopher Nolan"
   - "What books were written by Stephen King?"
   - "Show me all paintings by Pablo Picasso"

4. **Organizations**
   - "What programming languages were created by Google?"
   - "List all universities in California"
   - "What companies were founded by Elon Musk?"

### Sample SPARQL Queries

The module generates efficient SPARQL queries like:

```sparql
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>

SELECT ?item ?itemLabel ?year WHERE {
  ?item wdt:P31 wd:Q5 .
  ?item wdt:P166 wd:Q38104 .
  ?item wdt:P166 ?award .
  ?award wdt:P585 ?year .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} LIMIT 10
```

## Configuration

### Environment Variables

- `OPENAI_API_KEY`: Required for natural language to SPARQL conversion

### Integration Configuration

```python
@dataclass
class WikidataIntegrationConfiguration(IntegrationConfiguration):
    sparql_endpoint: str = "https://query.wikidata.org/sparql"
    user_agent: str = "ABI-WikidataAgent/1.0 (https://naas.ai/abi) Python/requests"
    timeout: int = 30
```

## Common Wikidata Entities and Properties

### Entities
- `Q5`: human
- `Q6256`: country
- `Q515`: city
- `Q43229`: organization
- `Q11424`: film
- `Q7725634`: literary work

### Properties
- `P31`: instance of
- `P17`: country
- `P106`: occupation
- `P569`: date of birth
- `P570`: date of death
- `P166`: award received
- `P57`: director
- `P50`: author
- `P36`: capital

## Error Handling

The module includes comprehensive error handling:

- SPARQL query validation
- Network timeout handling
- Rate limiting compliance
- Response parsing error handling
- Entity enhancement failure recovery

## Performance Considerations

- Queries are limited to prevent overwhelming the Wikidata service
- Results can be enhanced with additional entity information (optional)
- Caching could be implemented for frequently accessed entities
- Query complexity is managed through validation

## Contributing

When adding new capabilities:

1. Follow the existing patterns for agents, workflows, and pipelines
2. Add appropriate error handling and logging
3. Include comprehensive documentation
4. Test with various types of natural language questions
5. Update the ontology file with new entity types or properties

## Testing

```python
# Test the complete workflow
from src.core.modules.wikidata.agents.WikidataAgent import create_agent

agent = create_agent()
test_questions = [
    "Who are the Nobel Prize winners in Physics?",
    "What are the capitals of European countries?",
    "List all movies directed by Christopher Nolan"
]

for question in test_questions:
    response = agent.invoke(question)
    print(f"Question: {question}")
    print(f"Response: {response}")
    print("---")
```

## Dependencies

- `langchain-openai`: For natural language processing
- `requests`: For HTTP requests to Wikidata
- `rdflib`: For RDF/SPARQL handling (if needed)
- `pydantic`: For data validation
- `abi`: Core ABI framework components

## License

This module is part of the ABI framework and follows the same licensing terms. 