# Querying AI Agent Ontology Data

## Overview

ABI can now answer questions about its own AI agents by querying the ontology data stored in Oxigraph using templatable SPARQL queries.

## How It Works

1. **Ontology Data**: Each agent's concrete instance data is stored in the triplestore (models, system prompts, intent mappings)
2. **SPARQL Query Templates**: Pre-defined queries in `AIAgentQueries.ttl` use Jinja2 templates with parameters
3. **Runtime Tools**: The templatable SPARQL query system auto-generates tools from the query definitions
4. **Agent Integration**: ABI can use these tools to answer questions about agents

## Available Queries

### 1. Get Agent Model
**Question:** "What model does Mistral use?"  
**Tool:** `get_agent_model`  
**Parameters:** `agent_name` (e.g., "Mistral")  
**Returns:**
```json
{
  "agent_name": "Mistral",
  "model_id": "mistral-large-2407",
  "model_name": "mistral-large-2",
  "owner": "mistral"
}
```

### 2. Get Agent Context Window
**Question:** "What is Gemini's context window?"  
**Tool:** `get_agent_context_window`  
**Parameters:** `agent_name` (e.g., "Gemini")  
**Returns:**
```json
{
  "agent_name": "Gemini",
  "context_window": 1000000,
  "model_name": "gemini-2.0-flash"
}
```

### 3. Get Agent Objective
**Question:** "What is DeepSeek's objective?"  
**Tool:** `get_agent_objective`  
**Parameters:** `agent_name` (e.g., "DeepSeek")  
**Returns:**
```json
{
  "agent_name": "DeepSeek",
  "objective": "Provide Eastern regional context and advanced analytical reasoning",
  "role": "You are DeepSeek, an AI assistant specialized in Eastern regional context analysis and advanced reasoning."
}
```

### 4. Get Agent Tasks
**Question:** "What tasks can Claude do?"  
**Tool:** `get_agent_tasks`  
**Parameters:** `agent_name` (e.g., "Claude")  
**Returns:**
```json
{
  "agent_name": "Claude",
  "tasks": "Professional writing; Business proposals; Document creation; Constitutional AI compliance",
  "role": "You are Claude, Anthropic's AI assistant specialized in professional writing and business communication."
}
```

### 5. Get All Agents
**Question:** "List all available agents"  
**Tool:** `get_all_agents`  
**Parameters:** None  
**Returns:**
```json
[
  {
    "agent_name": "ChatGPT",
    "specialization": "Web search and Western context analysis",
    "description": "ChatGPT Agent that answers questions, generates text, provides real-time answers, analyzes images and PDFs."
  },
  {
    "agent_name": "Claude",
    "specialization": "Professional writing and constitutional AI",
    "description": "Anthropic's Claude AI agent specialized in professional writing and constitutional AI"
  },
  ...
]
```

### 6. Compare Agent Models
**Question:** "Compare all agent models"  
**Tool:** `compare_agent_models`  
**Parameters:** None  
**Returns:**
```json
[
  {
    "agent_name": "Gemini",
    "model_name": "gemini-2.0-flash",
    "context_window": 1000000,
    "owner": "google"
  },
  {
    "agent_name": "ChatGPT",
    "model_name": "gpt-4.1",
    "context_window": 1047576,
    "owner": "openai"
  },
  ...
]
```

## Integration with ABI Agent

To enable ABI to answer these questions, the tools need to be added to the agent:

```python
from src.core.templatablesparqlquery import get_tools

# In your agent initialization
class AbiAgent(IntentAgent):
    def __init__(self, ...):
        # ... other initialization ...
        
        # Add templatable SPARQL query tools
        tools.extend(get_tools())
```

## Intent Mapping Examples

Configure ABI to recognize these questions:

```python
intents = [
    Intent(
        intent_value="what model does", 
        intent_type=IntentType.TOOL, 
        intent_target="get_agent_model"
    ),
    Intent(
        intent_value="what is the context window", 
        intent_type=IntentType.TOOL, 
        intent_target="get_agent_context_window"
    ),
    Intent(
        intent_value="what is the objective", 
        intent_type=IntentType.TOOL, 
        intent_target="get_agent_objective"
    ),
    Intent(
        intent_value="what tasks can", 
        intent_type=IntentType.TOOL, 
        intent_target="get_agent_tasks"
    ),
    Intent(
        intent_value="list all agents", 
        intent_type=IntentType.TOOL, 
        intent_target="get_all_agents"
    ),
    Intent(
        intent_value="compare agents", 
        intent_type=IntentType.TOOL, 
        intent_target="compare_agent_models"
    ),
]
```

## SPARQL Query Templates

The queries are defined in `src/core/abi/ontologies/domain-level/AIAgentQueries.ttl`:

```turtle
intentMapping:getAgentModel a intentMapping:TemplatableSparqlQuery ;
    rdfs:label "get_agent_model"@en ;
    intentMapping:intentDescription "Get the AI model used by a specific agent"@en ;
    intentMapping:sparqlTemplate """
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
"""@en ;
    intentMapping:hasArgument intentMapping:agentNameArgument .
```

## Benefits

1. **Self-Documenting**: ABI can explain its own capabilities by querying the ontology
2. **Always Accurate**: Answers come directly from the source data (ontology)
3. **No Code Changes**: Add new queries by just adding TTL definitions
4. **BFO-Compliant**: All queries respect the formal ontological structure
5. **Queryable Knowledge**: The ontology becomes an executable knowledge base

## Files Created

- `src/core/abi/ontologies/domain-level/AIAgentQueries.ttl` - Query templates
- `docs/capabilities/querying_ai_agents.md` - This documentation
- `storage/datastore/ai_agents_ontology_instances.csv` - Source data for instances

## Next Steps

To activate these queries:

1. Ensure the ontology files are loaded (happens automatically on startup)
2. Add the templatable SPARQL tools to ABI agent
3. Configure intent mappings for natural language questions
4. Test queries through the agent interface

