# Custom Modules Guide

## Overview

This documentation covers how to work with custom modules in the ABI system. Custom modules are user-created extensions that live in the `src/custom/modules/` directory and provide additional functionality beyond the core system.

## What are Custom Modules?

Custom modules are extension points that allow you to add your own functionality to the ABI system without modifying the core codebase. They follow the same modular architecture as core modules but are kept separate to maintain a clear distinction between essential system functionality and custom extensions.

Custom modules can contain:
- **Assistants**: AI agents that provide specific capabilities
- **Workflows**: Sequences of operations that accomplish specific tasks
- **Pipelines**: Data processing flows that transform and analyze information
- **Integrations**: Connectors to external services and APIs
- **Tests**: Unit and integration tests for the module's components

## Installing Custom Modules

### Step 1: Obtain the Module

Custom modules can be obtained from:
- The ABI marketplace (`src/marketplace/`)
- Third-party repositories
- Your own development

### Step 2: Add the Module to Your Project

1. Copy the module directory to `src/custom/modules/`:

```bash
# If copying from marketplace
cp -r src/marketplace/your_module_name/ src/custom/modules/
```

2. Ensure the module follows the standard directory structure:

```
src/custom/modules/your_module_name/
├── assistants/           # Contains AI agents
├── workflows/            # Contains workflow implementations
├── pipelines/            # Contains pipeline implementations
├── integrations/         # Contains service connectors
└── tests/                # Contains tests for the module
```

### Step 3: Install Dependencies

If the module has dependencies, you need to add them to your project:

#### Using Poetry

```bash
# Add a single dependency
make add dep=package_name

# Add multiple dependencies
make add dep="package1 package2 package3"
```

#### Updating Makefile (if required)

Some modules may require specific build steps. In that case, you may need to add custom targets to your Makefile:

```makefile
# Example: Add a build step for a custom module with Rust components
src/custom/modules/your_module_name/target/wheels/module-*.whl:
	@ make -C src/custom/modules/your_module_name release

.venv: $(DEPENDENCIES) src/custom/modules/your_module_name/target/wheels/module-*.whl
	@ docker compose run --rm --remove-orphans abi poetry install
	@ docker compose run --rm --remove-orphans abi bash -c 'poetry run python -m pip install --force-reinstall /app/src/custom/modules/your_module_name/target/wheels/*.whl'
```

### Step 4: Configure the Module

1. Update `config.yaml` if the module requires specific configuration:

```yaml
custom_modules:
  your_module_name:
    setting1: value1
    setting2: value2
```

2. Set any required environment variables in your `.env` file.

## Using Custom Modules

Once installed, custom modules are automatically discovered and loaded by the ABI system at runtime. You can use them in several ways:

### Accessing Assistants

```bash
# Run a custom assistant directly
make chat-your-assistant-name-agent
```

### Using Workflows and Pipelines

Custom workflows and pipelines can be:
1. Used by assistants as tools
2. Called directly from your code
3. Accessed via the API endpoints they expose

### API Access

All workflows and pipelines that implement the `as_api()` method will automatically expose endpoints in the FastAPI server:

```bash
# Start the API server
make api
```

Then access your custom endpoints at `http://localhost:9879/docs`.

## Developing Custom Modules

If you want to create your own custom module, follow the guide in [modules.md](../modules/modules.md) for detailed instructions on module structure and development.

## Troubleshooting

If your custom module is not being loaded correctly:

1. Ensure it's located directly in `src/custom/modules/`
2. Check that its name doesn't contain "disabled"
3. Verify dependencies are properly installed
4. Look for import errors in the console output
5. Check that any required configuration is present in your `config.yaml` or `.env` file

## Best Practices

1. Keep custom modules self-contained with minimal dependencies on other modules
2. Include comprehensive documentation and tests
3. Consider contributing general-purpose modules back to the marketplace
4. Use semantic versioning for your modules to track changes
5. Document any environment variables or configuration required by your module
