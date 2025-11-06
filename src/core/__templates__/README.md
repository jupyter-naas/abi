# Template Module

## Overview

### Description

The Template Module serves as a reference implementation and starting point for creating new modules in the ABI system. This template demonstrates the standard structure, patterns, and conventions used across ABI modules.

This template includes:
- Agent implementation with IntentAgent pattern
- Integration class with configuration and LangChain tool support
- Pipeline for data processing and semantic transformation
- Workflow for orchestrated task execution
- Orchestration definitions for scheduled data workflows
- Ontology files for semantic data modeling
- Model configuration with airgap/cloud mode support
- Comprehensive test files for all components

### Requirements

Module-specific requirements should be documented here. The template includes a `requirements()` function in `__init__.py` that checks for necessary dependencies.

### TL;DR

To get started with a new module based on this template:

1. Copy the `__templates__` folder to create your new module
2. Rename files and classes according to your module's purpose
3. Update configuration and API keys as needed
4. Customize agents, integrations, pipelines, and workflows
5. Start chatting using this command:
```bash
make chat agent=TemplateAgent
```

### Structure

```
src/core/__templates__/

├── agents/                         
│   ├── TemplateAgent_test.py               
│   └── TemplateAgent.py          
├── integrations/                    
│   ├── TemplateIntegration_test.py          
│   └── TemplateIntegration.py     
├── pipelines/                     
│   ├── TemplatePipeline_test.py          
│   └── TemplatePipeline.py           
├── workflows/   
│   ├── TemplateWorkflow_test.py      
│   └── TemplateWorkflow.py      
├── orchestrations/
│   └── definitions.py              # Dagster orchestration definitions
├── models/                         
│   └── module_default.py         # Model configuration with airgap/cloud support
├── ontologies/                     
│   ├── TemplateOntology.ttl       # Ontology definitions
│   └── TemplateSparqlQueries.ttl  # SPARQL query templates
├── __init__.py                     # Module initialization with requirements()
└── README.md                       # This documentation
```

## Core Components

### Agents

#### Template Agent
A reference implementation of an IntentAgent that demonstrates:
- Basic agent configuration with system prompts
- Intent mapping for common queries
- Tool integration from SPARQL query templates
- Model selection based on AI_MODE (airgap/cloud)
- Standard agent structure and patterns

**Capabilities:**
- Responds to predefined intents
- Uses tools from templatablesparqlquery module
- Demonstrates proper agent initialization

**Usage:**
```bash
make chat agent=TemplateAgent
```

**Testing:**
```bash
uv run python -m pytest src/core/__templates__/agents/TemplateAgent_test.py
```

### Integrations

#### Template Integration
A reference implementation of an Integration class that demonstrates:
- Configuration pattern with dataclasses
- HTTP request handling structure
- LangChain tool conversion
- Standard integration patterns

**Key Methods:**
- `example_method()`: Example method demonstrating API interaction pattern
- `_make_request()`: Internal method for HTTP requests
- `as_tools()`: Converts integration to LangChain tools

**Configuration:**

```python
from src.core.__templates__.integrations.TemplateIntegration import (
    YourIntegration,
    YourIntegrationConfiguration
)

# Create configuration
config = YourIntegrationConfiguration(
    datastore_path="datastore/your_module"
)

# Initialize integration
integration = YourIntegration(config)
```

**Testing:**
```bash
uv run python -m pytest src/core/__templates__/integrations/TemplateIntegration_test.py
```

### Pipelines

#### Template Pipeline
A reference implementation of a Pipeline that demonstrates:
- Data transformation from integrations to semantic triples
- Triple store integration
- RDF graph construction
- LangChain tool and API endpoint generation

**Key Features:**
- Transforms raw data into RDF triples
- Stores results in triple store
- Provides tool and API interfaces

**Testing:**
```bash
uv run python -m pytest src/core/__templates__/pipelines/TemplatePipeline_test.py
```

### Workflows

#### Template Workflow
A reference implementation of a Workflow that demonstrates:
- Orchestrated task execution
- Integration with other components
- Parameter validation with Pydantic
- Tool and API endpoint generation

**Key Features:**
- Executes multi-step workflows
- Integrates with integrations and other services
- Provides tool and API interfaces

**Testing:**
```bash
uv run python -m pytest src/core/__templates__/workflows/TemplateWorkflow_test.py
```

### Orchestrations

#### Template Orchestration
A reference implementation of Dagster orchestration definitions that demonstrates:
- Scheduled data collection workflows
- Asset definitions for data processing
- Job and sensor configuration
- Code-data symmetry pattern

**Structure:**
- `definitions.py`: Contains Dagster Definitions with jobs, sensors, and assets
- Follows ABI's code-data symmetry: code in `src/core/__templates__/orchestrations/` mirrors data in `storage/datastore/core/modules/__templates__/orchestration/`

**Usage:**
Configure `DAGSTER_HOME` to point to the module's data directory:
```bash
DAGSTER_HOME=$(PWD)/storage/datastore/core/modules/__templates__/orchestration
```

### Models

#### Module Default Model
Model configuration that demonstrates:
- Airgap/cloud mode switching based on `AI_MODE` environment variable
- Model selection pattern for local vs cloud deployments
- Standard model import and configuration

**Configuration:**
- Uses `airgap_model` when `AI_MODE=airgap`
- Uses `cloud_model` otherwise
- Models are imported from core modules (e.g., `airgap_qwen`, `gpt_4_1_mini`)

### Ontologies

#### Template Ontology
Turtle file (`TemplateOntology.ttl`) that demonstrates:
- RDF ontology definitions
- Class and property definitions
- Semantic data modeling patterns

#### Template SPARQL Queries
Turtle file (`TemplateSparqlQueries.ttl`) that demonstrates:
- SPARQL query templates
- Query patterns for knowledge graph operations
- Reusable query structures

## Dependencies

### Python Libraries
- `abi.integration`: Base integration framework
- `abi.services.agent`: Agent framework (IntentAgent)
- `abi.pipeline`: Pipeline framework
- `abi.workflow`: Workflow framework
- `langchain_core`: Tool integration for AI agents
- `langchain_openai`: LangChain OpenAI integration
- `fastapi`: API router for agent endpoints
- `pydantic`: Data validation and serialization
- `rdflib`: RDF graph manipulation
- `dagster`: Data orchestration framework

### Modules

- `src.core.templatablesparqlquery`: Provides SPARQL query tools for agents
- `src.core.abi.models.airgap_qwen`: Airgap model for local deployments
- `src.core.chatgpt.models.gpt_4_1_mini`: Cloud model for cloud deployments

## Creating a New Module from This Template

1. **Copy the template:**
   ```bash
   cp -r src/core/__templates__ src/core/your_module_name
   ```

2. **Rename files and classes:**
   - Rename `Template*` files to your module name
   - Update class names from `Template*` to `YourModule*`
   - Update imports and references

3. **Customize components:**
   - Update agent system prompts and intents
   - Implement integration methods for your API/service
   - Define pipeline transformations for your data
   - Create workflow steps for your use case
   - Add orchestration assets/jobs if needed
   - Define your ontology in Turtle format

4. **Update configuration:**
   - Modify `__init__.py` requirements if needed
   - Update model selection in `models/module_default.py`
   - Configure API keys and settings

5. **Write tests:**
   - Update test files with your module name
   - Add test cases for your specific functionality

6. **Update documentation:**
   - Replace this README with module-specific documentation
   - Document your module's capabilities and usage