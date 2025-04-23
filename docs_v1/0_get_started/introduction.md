# Introduction

Build your own agentic AI system with ABI.

## What is ABI?

The **ABI** (Agent Based Intelligence) project is a Python-based backend framework designed to serve as the core infrastructure for building an Agentic AI Ontology Engine. This system empowers organizations to integrate, manage, and scale AI-driven operations with a focus on ontology, agent-driven workflows, and analytics. Designed for flexibility and scalability, ABI provides a customizable framework suitable for organizations aiming to create intelligent, automated systems tailored to their needs.

## Why ABI?
The **ABI** project aims to provide a open alternative to Palantir by offering a flexible and scalable framework for building intelligent systems using ontology. Unlike Palantir, which is often seen as a monolithic solution, ABI emphasizes modularity and customization, allowing organizations to tailor their AI-driven operations to specific needs. Combined with the Naas.ai ecosystem, ABI can be used to build the brain of your organization's agentic AI applications.

## Key Features

- **Agents**: Configurable AI agents (also named agents) to handle specific organizational tasks and interact with users.
- **Flexible Tools**: Agents with custom tools to interact with external services and data sources (Integrations, Pipelines, Workflows, Analytics)
- **Ontology Based**: Ontologies are used to convert data into knowledge to create a flexible and scalable system.
- **Storage**: Storage system is managing unstructured data in datastore, knowledge graph in triple_store and vector data in vectorstore. It is also designed to manage local and remote data storage seamlessly.
- **Customizable API**: All components can be deployed in an API and use externally by other applications.

## Key Capabilities

- **Event-Driven**: Actions can be triggered by events logged in the triple store.
- **Deterministic Queries**: Deterministic SPARQL queries can be added to the ontology to used by the agents as tools without having to create any python code.
- **Scheduling Tasks**: Tasks can be pre-processed and scheduled to avoid latency.
- **Multi-models**: This project is model agnostic. You can use any LLM you want in your agents or workflows.
