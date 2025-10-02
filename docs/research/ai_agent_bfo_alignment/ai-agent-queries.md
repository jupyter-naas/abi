# AI Agent SPARQL Queries

## Overview

This document describes the templatable SPARQL queries created to query the BFO-compliant AI agent ontology. These queries enable ABI to answer questions about its own agents by directly querying the semantic knowledge graph.

## Query Ontology

All queries are defined in: `src/core/abi/ontologies/domain-level/AIAgentQueries.ttl`

## Available Queries

### 1. Get Agent Model
**Query ID:** `get_agent_model`  
**Description:** Get the AI model used by a specific agent  
**Arguments:** `agent_name` (e.g., "ChatGPT", "Claude")

**Example Questions:**
- "What model does ChatGPT use?"
- "Which model does Mistral use?"

**SPARQL Template:**
```sparql
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?agent_name ?model_id ?model_name ?owner
WHERE {
    ?agent a abi:AIAgent ;
           rdfs:label ?agent_name ;
           abi:usesModel ?model .
    
    ?model abi:hasModelId ?model_id ;
           rdfs:label ?model_name ;
           abi:hasOwner ?owner .
    
    FILTER(CONTAINS(LCASE(?agent_name), LCASE("{{ agent_name }}")))
}
```

**Returns:**
```json
{
  "agent_name": "ChatGPT",
  "model_id": "gpt-4.1",
  "model_name": "gpt-4.1",
  "owner": "openai"
}
```

### 2. Get Agent Context Window
**Query ID:** `get_agent_context_window`  
**Description:** Get the context window size for a specific agent  
**Arguments:** `agent_name`

**Example Questions:**
- "What is Gemini's context window?"
- "Context window of ChatGPT?"

**SPARQL Template:**
```sparql
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?agent_name ?context_window ?model_name
WHERE {
    ?agent a abi:AIAgent ;
           rdfs:label ?agent_name ;
           abi:usesModel ?model .
    
    ?model abi:hasContextWindow ?context_window ;
           rdfs:label ?model_name .
    
    FILTER(CONTAINS(LCASE(?agent_name), LCASE("{{ agent_name }}")))
}
```

### 3. Get Agent Objective
**Query ID:** `get_agent_objective`  
**Description:** Get the objective of a specific agent  
**Arguments:** `agent_name`

**Example Questions:**
- "What is DeepSeek's objective?"
- "What is the objective of Claude?"

**SPARQL Template:**
```sparql
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?agent_name ?objective ?role
WHERE {
    ?agent a abi:AIAgent ;
           rdfs:label ?agent_name ;
           abi:usesSystemPrompt ?prompt .
    
    ?prompt abi:hasObjective ?objective ;
            abi:hasRole ?role .
    
    FILTER(CONTAINS(LCASE(?agent_name), LCASE("{{ agent_name }}")))
}
```

### 4. Get Agent Tasks
**Query ID:** `get_agent_tasks`  
**Description:** Get the tasks that an agent can perform  
**Arguments:** `agent_name`

**Example Questions:**
- "What tasks can Claude do?"
- "What can Mistral do?"

**SPARQL Template:**
```sparql
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?agent_name ?tasks ?role
WHERE {
    ?agent a abi:AIAgent ;
           rdfs:label ?agent_name ;
           abi:usesSystemPrompt ?prompt .
    
    ?prompt abi:hasTasks ?tasks ;
            abi:hasRole ?role .
    
    FILTER(CONTAINS(LCASE(?agent_name), LCASE("{{ agent_name }}")))
}
```

### 5. Get All Agents
**Query ID:** `get_all_agents`  
**Description:** Get a list of all available AI agents with their specializations  
**Arguments:** None

**Example Questions:**
- "List all agents"
- "Show all agents"

**SPARQL Template:**
```sparql
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?agent_name ?specialization ?description
WHERE {
    ?agent a abi:AIAgent ;
           rdfs:label ?agent_name ;
           rdfs:comment ?description ;
           abi:hasSpecializedRole ?specialization .
}
ORDER BY ?agent_name
```

### 6. Compare Agent Models
**Query ID:** `compare_agent_models`  
**Description:** Compare the models and context windows of all agents  
**Arguments:** None

**Example Questions:**
- "Compare agents"
- "Compare all agent models"

**SPARQL Template:**
```sparql
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?agent_name ?model_name ?context_window ?owner
WHERE {
    ?agent a abi:AIAgent ;
           rdfs:label ?agent_name ;
           abi:usesModel ?model .
    
    ?model rdfs:label ?model_name ;
           abi:hasContextWindow ?context_window ;
           abi:hasOwner ?owner .
}
ORDER BY DESC(?context_window)
```

## Query Arguments

### agentNameArgument
```turtle
intentMapping:agentNameArgument a intentMapping:QueryArgument ;
    intentMapping:argumentName "agent_name"@en ;
    intentMapping:argumentDescription "The name of the AI agent (e.g., ChatGPT, Claude, Gemini, Mistral, DeepSeek, Grok, Perplexity)"@en ;
    intentMapping:validationPattern "^[a-zA-Z]+$"@en ;
    intentMapping:validationFormat "Agent name (letters only, e.g., 'ChatGPT', 'Claude')"@en .
```

## Integration with ABI

These queries are automatically loaded from the ontology and converted into tools at runtime by the templatable SPARQL query system.

### Tool Loading
```python
from src.core.templatablesparqlquery import get_tools

# In AbiAgent initialization
ai_agent_query_tools = [
    "get_agent_model",
    "get_agent_context_window",
    "get_agent_objective",
    "get_agent_tasks",
    "get_all_agents",
    "compare_agent_models"
]
tools.extend(get_tools(ai_agent_query_tools))
```

### Intent Mappings
```python
Intent(intent_type=IntentType.TOOL, intent_value="what model does", intent_target="get_agent_model"),
Intent(intent_type=IntentType.TOOL, intent_value="which model does", intent_target="get_agent_model"),
Intent(intent_type=IntentType.TOOL, intent_value="what is the context window", intent_target="get_agent_context_window"),
Intent(intent_type=IntentType.TOOL, intent_value="context window of", intent_target="get_agent_context_window"),
Intent(intent_type=IntentType.TOOL, intent_value="what is the objective", intent_target="get_agent_objective"),
Intent(intent_type=IntentType.TOOL, intent_value="what tasks can", intent_target="get_agent_tasks"),
Intent(intent_type=IntentType.TOOL, intent_value="list all agents", intent_target="get_all_agents"),
Intent(intent_type=IntentType.TOOL, intent_value="show all agents", intent_target="get_all_agents"),
Intent(intent_type=IntentType.TOOL, intent_value="compare agents", intent_target="compare_agent_models"),
```

## BFO Compliance

All queries respect the BFO 7-bucket ontology structure:

### Query Pattern for Models (Bucket 7: Generically Dependent Continuants)
```sparql
?agent a abi:AIAgent ;           # AI Agent (GDC)
       abi:usesModel ?model .     # links to Model (GDC)

?model abi:hasModelId ?model_id ; # Model properties
       abi:hasContextWindow ?context_window ;
       abi:hasOwner ?owner .
```

### Query Pattern for System Prompts (Bucket 7: Generically Dependent Continuants)
```sparql
?agent a abi:AIAgent ;
       abi:usesSystemPrompt ?prompt .  # links to System Prompt (GDC)

?prompt abi:hasObjective ?objective ;  # System Prompt properties
        abi:hasTasks ?tasks ;
        abi:hasRole ?role .
```

## Benefits

1. **Self-Documenting**: ABI can explain its own capabilities by querying the ontology
2. **Always Accurate**: Answers come directly from the source data (ontology instances)
3. **No Code Changes**: Add new queries by just adding TTL definitions
4. **BFO-Compliant**: All queries respect the formal ontological structure
5. **Queryable Knowledge**: The ontology becomes an executable knowledge base

## Testing

### Manual Test via Oxigraph
```bash
curl -X POST http://localhost:7878/query \
  -H "Content-Type: application/sparql-query" \
  -d 'PREFIX abi: <http://ontology.naas.ai/abi/>
SELECT (COUNT(?agent) as ?count)
WHERE {
  ?agent a abi:AIAgent .
}'
```

### Test via ABI
Once integrated, ask ABI:
- "What model does ChatGPT use?"
- "List all agents"
- "What is Claude's objective?"
- "Compare all agent models"

## Files

- **Query Definitions**: `src/core/abi/ontologies/domain-level/AIAgentQueries.ttl`
- **Query System**: `src/core/templatablesparqlquery/workflows/TemplatableSparqlQuery.py`
- **Integration**: `src/core/abi/agents/AbiAgent.py`
- **Agent Recommendation Queries**: `src/core/abi/ontologies/application-level/AgentRecommendationQueries.ttl`

## Next Steps

1. Enable all agent modules to load their ontologies (fix module loading race condition)
2. Test all queries with full agent coverage
3. Add more complex queries (e.g., find best agent for task, filter by capability)
4. Create visualization of query results

