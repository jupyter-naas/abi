---
sidebar_position: 3
title: "Ontology-Driven AI System"
---

# Ontology-Driven AI System

ABI is an **AI Operating System**: build your own AI using ontologies as the unifying field connecting data, models, workflows, and systems.

---

## The core idea

Most AI systems treat data, models, and workflows as separate concerns stitched together with glue code. ABI takes a different approach: **ontologies are the unifying field**.

An ontology is a formal, machine-readable description of the world: what entities exist, how they relate, and what operations can be performed on them. When your data, agents, workflows, and integrations all speak the same ontological language, they become composable by design rather than by accident.

```bash
     Data sources          Knowledge Graph (RDF/OWL)
     ─────────────  ──────────────────────────────────────
     CRM, ERP,      Entities, relationships, facts, inferred
     APIs, files    knowledge, queryable via SPARQL

          ↕                         ↕

     Agents                    Workflows & Pipelines
     ──────────────────         ────────────────────────────
     LLM-powered interfaces     Business logic operating on
     that route intent and      the knowledge graph, triggered
     invoke tools               by events or schedules
```

Everything in ABI (agents, pipelines, workflows, integrations) operates on the same shared knowledge graph. There is no ETL to a vector store, no separate "AI layer". The ontology IS the integration layer.

---

## Why an operating system

An OS provides shared primitives that every application uses without reimplementing: memory, I/O, scheduling, inter-process communication.

ABI provides the same for AI:

| OS primitive | ABI equivalent |
|---|---|
| File system | Knowledge graph (triple store) |
| Process model | Agent runtime (LangGraph state machines) |
| IPC / messaging | Bus service (RabbitMQ or in-memory) |
| Package manager | Module system (installable, versioned capabilities) |
| Shell / CLI | `abi chat`, MCP server, REST API |
| Scheduler | Dagster pipelines and workflow triggers |

You bring the domain. ABI provides the runtime.

---

## The agent layer

Agents are the user-facing interface to the system. Each agent is a LangGraph state machine with:

- A **system prompt** defining its role and behavior
- A **tool list** (workflows, integrations, or other agents it can invoke)
- An **intent declaration** controlling how the supervisor routes to it
- Optional **persistent memory** (PostgreSQL-backed conversation history)

### Intent routing

A **SupervisorAgent** receives all incoming messages and routes them to the correct specialized agent using semantic intent matching (vector similarity over registered intent descriptions).

Each agent declares a scope:

| Scope | Behavior |
|---|---|
| `supervisor` | Visible in the default routing table: production agents users can access directly |
| `integration` | Available for direct invocation, excluded from supervisor routing, for agents requiring specific credentials |
| `research` | Excluded from production routing: experimental or evaluation agents |

### Agent composition

Agents can use other agents as tools, enabling delegation hierarchies:

```bash
SupervisorAgent
├── ContentAgent        → LinkedIn integration tools
├── CRMAgent            → Salesforce + knowledge graph tools
├── FinanceAgent        → QuickBooks + SPARQL workflows
└── ResearchAgent       → web search + OntologyEngineerAgent
    └── OntologyEngineerAgent  (scope: research)
```

### Built-in agents

| Agent | Role |
|---|---|
| `AbiAgent` | Root supervisor: routes all queries via intent matching |
| `OntologyEngineerAgent` | Designs and extends ontologies using BFO/CCO |
| `KnowledgeGraphBuilderAgent` | Converts unstructured descriptions into RDF triples |
| `EntityToSPARQLAgent` | Converts natural-language queries into SPARQL |

---

## Model layer

All agents accept a `ChatModel` interface, not a specific provider. The default uses **OpenRouter**; one API key gives access to every supported model.

For local or air-gapped deployments, models are served via **Ollama**:

| Model | Command | Use case |
|---|---|---|
| Qwen3 8B | `ollama pull qwen3:8b` | Multilingual, code-capable |
| DeepSeek R1 8B | `ollama pull deepseek-r1:8b` | Advanced reasoning |
| Gemma3 4B | `ollama pull gemma3:4b` | Lightweight and fast |

---

## How agents are exposed

Every agent is automatically available on three interfaces without additional configuration:

| Interface | Endpoint |
|---|---|
| REST API | `POST /agents/{agent_name}/completion` and `/stream-completion` |
| MCP tool | Dynamically registered at MCP server startup |
| CLI | `abi chat --agent {name}` |

Bearer token authentication is required for all REST endpoints.

---

## Further reading

- [The ABI Stack](the-stack): the four packages and how they fit together
- [Knowledge Graph](knowledge-graph): ontologies, RDF, and SPARQL in depth
- [Creating an Agent](../capabilities/agents/creating-an-agent): step-by-step guide
- [Agent.New() Pattern](/updates/agent-class-new-pattern): ADR
- [Intent Scope Routing](/updates/intent-scope-agent-routing): ADR
