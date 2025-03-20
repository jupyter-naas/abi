# ABI
*Agent Based Intelligence*

<img src="./assets/abi-flywheel.png" width="100%" height="100%">

## Overview

The **ABI** (Agent Based Intelligence) project is a Python-based backend framework designed to serve as the core infrastructure for building an Agentic AI Ontology Engine. This system empowers organizations to integrate, manage, and scale AI-driven operations with a focus on ontology, agent-driven workflows, and analytics. Designed for flexibility and scalability, ABI provides a customizable framework suitable for organizations aiming to create intelligent, automated systems tailored to their needs.

## Why ABI?
The **ABI** project aims to provide a open alternative to Palantir by offering a flexible and scalable framework for building intelligent systems using ontology. Unlike Palantir, which is often seen as a monolithic solution, ABI emphasizes modularity and customization, allowing organizations to tailor their AI-driven operations to specific needs. Combined with the Naas.ai ecosystem, ABI can be used to build the brain of your organization's agentic AI applications.

## Key Features

- **Assistants**: Configurable AI assistants (also named agents) to handle specific organizational tasks and interact with users.
- **Ontology Management**: Define and manage data relationships, structures, and semantic elements.
- **Integrations**: Seamlessly connect to external data sources and APIs for unified data access.
- **Pipelines**: Define data processing pipelines to handle and transform data efficiently into the ontological layer.
- **Workflows**: Automate complex business processes and manage end-to-end workflows.
- **Analytics**: Access insights through integrated analytics and real-time data processing.
- **Data**: Handle diverse datasets and manage schema, versioning, deduplication, and change data capture.

## Quick Start

### Step 1: Clone the repository

```bash
git clone https://github.com/jupyter-naas/abi.git
```

### Step 2: Setup environment variables

```bash
cp .env.example .env
```

### Step 3: Run the project

```bash
make
```
This will run the supervisor agent and the agentic engine.

For specific agents, you can run them directly with the following command:

```bash
make chat-[name]-agent
```

### Step 4: Build and run the API

You need to build the API before running it. Find out more about the API in the [API documentation](./docs/api/deploy-api.md).

```bash
make api
```

### Step 5: Build your own agent

```bash
make build-agent
```

This will build the agent and save it in the `/src/custom/modules` directory.


## Contributing

We welcome contributions! Please read the [contributing guidelines](./CONTRIBUTING.md) for more information.

## License
ABI Framework is open-source and available for use under the [MIT license](https://opensource.org/licenses/MIT). Professionals and enterprises are encouraged to contact our support for custom services as this project evolves rapidly at support@naas.ai

