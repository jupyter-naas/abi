# Demo Module

## Description

The Demo Module provides example implementations and demonstrations of core ABI framework capabilities, including multi-model agents, Python code execution workflows, and Streamlit applications.

Key Features:
- Multi-model agent comparison with different AI models
- Safe Python code execution workflow with timeout and security controls
- Streamlit web application demonstration
- Dagster data orchestration with RSS feed processing
- Example implementations for learning and development

## TL;DR

- Run the demo agent:
```bash
make chat Agent=MultiModelAgent
```
- Start Streamlit demo:
```bash
cd src/core/modules/__demo__/apps/streamlit && make run
```
- Start Dagster RSS processing:
```bash
make dagster-up
```

## Overview

### Structure

```
src/core/modules/__demo__/
├── workflows/                                     # Data processing workflows
│   └── ExecutePythonCodeWorkflow.py              # Safe Python code execution
├── agents/                                        # AI agents
│   ├── MultiModelAgent.py                        # Multi-model comparison agent
│   └── MultiModelAgent_test.py                   # Agent tests
├── apps/                                          # Applications
│   └── streamlit/                                 # Streamlit web app
│       ├── __init__.py                           # Streamlit application
│       ├── Dockerfile                            # Container configuration
│       └── Makefile                              # Build commands
└── orchestration/                                 # Data orchestration capability
    ├── __init__.py                               # Orchestration module
    └── definitions.py                            # Orchestration definitions (Dagster)
```

### Core Components

- **MultiModelAgent**: Agent that compares responses from different AI models (o3-mini, gpt-4o-mini, gpt-4-1)
- **ExecutePythonCodeWorkflow**: Safe Python code execution with timeout and import controls
- **Streamlit App**: Web-based chat interface demonstrating agent capabilities
- **Data Orchestration**: Automated RSS feed monitoring and data collection from 15+ sources using orchestration engine

## Agents

### Multi-Model Agent

An AI agent that demonstrates multi-model comparison capabilities:

1. **Model Comparison**: Uses multiple AI models to answer questions and compare responses
2. **Python Execution**: Integrates with Python code execution workflow for code analysis
3. **Response Analysis**: Compares and analyzes responses from different models
4. **Structured Output**: Presents results organized by model with pros/cons analysis

```python
from src.core.modules.__demo__.agents.MultiModelAgent import create_agent

# Create agent
agent = create_agent()

# Use agent for multi-model comparison
# The agent automatically calls multiple models and compares their responses
```

## Workflows

### Execute Python Code Workflow

A workflow for safely executing Python code with security controls:

1. **Safe Execution**: Runs code in isolated subprocess with timeout protection
2. **Import Control**: Configurable import statement restrictions
3. **Error Handling**: Comprehensive error capture and reporting
4. **Resource Management**: Automatic cleanup of temporary files
5. **Output Capture**: Captures both stdout and stderr for complete feedback

```python
from src.core.modules.__demo__.workflows.ExecutePythonCodeWorkflow import (
    ExecutePythonCodeWorkflow,
    ExecutePythonCodeWorkflowConfiguration,
    ExecutePythonCodeWorkflowParameters
)

# Configure workflow
config = ExecutePythonCodeWorkflowConfiguration(
    timeout=10,
    allow_imports=True
)

workflow = ExecutePythonCodeWorkflow(config)

# Execute code
parameters = ExecutePythonCodeWorkflowParameters(
    code="print('Hello, World!')"
)

result = workflow.execute_python_code(parameters)
print(f"Execution result: {result}")
```

## Data Orchestration

### RSS Feed Orchestration

A data orchestration pipeline that monitors RSS feeds and processes news content:

1. **RSS Monitoring**: 15 sensors monitoring feeds from tech companies, AI topics, and key personalities
2. **Data Processing**: Converts RSS entries to structured JSON with timestamp-based filenames
3. **Storage**: Saves processed data to `storage/datastore/core/modules/__demo__/rss_feed/`
4. **Scheduling**: 30-second polling intervals for real-time updates
5. **Smart Naming**: Files include timestamp, query term, and title for easy analysis

**Monitored Sources:**
- Technology: AI, LLM, Ontology, OpenAI
- Companies: Google, Meta, Microsoft, Apple, Amazon, Tesla, SpaceX, NASA, Palantir
- Personalities: Elon Musk, Donald Trump

```bash
# Start data orchestration
make dagster-up

# Check orchestration status
make dagster-status

# View orchestration web interface
open http://localhost:3000
```

## Applications

### Streamlit Demo

A web-based chat interface demonstrating agent capabilities:

1. **Interactive Chat**: Real-time conversation with AI agents
2. **Streaming Responses**: Live streaming of agent responses
3. **Session Management**: Persistent conversation history
4. **Tool Integration**: Demonstrates tool usage in conversations

```bash
# Start Streamlit app
cd src/core/modules/__demo__/apps/streamlit
make run
```

## Usage Examples

### Multi-Model Comparison

```bash
# Start multi-model agent
make chat Agent=MultiModelAgent

# Example conversation:
# "Compare the benefits of renewable vs non-renewable energy sources"
# The agent will:
# 1. Query multiple AI models
# 2. Compare their responses
# 3. Present analysis with pros/cons
```

### Python Code Execution

```python
# Execute Python code safely
code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print([fibonacci(i) for i in range(10)])
"""

result = workflow.execute_python_code(
    ExecutePythonCodeWorkflowParameters(code=code)
)
```

## Testing

### Run Tests

```bash
# Test multi-model agent
uv run python -m pytest src/core/modules/__demo__/agents/MultiModelAgent_test.py

# Test Python code execution workflow
uv run python -m pytest src/core/modules/__demo__/workflows/ExecutePythonCodeWorkflow_test.py
```

## Performance Considerations

- **Timeout Protection**: Configurable execution timeouts prevent hanging processes
- **Resource Cleanup**: Automatic cleanup of temporary files and processes
- **Memory Management**: Isolated subprocess execution prevents memory leaks
- **Error Recovery**: Graceful handling of execution errors and timeouts

## Dependencies

### Core Dependencies
- **abi**: Core ABI framework
- **langchain-openai**: OpenAI integration for multi-model support
- **streamlit**: Web application framework
- **fastapi**: API framework for workflow endpoints

### Python Libraries
- **subprocess**: Process management for code execution
- **tempfile**: Temporary file handling
- **pydantic**: Data validation and serialization
- **typing**: Type hints and annotations

## Security Features

1. **Code Isolation**: Python code runs in separate subprocess
2. **Import Control**: Configurable restrictions on import statements
3. **Timeout Protection**: Prevents infinite loops and hanging processes
4. **Resource Limits**: Automatic cleanup of temporary files
5. **Error Containment**: Isolated error handling prevents system impact

## Troubleshooting

### Common Issues

1. **Timeout Errors**: Increase timeout configuration for complex code
2. **Import Restrictions**: Enable allow_imports for code requiring external libraries
3. **Memory Issues**: Large code execution may require increased memory allocation
4. **Streamlit Issues**: Ensure proper environment setup for web application
5. **Model Access**: Verify OpenAI API key configuration for multi-model agent
