# ABI Source Core Directory

This directory contains the core functionality of ABI, including assistants, integrations, models, ontologies, pipelines, and workflows.

## Directory Structure

### `analytics/`
Contains modules related to data analytics and visualization.

- **dashboards/**: Templates and implementations for various dashboards.
- **reports/**: Modules for generating analytical reports.
- **visualization/**: Tools and classes for visualizing ontologies and data graphs.

### `apps/`
Houses application-specific code, including terminal agents.

- **terminal_agent/**: Modules for terminal-based AI agents.
  - `main.py`: Entry point for the terminal agent.
  - `prompts.py`: Configuration of assistant prompts.
  - `terminal_style.py`: Styling and user interface utilities for the terminal.

### `assistants/`
Defines various AI assistants with different scopes and integrations.

- **custom/**: Custom assistants tailored to specific needs.
- **domain/**: Domain-specific assistants focusing on particular areas.
- **expert/**: Expert assistants focused on specific tasks and tools.
- **foundation/**: Foundational components and manager for assistants.
- **prompts/**: Prompt templates used in the assistants.

### `integrations/`
Modules for connecting with external services and APIs.

### `models/`
List of models used in the assistants.

### `ontologies/`
Ontologies schemas organized in four hierarchical layers in the directory:

- **Top-Level**: Foundational concepts and relationships that apply across all domains
- **Mid-Level**: Common patterns and structures shared between multiple domains
- **Domain-Level**: Specific concepts and relationships for individual domains
- **Application-Level**: Concrete implementations and extensions for specific use cases

### `pipelines/`
Data processing pipelines organized by tools/functionality.
Each pipeline follows a standardized structure for data transformation and processing.

### `workflows/`
Houses workflow definitions that orchestrate complex processes.
- Workflows combine multiple integrations and pipelines to achieve specific business objectives.
- Each workflow is self-contained and follows a standardized interface.