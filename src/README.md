# ABI Source Directory

Welcome to the `src` directory of ABI! This is the central place where users interact with the functionalities built in the `lib/abi` library. Here, you can build all your integrations, pipelines, workflows, and applications. Additionally, this directory is where ontologies, models, and assistants are defined and managed.

## Directory Structure

### `analytics/`
Contains modules related to data analytics and visualization.

- **dashboards/**: Templates and implementations for various dashboards.
  - `finance-dashboard.py`: Finance-specific dashboard implementation.
  - `finance-dashboard-template.py`: Template for creating new finance dashboards.
- **reports/**: Modules for generating analytical reports.
- **visualization/**: Tools and classes for visualizing ontologies and data graphs.
  - `ontology_graph.py`: Visualization tool for ontologies using RDFlib and PyVis.

### `apps/`
Houses application-specific code, including a terminal agents.

- **terminal_agent/**: Modules for terminal-based AI agents.
  - `main.py`: Entry point for the terminal agent.
  - `prompts.py`: Configuration of assistant prompts.
  - `terminal_style.py`: Styling and user interface utilities for the terminal.

### `assistants/`
Defines various AI assistants with different scopes and integrations.

- **custom/**: Custom assistants tailored to specific needs.
- **domain/**: Domain-specific assistants focusing on particular areas.
- **foundation/**: Foundational components and manager for assistants.
  - `assistant_manager.py`: Manages the creation and handling of assistants.
- **personal/**: Personal AI assistants for individual users.
- `assistants-config.yaml`: Configuration file for managing assistant settings.

### Root-Level Files

- `cli.py`: Command-line interface for interacting with ABI.
- `__init__.py`: Initializes the `src` package.

## Key Components

### Integrations
Leverage or build integrations to connect ABI with external services. Integrations facilitate communication between ABI and platforms like GitHub, LinkedIn, Stripe, and more.

### Pipelines
Define data processing pipelines to handle and transform data efficiently. Pipelines automate workflows, ensuring data flows seamlessly through various processing stages.

### Workflows
Automate tasks and processes to streamline operations. Workflows define the sequence of actions and integrations necessary to accomplish specific objectives.

### Applications
Develop user-facing applications and administrative tools using frameworks like Streamlit. Applications provide interfaces for managing configurations, monitoring analytics, and interacting with AI assistants.

### Ontologies and Models
Ontologies are organized in four hierarchical layers in the `src/ontologies` directory:

- **Top-Level**: Foundational concepts and relationships that apply across all domains
- **Mid-Level**: Common patterns and structures shared between multiple domains
- **Domain-Level**: Specific concepts and relationships for individual domains
- **Application-Level**: Concrete implementations and extensions for specific use cases

### Assistants
Create and configure AI assistants in the `assistants/` directory. Assistants can range from personal helpers to domain-specific advisors, each tailored with unique prompts and integrations.