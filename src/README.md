# ABI Source Directory

Welcome to the `src` directory of ABI! This is the central place where users interact with the functionalities built in the `lib/abi` library.

## Directory Structure 
The ABI source directory is organized into three main sections:

1. Core Components
   - Located in the `core/` directory
   - Contains essential ABI functionality and modules

2. Custom Extensions 
   - Located in the `custom/` directory
   - Organization-specific implementations and adaptations
   - Allows extending core features while maintaining separation

3. Root-Level Files
   - Located in the root `src/` directory
   - Configuration and initialization files
   - Core utilities like CLI tools

### Root-Level Files

- `__init__.py`: Initializes the `src` package.
- `api.py`: Use to create specific API endpoints.
- `cli.py`: Command-line interface for interacting with ABI.
- `mappings.py`: Use to create custom mappings.
- `openapi_docs.py`: Use to create OpenAPI documentation.
- `services.py`: Use to create custom services (store).