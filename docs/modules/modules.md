# ABI Modules Documentation

## What is a Module?

A module in the ABI system is a self-contained, standalone component that encapsulates related functionality. Modules are designed to be pluggable, meaning they can be added or removed from the system without modifying other parts of the codebase. Modules are now organized into two categories:

1. **Core Modules**: Located in `src/core/modules/` - These are essential modules that provide the core functionality of the ABI system.
2. **Custom Modules**: Located in `src/custom/modules/` - These are user-created modules that extend the system with additional capabilities.

This separation makes the system architecture easier to understand and maintain, with a clear distinction between core functionality and custom extensions.

Modules provide a way to organize and structure your code in a modular fashion, making it easier to maintain, extend, and reuse functionality. They can contain various components such as:

- **Agents**: AI agents that provide specific capabilities
- **Workflows**: Sequences of operations that accomplish specific tasks
- **Pipelines**: Data processing flows that transform and analyze information
- **Tests**: Unit and integration tests for the module's components

## How Modules Work

### Module Loading Process

The ABI system automatically discovers and loads modules at runtime. Here's how the process works:

1. The system scans both the `src/core/modules/` and `src/custom/modules/` directories for subdirectories
2. Each subdirectory (except `__pycache__` and those containing "disabled" in their name) is considered a module
3. The module is imported using Python's import system
4. An `IModule` instance is created for the module
5. The module's components (agents, workflows, pipelines) are loaded
6. The loaded module is added to the system's registry

This automatic loading mechanism means that you can add new functionality to the system simply by creating a new module directory with the appropriate structure in either the core or custom modules directory.

### Module Structure

A typical module has the following directory structure:

```
src/core/modules/your_core_module_name/
├── agents/           # Contains AI agents
│   └── YourAssistant.py  # An agent implementation
├── workflows/            # Contains workflow implementations
│   └── YourWorkflow.py   # A workflow implementation
├── pipelines/            # Contains pipeline implementations
│   └── YourPipeline.py   # A pipeline implementation
└── tests/                # Contains tests for the module
    └── test_module.py    # Test implementations
```

Or for custom modules:

```
src/custom/modules/your_custom_module_name/
├── agents/           # Contains AI agents
│   └── YourAssistant.py  # An agent implementation
├── workflows/            # Contains workflow implementations
│   └── YourWorkflow.py   # A workflow implementation
├── pipelines/            # Contains pipeline implementations
│   └── YourPipeline.py   # A pipeline implementation
└── tests/                # Contains tests for the module
    └── test_module.py    # Test implementations
```

### How Components Are Loaded

- **Agents**: The system looks for Python files in the `agents/` directory. Each file should contain a `create_agent()` function that returns an `Agent` instance.
- **Workflows and Pipelines**: These are made available to the system when they're imported as part of the module loading process.

## Creating a New Module

To create a new module, follow these steps:

1. Decide whether your module should be a core module or a custom module:
   - Core modules (`src/core/modules/`) are for essential system functionality
   - Custom modules (`src/custom/modules/`) are for extensions and user-specific functionality
2. Create a new directory under the appropriate path with your module name (use a descriptive name in snake_case)
3. Set up the standard directory structure (agents, workflows, pipelines, tests)
4. Implement your components following the appropriate patterns

### Step-by-Step Guide

#### 1. Create the Module Directory

For a core module:
```bash
mkdir -p src/core/modules/your_module_name/{agents,workflows,pipelines,tests}
```

For a custom module:
```bash
mkdir -p src/custom/modules/your_module_name/{agents,workflows,pipelines,tests}
```

#### 2. Create an Assistant

Create a file `src/[core|custom]/modules/your_module_name/agents/YourAssistant.py`:

```python
from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from src import secret, services

NAME = "Your Assistant Name"
DESCRIPTION = "A brief description of what your assistant does."
MODEL = "o3-mini"  # Or another appropriate model
TEMPERATURE = 1
AVATAR_URL = "https://example.com/your_assistant_avatar.png"
SYSTEM_PROMPT = """Your system prompt that defines the assistant's behavior and capabilities."""

def create_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    """Creates and returns an instance of your assistant.
    
    This function is called by the module loading system to instantiate your assistant.
    
    Args:
        agent_shared_state: Shared state for the agent
        agent_configuration: Configuration for the agent
        
    Returns:
        An instance of your assistant
    """
    # Initialize your assistant here
    # ...
    
    return your_assistant
```

#### 3. Create a Workflow

Create a file `src/[core|custom]/modules/your_module_name/workflows/YourWorkflow.py`:

```python
from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from dataclasses import dataclass
from pydantic import BaseModel, Field
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from typing import Any

@dataclass
class YourWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for your workflow."""
    # Add configuration parameters here
    pass

class YourWorkflowParameters(WorkflowParameters):
    """Parameters for your workflow execution."""
    parameter_1: str = Field(..., description="Description of parameter_1")
    parameter_2: int = Field(..., description="Description of parameter_2")

class YourWorkflow(Workflow):
    """Your workflow implementation."""
    
    def __init__(self, configuration: YourWorkflowConfiguration):
        self.__configuration = configuration
    
    def run(self, parameters: YourWorkflowParameters) -> Any:
        # Implement your workflow logic here
        return "Your result"
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [StructuredTool(
            name="your_workflow_name",
            description="Description of what your workflow does",
            func=lambda **kwargs: self.run(YourWorkflowParameters(**kwargs)),
            args_schema=YourWorkflowParameters
        )]
    
    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router."""
        @router.post("/your_endpoint")
        def run_workflow(parameters: YourWorkflowParameters):
            return self.run(parameters)
```

#### 4. Create a Pipeline

Create a file `src/[core|custom]/modules/your_module_name/pipelines/YourPipeline.py`:

```python
from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from abi.utils.Graph import ABIGraph
from rdflib import Graph
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class YourPipelineConfiguration(PipelineConfiguration):
    """Configuration for your pipeline."""
    # Add configuration parameters here
    pass

class YourPipelineParameters(PipelineParameters):
    """Parameters for your pipeline execution."""
    parameter_1: str
    parameter_2: int

class YourPipeline(Pipeline):
    """Your pipeline implementation."""
    
    def __init__(self, configuration: YourPipelineConfiguration):
        self.__configuration = configuration
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline."""
        return [StructuredTool(
            name="your_pipeline",
            description="Executes the pipeline with the given parameters",
            func=lambda **kwargs: self.run(YourPipelineParameters(**kwargs)),
            args_schema=YourPipelineParameters
        )]
    
    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router."""
        @router.post("/YourPipeline")
        def run(parameters: YourPipelineParameters):
            return self.run(parameters).serialize(format="turtle")
    
    def run(self, parameters: YourPipelineParameters) -> Graph:
        graph = ABIGraph()
        
        # Implement your pipeline logic here
        
        return graph
```

#### 5. Add Tests

Create a file `src/[core|custom]/modules/your_module_name/tests/test_module.py`:

```python
import unittest
# Import your module components
# from ..agents.YourAssistant import create_agent
# from ..workflows.YourWorkflow import YourWorkflow, YourWorkflowConfiguration
# from ..pipelines.YourPipeline import YourPipeline, YourPipelineConfiguration

class TestYourModule(unittest.TestCase):
    def test_your_assistant(self):
        # Test your assistant
        pass
    
    def test_your_workflow(self):
        # Test your workflow
        pass
    
    def test_your_pipeline(self):
        # Test your pipeline
        pass

if __name__ == "__main__":
    unittest.main()
```

## Disabling a Module

To disable a module without removing it from the codebase, simply add "disabled" to the module directory name:

```bash
# For core modules
mv src/core/modules/your_module_name src/core/modules/your_module_name_disabled

# For custom modules
mv src/custom/modules/your_module_name src/custom/modules/your_module_name_disabled
```

The system will automatically skip loading modules with "disabled" in their name.

## Best Practices

1. **Choose the right location**: Place essential system functionality in core modules and extensions in custom modules
2. **Keep modules focused**: Each module should have a clear, specific purpose
3. **Maintain independence**: Minimize dependencies between modules
4. **Document your components**: Provide clear documentation for your agents, workflows, and pipelines
5. **Write tests**: Include comprehensive tests for your module's components
6. **Follow naming conventions**: Use descriptive names for your module and its components

## Troubleshooting

If your module is not being loaded correctly, check the following:

1. Ensure your module directory is directly under either `src/core/modules/` or `src/custom/modules/`
2. Verify that your module name doesn't contain "disabled"
3. Check that your agents have a `create_agent()` function
4. Ensure your workflows and pipelines follow the correct class structure
5. Check for import errors or exceptions during the loading process

By following this guide, you should be able to create and integrate new modules into the ABI system effectively.

## Additional Resources

For a detailed, step-by-step guide on how to create a new module from scratch, see the [Creating Modules](./creating-modules.md) documentation.
