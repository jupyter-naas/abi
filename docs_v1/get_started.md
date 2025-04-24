# Get Started

**Table of Contents**

- [Get Started](#get-started)
  - [Introduction](#introduction)
    - [What is ABI?](#what-is-abi)
    - [Why ABI?](#why-abi)
    - [Key Features](#key-features)
    - [Key Capabilities](#key-capabilities)
  - [Installation](#installation)
    - [Pre-requisites](#pre-requisites)
    - [Installation Options](#installation-options)
    - [Setup Environment](#setup-environment)
    - [Configure YAML](#configure-yaml)
  - [Quickstart](#quickstart)
    - [Start Chatting](#start-chatting)
    - [Create Your First Module](#create-your-first-module)
  - [Help \& Support](#help--support)

## Introduction

### What is ABI?

The **ABI** (Agent Based Intelligence) project is a Python-based backend framework designed to serve as the core infrastructure for building an Agentic AI Ontology Engine. This system empowers organizations to integrate, manage, and scale AI-driven operations with a focus on ontology, agent-driven workflows, and analytics. Designed for flexibility and scalability, ABI provides a customizable framework suitable for organizations aiming to create intelligent, automated systems tailored to their needs.

### Why ABI?
The **ABI** project aims to provide a open alternative to Palantir by offering a flexible and scalable framework for building intelligent systems using ontology. Unlike Palantir, which is often seen as a monolithic solution, ABI emphasizes modularity and customization, allowing organizations to tailor their AI-driven operations to specific needs. Combined with the Naas.ai ecosystem, ABI can be used to build the brain of your organization's agentic AI applications.

### Key Features

- **Agents**: Configurable AI agents (also named agents) to handle specific organizational tasks and interact with users.
- **Flexible Tools**: Agents with custom tools to interact with external services and data sources (Integrations, Pipelines, Workflows, Analytics)
- **Ontology Based**: Ontologies are used to convert data into knowledge to create a flexible and scalable system.
- **Storage**: Storage system is managing unstructured data in datastore, knowledge graph in triple_store and vector data in vectorstore. It is also designed to manage local and remote data storage seamlessly.
- **Customizable API**: All components can be deployed in an API and use externally by other applications.

### Key Capabilities

- **Event-Driven**: Actions can be triggered by events logged in the triple store.
- **Deterministic Queries**: Deterministic SPARQL queries can be added to the ontology to used by the agents as tools without having to create any python code.
- **Scheduling Tasks**: Tasks can be pre-processed and scheduled to avoid latency.
- **Multi-models**: This project is model agnostic. You can use any LLM you want in your agents or workflows.

## Installation

Get started with ABI - Install, configure and chat with your first agent.

### Pre-requisites

- **Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)**
- **Create your account on [NAAS](https://naas.ai)** (Optional, only if you want to use the storage system in production)

### Installation Options

Choose one of the following options:

1. **Clone the Repository**
```bash
git clone https://github.com/jupyter-naas/abi.git
cd abi
```

2. **Fork the Repository**
```bash
# 1. Fork via GitHub UI
# 2. Clone your fork
git clone https://github.com/YOUR-USERNAME/abi.git
cd abi
```

3. **Create a Private Fork**
```bash
# 1. Create private repository via GitHub UI
# 2. Clone your private repository
git clone https://github.com/YOUR-USERNAME/abi-private.git
cd abi-private
git remote add upstream https://github.com/jupyter-naas/abi.git
git pull --rebase upstream main
git push
```

### Setup Environment

1. Copy this file to .env
```bash
cp .env.example .env
```
2. Replace placeholder values with your actual credentials
3. Uncomment (remove #) from lines you want to activate. The variables are used to configure the assistant.

Note: The .env file should never be committed to version control
as it contains sensitive credentials

### Configure YAML

1. Copy the example file to config.yaml
```bash
cp config.yaml.example config.yaml
```

2. Edit the file with your configuration:
- `workspace_id`: Workspace ID in Naas Platform. It will be used for storage and publishing modules components. Access it from this [link](https://naas.ai/account/settings)
- `github_project_repository`: Your Github repository name (e.g. "jupyter-naas/abi"). It will be used in documentation and API as registry name.
- `github_support_repository`: A Github repository name (e.g. "jupyter-naas/abi") to store support issues. It will be used by the support agent to create all requests or report bugs. It can be the same as `github_project_repository`.
- `github_project_id`: Your Github project number stored in Github URL (e.g. 12 for https://github.com/jupyter-naas/abi/projects/12). It will be used to assign all your issues to your github project.
- `triple_store_path`: Path to the ontology store (e.g. "storage/triplestore")
- `api_title`: API title (e.g. "ABI API") displayed in the documentation.
- `api_description`: API description (e.g. "API for ABI, your Artifical Business Intelligence") displayed in the documentation.
- `logo_path`: Path to the logo (e.g. "assets/logo.png") used in the API documentation.
- `favicon_path`: Path to the favicon (e.g. "assets/favicon.ico") used in the API documentation.
- `storage_name`: Name of the storage (e.g. "abi")
- `space_name`: Name of the space (e.g. "abi")

## Quickstart

### Start Chatting

Now, the project is installed and configured, you can start chatting with the core agent by running the following command:

```bash
make chat-supervisor-agent
```

This command will setup the environment, install the dependencies, initalize your triple store and run the supervisor agent.
It can take a few minutes at the first time you run it.


### Create Your First Module

```bash
make create-module
```

This process will create a new module in the `src/custom/modules` directory with all the necessary components templates: agents, integrations, ontologies, pipelines and workflows.
It will also register your agent in the Makefile so you can run it directly with the following command:

```bash
make chat-[name]-agent
```

Now, learn how to customize your module by following the [module documentation](../modules/overview.md).

## Help & Support
For any questions or support requests, please create an issue on this repository or reach out via [support@naas.ai](mailto:support@naas.ai).


