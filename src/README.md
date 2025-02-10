# ABI Source Directory

Welcome to the `src` directory of ABI! This is the central place where users interact with the functionalities built in the `lib/abi` library. Here, you can build all your integrations, pipelines, workflows, and applications.

## Directory Structure 
The ABI source directory is organized into three main sections:

1. Core Components
   - Contains essential ABI functionality and modules
   - Houses assistants, integrations, pipelines, and more
   - Located in the `core/` directory

2. Custom Extensions 
   - Organization-specific implementations and adaptations
   - Allows extending core features while maintaining separation
   - Located in the `custom/` directory

3. Root-Level Files
   - Configuration and initialization files
   - Core utilities like CLI tools
   - Located in the root `src/` directory

### Core Directory

The `core` directory contains the core functionality of ABI, including assistants, integrations, models, ontologies, pipelines, and workflows.

- `analytics/`: Data analytics and visualization modules.
- `apps/`: Application-specific code, including terminal agents.
- `assistants/`: AI assistants with different scopes and integrations.
- `integrations/`: Modules for connecting with external services and APIs.
- `models/`: List of models used in the assistants.
- `ontologies/`: Ontologies schemas organized in four hierarchical layers.
- `pipelines/`: Data processing pipelines organized by tools/functionality.
- `workflows/`: Workflows that orchestrate complex processes.

### Custom Directory

The `custom` directory contains custom implementations and extensions of the core functionality. It allows for organization-specific adaptations and specialized features while maintaining separation from the core codebase.

### Root-Level Files

- `__init__.py`: Initializes the `src` package.
- `api.py`: Use to create specific API endpoints.
- `cli.py`: Command-line interface for interacting with ABI.
- `mappings.py`: Use to create custom mappings.
- `openapi_docs.py`: Use to create OpenAPI documentation.
- `services.py`: Use to create custom services (store).