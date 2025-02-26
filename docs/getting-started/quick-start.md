# Quick Start Guide

This guide will help you get up and running with ABI quickly.

## Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.8 or higher
- pip (Python package manager)
- Git

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/abi.git
cd abi

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials
```

## Basic Usage

1. **Initialize the ABI system**

```python
from abi import initialize_system

# Initialize the system with default configuration
abi = initialize_system()
```

2. **Run your first workflow**

```python
from src.workflows.example import ExampleWorkflow, ExampleWorkflowParameters, ExampleWorkflowConfiguration

# Create configuration
config = ExampleWorkflowConfiguration(
    # Add your configuration parameters here
)

# Initialize workflow
workflow = ExampleWorkflow(config)

# Run workflow with parameters
result = workflow.run(
    ExampleWorkflowParameters(
        parameter_1="value1",
        parameter_2=42
    )
)
print(result)
```

## Next Steps

- Check out the [Installation Guide](installation.md) for detailed installation instructions
- See the [Configuration Guide](configuration.md) to learn about customizing ABI
- Explore [Core Concepts](../concepts/architecture.md) to understand how ABI works 