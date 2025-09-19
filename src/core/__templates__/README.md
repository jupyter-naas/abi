# Template Module

## Overview

### Description

The Template Module provides comprehensive integration with Perplexity AI's search and question-answering capabilities. 

This module enables:
- Capability 1
- Capibility 2
- Capability 3
- Capability 4
- Capability 5

### Requirements

API Key Setup:
1. Obtain an API key from [Tool](https://www.linktoapikey.com/)
2. Configure your `YOUR_API_KEY` in your .env file

### TL;DR

To get started with the X module:

1. Obtain an API key from [Tool](https://www.linktoapikey.com/)
2. Configure your `YOUR_API_KEY` in your .env file

Start chatting using this command:
```bash
make chat agent=Agent
```

### Structure

```
src/core/module_name/

├── agents/                         
│   ├── ModuleAgent_test.py               
│   └── ModuleAgent.py          
├── integrations/                    
│   ├── ModuleIntegration_test.py          
│   └── ModuleIntegration.py     
├── pipelines/                     
│   ├── ModulePipeline_test.py          
│   └── ModulePipeline.py           
├── models/                         
│   ├── model_name.py                
│   └── model_name2.py                
├── ontologies/                     
│   ├── ModuleOntology.py            
│   └── ModuleSparqlQueries.py                          
├── workflows/   
│   │── ModuleSparqlQueries_test.py                      
│   │── ModuleWorkflow_test.py      
│   └── ModuleWorkflow.py      
└── README.md                       
```

## Core Components
Concise list of available components with capabilities.

### Agents

#### Module Agent
Description + Capabilities + Command + Use Cases

#### Testing
Command to run test + list of test description
```bash
uv run python -m pytest src/core/module_name/agents/ModuleAgent_test.py
```

### Integrations

#### Module Integration
Description + List of functions

##### Configuration

```python
from src.custom.perplexity.integrations.PerplexityIntegration import (
    PerplexityIntegration,
    PerplexityIntegrationConfiguration
)

# Create configuration
config = PerplexityIntegrationConfiguration(
    api_key="your_api_key_here"
)

# Initialize integration
integration = PerplexityIntegration(config)
```

#### Run
Command to run integration with list of required parameters
```bash
uv run python -m pytest src/core/module_name/agents/ModuleAgent_test.py
```

#### Testing
Command to run test + list of test description
```bash
uv run python -m pytest src/core/module_name/agents/ModuleAgent_test.py
```
### Models
List of models used to run the agent

### Ontologies

#### Module Ontology

Ontology associated to module and use in pipeline and SPARQL queries

#### Module Sparql Queries

Turtle file storing SPARQL queries to be used by agent

### Pipelines
Same as integrations

### Workflows
Same as integrations

## Dependencies

### Python Libraries
- `abi.integration`: Base integration framework
- `abi.services.agent`: Agent framework
- `langchain_core`: Tool integration for AI agents
- `langchain_openai`: LangChain OpenAI integration
- `fastapi`: API router for agent endpoints
- `pydantic`: Data validation and serialization
- `requests`: HTTP client for API calls

### Modules

- `module`: Integration used ...