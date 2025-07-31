# Modules

Modules are the building blocks of the ABI system, providing specific functionality and capabilities. They can include agents, integrations, pipelines, workflows, and other components.

## Core Models

The ABI system includes several pre-built core AI models available in `src/core/modules/`:

### Available Models

| Module | Provider | Model | Description | API Key Required |
|--------|----------|-------|-------------|------------------|
| `openai_gpt_4o` | OpenAI | GPT-4o | Advanced reasoning and general tasks | `OPENAI_API_KEY` |
| `anthropic_claude_3_5_sonnet` | Anthropic | Claude 3.5 Sonnet | Best-in-class reasoning and analysis | `ANTHROPIC_API_KEY` |
| `google_gemini_2_0_flash` | Google | Gemini 2.0 Flash | Fast multimodal model | `GOOGLE_API_KEY` |
| `meta_llama_3_3_70b` | Meta | Llama 3.3 70B | Open-source instruction-following | `OPENAI_API_KEY` |
| `mistral_mistral_large_2` | Mistral | Mistral Large 2 | Enhanced code and math capabilities | `MISTRAL_API_KEY` |
| `perplexity_sonar` | Perplexity | Sonar | Real-time web search integration | Custom integration |

### Usage

Each core model provides both a model configuration and an agent implementation:

```python
# Import a model
from src.core.modules.anthropic_claude_3_5_sonnet.models.anthropic_claude_3_5_sonnet import model

# Import an agent
from src.core.modules.anthropic_claude_3_5_sonnet.agents.anthropic_claude_3_5_sonnet import create_agent

# Create and use the agent
agent = create_agent()
```

### API Keys Setup

Configure the required API keys in your `.env` file:

```bash
# Required for OpenAI GPT-4o and Meta Llama models
OPENAI_API_KEY=your_openai_api_key

# Required for Anthropic Claude models
ANTHROPIC_API_KEY=your_anthropic_api_key

# Required for Google Gemini models
GOOGLE_API_KEY=your_google_api_key

# Required for Mistral models
MISTRAL_API_KEY=your_mistral_api_key
```

## What is a Module?

A module in the ABI system is a self-contained, standalone component that encapsulates related functionality. Modules are designed to be pluggable, meaning they can be added or removed from the system without modifying other parts of the codebase. Modules are now organized into two categories:

1. **Core Modules**: Located in `src/core/modules/` - These are essential modules that provide the core functionality of the ABI system.
2. **Custom Modules**: Located in `src/custom/modules/` - These are user-created modules that extend the system with additional capabilities.

This separation makes the system architecture easier to understand and maintain, with a clear distinction between core functionality and custom extensions.

Modules provide a way to organize and structure your code in a modular fashion, making it easier to maintain, extend, and reuse functionality. They can contain various components such as:

- **Agents**: AI agents that provide specific capabilities
- **Workflows**: Sequences of operations that accomplish specific tasks
- **Pipelines**: Data processing flows that transform and analyze information
- **Ontologies**: Definitions of concepts and relationships in the domain
- **Integrations**: APIs and services that provide data and functionality
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
src/[core|custom]/modules/your_module_name/
├── agents/                  # Contains AI agents
│   └── YourAgent.py         # An agent implementation
├── integrations/            # Contains integration implementations
│   └── YourIntegration.py   # An integration implementation
├── ontologies/              # Contains ontology implementations
│   └── YourOntology.py      # An ontology implementation
├── pipelines/               # Contains pipeline implementations
│   └── YourPipeline.py      # A pipeline implementation
├── workflows/               # Contains workflow implementations
│   └── YourWorkflow.py      # A workflow implementation
└── tests/                   # Contains tests for the module
    └── test_module.py       # Test implementations
```

### How Components Are Loaded

- **Agents**: The system looks for Python files in the `agents/` directory. Each file should contain a `create_agent()` function that returns an `Agent` instance.
- **Workflows and Pipelines**: These are made available to the system when they're imported as part of the module loading process.

### Disabling a Module

To disable a module without removing it from the codebase, simply add "disabled" to the module directory name:

```bash
# For core modules
mv src/core/modules/your_module_name src/core/modules/your_module_name_disabled

# For custom modules
mv src/custom/modules/your_module_name src/custom/modules/your_module_name_disabled
```

The system will automatically skip loading modules with "disabled" in their name.

## Test-Driven Development Approach
1. Start by writing tests in the appropriate `tests` folder
2. Run the test script to verify expected behavior
3. Implement the actual component code based on test requirements
4. Iterate and refine until tests pass

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

