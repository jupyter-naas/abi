# Modules

## What is a Module?

A module in the ABI system is a self-contained, standalone component that encapsulates related functionality. Modules are designed to be pluggable, meaning they can be added or removed from the system without modifying other parts of the codebase. Modules are organized into three categories:

1. **Core Modules**: Located in `src/core/` - These are essential modules that provide the core functionality of the ABI system.
2. **Custom Modules**: Located in `src/custom/modules/` - These are user-created modules that extend the system with additional capabilities.
3. **Marketplace Modules**: Located in `src/marketplace/` - These are community-shared modules available for selective activation.

This three-tier separation provides a clean architecture with distinct purposes: core system functionality, private extensions, and shared community resources.

### Module Directory Purposes

- **Core Modules** (`src/core/`): Foundation modules that provide essential ABI functionality. These should not be modified directly.
- **Custom Modules** (`src/custom/modules/`): Your private modules and customizations. Perfect for organization-specific agents and workflows.
- **Marketplace Modules** (`src/marketplace/`): Community-shared modules. All are disabled by default (`.disabled` suffix) for safety. Enable selectively as needed.

Modules provide a way to organize and structure your code in a modular fashion, making it easier to maintain, extend, and reuse functionality. They can contain various components such as:

- **Agents**: AI agents that provide specific capabilities
- **Workflows**: Sequences of operations that accomplish specific tasks
- **Pipelines**: Data processing flows that transform and analyze information
- **Ontologies**: Definitions of concepts and relationships in the domain
- **Integrations**: APIs and services that provide data and functionality
- **Tests**: Unit and integration tests for the module's components

## How Modules Work

### Module Loading Process

The ABI system uses a configuration-driven approach to load modules at runtime. Here's how the process works:

1. **Configuration Reading**: The system reads the `config.yaml` file to determine which modules should be loaded
2. **Module Selection**: Only modules listed in the `modules` section of the configuration with `enabled: true` are loaded
3. **Path Validation**: The system verifies that each enabled module path exists as a directory
4. **Module Import**: Each valid module path is converted to a Python import path and imported using `importlib.import_module()`
5. **IModule Creation**: An `IModule` instance is created for each successfully imported module
6. **Component Loading**: The module's components are loaded in the following order:
   - Requirements checking (if a `requirements()` function exists)
   - Triggers loading (from `triggers.py` if it exists)
   - Ontologies loading (from `.ttl` files in the `ontologies/` directory)
   - Agents loading (deferred until after all modules are initialized)
7. **Module Registration**: The loaded module is added to the system's registry
8. **Initialization**: After all modules are loaded, `on_initialized()` is called on each module
9. **Agent Loading**: Finally, agents are loaded from each module's agent files

**Key Benefits of Configuration-Based Loading**:
- **Selective Activation**: Enable/disable modules without modifying code
- **Environment-Specific Configurations**: Different module sets for development, testing, and production
- **Dependency Management**: Control loading order and module dependencies
- **Error Handling**: Graceful failure handling with detailed error messages

**Configuration Example** (from `config.yaml` or `config.local.yaml`):
```yaml
modules:
  - module: naas_abi
    enabled: true
  - module: naas_abi_marketplace.ai.chatgpt
    enabled: true
    config:
      openai_api_key: "{{ secret.OPENAI_API_KEY }}"
  - module: naas_abi_marketplace.applications.github
    enabled: false  # This module will not be loaded
```

Modules are referenced by their **Python package name** (the importable path), not by filesystem path. Core modules live in `libs/naas-abi/` and `libs/naas-abi-marketplace/`. Custom modules you build can live anywhere that is importable.

### Module Structure

A typical module has the following directory structure:

```
src/[core|marketplace]/modules/your_module_name/
├── agents/                  # Contains AI agents (optional)
│   └── YourAgent.py         # Must contain create_agent() function
├── ontologies/              # Contains semantic ontology files (optional)
│   └── schema.ttl           # Turtle format ontology files
├── triggers.py              # Event triggers (optional)
├── __init__.py              # Module initialization
└── tests/                   # Contains tests for the module (optional)
    └── test_module.py       # Test implementations
```

**Key Structure Notes**:
- **Required**: Only `__init__.py` is required for a valid module
- **Agent Files**: Must end with `Agent.py` and contain a `create_agent()` function
- **Ontology Files**: `.ttl` files are automatically discovered recursively in `ontologies/`
- **Triggers**: A `triggers.py` file with a `triggers` variable for event handling
- **Optional Functions**: `requirements()` for dependency checking, `on_initialized()` for setup

**Note**: The `src/custom/modules/` directory mentioned in the overview is not currently used in the configuration system. Most modules are either core modules or marketplace modules.

### How Components Are Loaded

The system loads different types of components through specific mechanisms:

- **Agents**: The system recursively scans the module directory for files ending with `Agent.py` (excluding test files ending with `Agent_test.py`). Each agent file must contain a `create_agent()` function that returns an `Agent` instance. Duplicate agents (same name) are skipped with a warning.

- **Triggers**: If a `triggers.py` file exists in the module root, it's imported and any `triggers` attribute is loaded. Triggers are used for event-driven functionality in the triple store system.

- **Ontologies**: The system recursively searches for `.ttl` (Turtle) files in the `ontologies/` directory and loads them into the triple store service for semantic data processing.

- **Requirements**: If the module defines a `requirements()` function, it's called during loading to verify that all necessary dependencies and conditions are met before proceeding.

- **Initialization**: If the module defines an `on_initialized()` function, it's called after all modules have been loaded but before agents are loaded, allowing for cross-module setup.

### Disabling a Module

There are two ways to disable a module:

#### 1. Configuration-Based Disabling (Recommended)

Set `enabled: false` in your `config.yaml` file:

```yaml
modules:
  - module: naas_abi_marketplace.applications.postgres
    enabled: false  # This module will not be loaded
```

This is the preferred method as it:
- Keeps the module code intact
- Allows easy re-enabling
- Supports environment-specific configurations
- Provides clear visibility of disabled modules

#### 2. Directory Naming (Legacy)

Add "disabled" to the module directory name:

```bash
# For core modules
mv src/core/your_module_name src/core/your_module_name.disabled

# For marketplace modules  
mv src/marketplace/your_module_name src/marketplace/your_module_name.disabled
```

**Note**: The system will skip loading modules with "disabled" in their name even if they're enabled in the configuration. However, the configuration-based approach is recommended for better maintainability.

## Test-Driven Development Approach
1. Start by writing tests in the appropriate `tests` folder
2. Run the test script to verify expected behavior
3. Implement the actual component code based on test requirements
4. Iterate and refine until tests pass

## Best Practices

1. **Choose the right location**: Place essential system functionality in core modules, your private extensions in custom modules, and shared community modules in marketplace
2. **Keep modules focused**: Each module should have a clear, specific purpose
3. **Maintain independence**: Minimize dependencies between modules
4. **Document your components**: Provide clear documentation for your agents, workflows, and pipelines
5. **Write tests**: Include comprehensive tests for your module's components
6. **Follow naming conventions**: Use descriptive names for your module and its components

## Troubleshooting

If your module is not being loaded correctly, check the following:

### Configuration Issues
1. **Module Not Listed**: Ensure your module is listed in the `modules` section of `config.yaml`
2. **Module Disabled**: Verify that `enabled: true` is set for your module in the configuration
3. **Path Incorrect**: Check that the module path in `config.yaml` matches the actual directory structure
4. **Directory Doesn't Exist**: Ensure the module directory exists at the specified path

### Module Structure Issues
5. **Missing __init__.py**: Verify your module has an `__init__.py` file (required for Python imports)
6. **Agent Function Missing**: Check that agent files ending with `Agent.py` contain a `create_agent()` function
7. **Import Path Issues**: Ensure the module can be imported using the path specified in the configuration

### Runtime Issues
8. **Requirements Not Met**: If your module has a `requirements()` function, ensure it returns `True`
9. **Import Errors**: Check the application logs for detailed error messages during module loading
10. **Name Contains "disabled"**: Even if enabled in config, modules with "disabled" in their directory name are skipped

### Debugging Steps
- Check application logs for detailed error messages
- Verify module paths with: `python -c "import sys; sys.path.append('.'); import your.module.path"`
- Test agent creation independently: `from your.module.path.agents.YourAgent import create_agent; create_agent()`

**Error Handling**: Module loading failures cause the application to exit with detailed error messages to prevent running with incomplete functionality.

By following this guide, you should be able to create and integrate new modules into the ABI system effectively.

