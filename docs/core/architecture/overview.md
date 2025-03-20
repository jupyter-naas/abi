# ABI Architecture Overview

ABI is a Python-based framework for building organizational AI systems with a layered, modular architecture designed for flexibility and extensibility.

## Architectural Principles

ABI follows these core architectural principles:

1. **Layered Design**: Clear separation between integrations, pipelines, and workflows
2. **Hexagonal Architecture**: Services use ports and adapters pattern for flexible backend integration
3. **Semantic Data Model**: Ontology-based knowledge representation
4. **Component Exposure**: Components can be exposed as both LLM tools and API endpoints
5. **Modular Organization**: Core and custom modules with standardized structure

## System Architecture Diagram

## Key Components

1. **Integrations**: Connect to external services and APIs
2. **Pipelines**: Transform raw data into semantic knowledge
3. **Workflows**: Implement business logic and specific intents
4. **Assistants**: AI agents with specific roles using workflows, pipelines, and integrations
5. **Ontology**: Knowledge representation using RDF/semantic web technologies
6. **Services**: Core system services following hexagonal architecture

## Module Organization

ABI's codebase is organized into two primary module categories:

1. **Core Modules** (`src/core/modules/`): Essential system functionality
2. **Custom Modules** (`src/custom/modules/`): User-created extensions
3. **Marketplace**: (`src/custom/marketplace/`) A place for sharing and discovering integrations, pipelines, and workflows, analytics, agents & assistants

Each module follows a standardized directory structure:
- `assistants/`: AI agent implementations
- `analytics/`: Analytics and reporting
- `workflows/`: Business logic implementations
- `ontology/`: Ontology management and reasoning
- `pipelines/`: Data transformation implementations
- `integrations/`: External service connectors
- `tests/`: Unit and integration tests

## Technology Stack

- **Python**: Primary programming language
- **Docker**: Containerization for development and deployment
- **Poetry**: Dependency management
- **RDFLib**: Semantic data handling
- **LangChain**: LLM integration and agent framework
- **FastAPI**: API development