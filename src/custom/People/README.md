# People Module - Standard Operating Procedure

## Overview

The People module provides a comprehensive set of tools and workflows for managing HR and talent-related operations. This module integrates with knowledge graphs and ontology stores to enable semantic queries, talent searches, and HR-related data management.

## Directory Structure

```
src/custom/People/
├── agent/         # Agent implementations (e.g., HRAssistant)
├── analytics/     # Analytics tools for people data
├── models/        # Data models and schemas
├── pipelines/     # Data processing pipelines
├── tests/         # Module test suite
└── workflows/     # Workflow implementations (e.g., HRTalentWorkflow)
```

## Components

### 1. Agent Components

Located in the `agent/` directory, these components provide intelligent assistants for HR-related tasks:

- **HRAssistant**: AI assistant specialized in HR tasks such as talent search and personnel management

### 2. Workflow Components

Located in the `workflows/` directory, these components define reusable workflows for people-related operations:

- **HRTalentWorkflow**: Workflow for talent search, skill matching, and personnel queries

## Usage Instructions

### Setting Up the HR Talent Workflow

```python
from src.custom.People.workflows.HRTalentWorkflow import HRTalentWorkflow, HRTalentWorkflowConfiguration

# Create configuration
config = HRTalentWorkflowConfiguration()

# Initialize workflow
hr_workflow = HRTalentWorkflow(config)
```

### Finding Talent by Skills

```python
from src.custom.People.workflows.HRTalentWorkflow import TalentFinderParameters

# Define parameters
parameters = TalentFinderParameters(skill_name="Python")

# Execute talent search
results = hr_workflow.talent_finder(parameters)
```

### Using the HR Assistant

```python
from src.custom.People.agent.HRAssistant import create_hr_agent

# Create the HR agent
hr_agent = create_hr_agent()

# Invoke the agent with a query
response = hr_agent.invoke({"message": "Find employees with experience in data analysis"})
```

## API Endpoints

The HRTalentWorkflow provides the following API endpoints:

- **POST /talent-finder**: Find personnel with specific skills
- **POST /schema**: Retrieve the ontology schema
- **POST /query**: Execute custom SPARQL queries against the personnel knowledge graph

## Maintenance Procedures

### Adding New HR Workflows

1. Create a new file in the `workflows/` directory
2. Implement the workflow class extending the base `Workflow` class
3. Define required configuration and parameter classes
4. Implement the `as_tools()` and `as_api()` methods for integration

### Adding New Agent Capabilities

1. Create or modify files in the `agent/` directory
2. Follow the established pattern for agent creation
3. Update the agent README with usage examples

## Troubleshooting

Common issues and their solutions:

- **Query returns no results**: Verify that the ontology store contains the expected data
- **Schema validation errors**: Ensure all required parameters are provided in the correct format

## References

- Core API Documentation: See `/docs/api.md`
- Ontology Documentation: See `/docs/ontology/` 