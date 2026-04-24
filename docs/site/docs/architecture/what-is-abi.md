---
sidebar_position: 1
---

# Overview

ABI is the open-source AI operating system for enterprise knowledge work. Its architecture mirrors the approach Palantir took with Foundry and AIP, but built entirely in the open: MIT-licensed, self-hosted, and grounded in the same formal ontology standards (BFO/OWL/SPARQL) used in defense, healthcare, and intelligence.

This architecture center documents how the system is designed, how its components fit together, and what it takes to deploy it in production.

---

## What is ABI?

ABI (Agentic Brain Infrastructure) gives any organization three things: a private knowledge graph grounded in formal ontology, a configurable fleet of AI agents, and the infrastructure to connect them to every tool and data source the organization uses.

Most organizations have a data problem masquerading as an AI problem. Data lives in dozens of disconnected SaaS tools. Querying it requires either hand-coding integrations for each source or feeding unstructured exports into an LLM and hoping it reasons correctly. ABI solves this by converting raw data into a structured knowledge graph with a formal ontology (BFO/OWL), then letting AI agents query that graph with precision. Agents know the difference between a Person, a Role, and an Organization because the ontology says so, not because an LLM guessed.

---

## How it compares

| Capability | ABI | Palantir Foundry | LangChain / LlamaIndex |
|---|---|---|---|
| Formal ontology (BFO/OWL) | Yes | Yes | No |
| Self-hosted / air-gapped | Yes | No | Yes |
| Open source (MIT) | Yes | No | Yes |
| Knowledge graph (SPARQL) | Yes | Yes | Partial |
| Multi-agent orchestration | Yes | No | Yes |
| Module marketplace | Yes | No | Limited |
| Managed enterprise tier | Yes (naas.ai) | Yes | No |

---

## What it is not

It is not a chatbot wrapper. The knowledge graph and the service infrastructure are the product; agents are the interface on top.

It is not a low-code platform. ABI is a Python framework for teams that want to own their AI stack in code.

It is not cloud-locked. The full stack runs locally with Docker, entirely air-gapped, or on your own infrastructure. MIT licensed: your data, your models, your infrastructure, permanently.

---

## Guide to the Architecture

This section is written for engineers, architects, and technical decision-makers evaluating or deploying ABI. Each page covers a distinct slice of the architecture:

**[The ABI Stack](./the-stack)** covers how the three open-source packages constitute an enterprise AI operating system: the module as the atomic unit, the five runtime layers, the package structure, and what runs in production. Start here for a complete picture of the system.

**[The Ontology System](./knowledge-graph)** explains how ABI models the operational world as typed entities and relationships using ISO open standards (BFO/OWL/SPARQL): the Language, Engine, and Toolchain that make the knowledge graph a first-class architectural component rather than a reporting layer.

**[The Data Plane](./data-plane)** covers ABI's "any data, any compute, any model" architecture: the five purpose-built open-source stores, the three compute modes (batch, event-driven, interactive), and how models are selected per request without code changes.

**[Interoperability](./interoperability)** documents every integration point: SPARQL endpoints, S3-compatible object storage, MCP tool registration, OpenAI-compatible model interfaces, standard JWT auth, and the Python SDK.

**[The Runtime](./deployment-models)** covers how ABI is operated in practice: Docker Compose as the infrastructure substrate, the four deployment topologies (local, on-premises, air-gapped, managed), and how configuration drives environment differences.

**[The Agent System](./agent-system)** explains how agents are structured as LangGraph state machines, how intent routing dispatches requests to the right domain agent, how agents compose into delegation hierarchies, and how they are exposed simultaneously via REST, MCP, and CLI.

---

→ [The ABI Stack](./the-stack)
