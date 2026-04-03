# The Agent System

ABI agents are LLM-powered interfaces that sit on top of the knowledge graph and the module system. They route user intent to the right tools, delegate to specialized agents, and maintain conversation context across sessions.

Related pages: [[building/creating-an-agent|Creating an Agent]], [[concepts/the-stack|The ABI Stack]], [[libs/naas-abi-core/Engine|Engine]], [[adr/20260305_agent-class-new-pattern|ADR: Agent.New() Pattern]].

---

## What an agent is

An ABI agent is a LangGraph state machine with:
- A **system prompt** that defines its role and behavior.
- A **tool list** (workflows, integrations, or other agents) it can invoke.
- An **intent declaration** that controls how the supervisor routes to it.
- Optional **persistent memory** (PostgreSQL-backed conversation history).

Agents are defined as Python classes using the `Agent.New()` class method pattern and are auto-discovered by the Engine at startup.

---

## The intent routing system

ABI has a **SupervisorAgent** (also called the ABI agent or IntentAgent) that receives all incoming messages and routes them to the correct specialized agent based on registered intents.

Each agent declares one or more **intents** - short descriptions of what it handles. The supervisor uses semantic matching (vector similarity) to select the best agent for a given query.

### Intent scopes

Agents declare a scope that controls their visibility to the supervisor:

| Scope | Behavior |
|-------|---------|
| `supervisor` | Visible in the default routing table. Used for production agents that users can access directly. |
| `integration` | Available for direct invocation but excluded from the supervisor's routing. Use for agents that require specific API credentials. |
| `research` | Excluded from production routing. Use for experimental or evaluation agents. |

See [[adr/20250925_intent-scope-agent-routing|ADR: Intent Scope]].

---

## Agent composition

Agents can use other agents as tools. This enables delegation hierarchies:

```
SupervisorAgent
├── ContentAgent        → uses LinkedIn integration tools
├── CRMAgent            → uses Salesforce and knowledge graph tools
├── FinanceAgent        → uses QuickBooks + SPARQL workflows
└── ResearchAgent       → uses web search + ontology engineer agent
    └── OntologyEngineerAgent  (scope: research)
```

Agents passed in the `agents=[]` list of another agent's constructor are automatically registered as callable tools.

---

## Built-in agents

| Agent | Description |
|-------|-----------|
| `AbiAgent` | Root supervisor. Routes all queries to specialized agents via intent matching. |
| `OntologyEngineerAgent` | Designs and extends ontologies. Understands BFO/CCO structure. |
| `KnowledgeGraphBuilderAgent` | Converts unstructured descriptions into RDF triples for the knowledge graph. |
| `EntityToSPARQLAgent` | Converts natural-language entity descriptions into SPARQL queries. |

---

## Model configuration

All agents accept a `ChatModel` interface rather than being bound to a specific provider. The default model is configured via OpenRouter - a single `OPENROUTER_API_KEY` gives access to every supported provider.

For local/air-gapped deployments, models are served via Ollama:

| Model | Command | Use case |
|-------|---------|---------|
| Qwen3 8B | `ollama pull qwen3:8b` | Multilingual, code-capable |
| DeepSeek R1 8B | `ollama pull deepseek-r1:8b` | Advanced reasoning |
| Gemma3 4B | `ollama pull gemma3:4b` | Lightweight and fast |

See [[adr/20251106_openrouter-unified-model-layer|ADR: OpenRouter]] and [[getting-started/configuration|Configuration]].

---

## Persistent memory

Agents automatically detect and configure memory based on the environment:

- **With PostgreSQL** (`POSTGRES_URL` set): conversation history persists across restarts. Each `thread_id` is an isolated conversation context.
- **Without PostgreSQL**: in-memory storage, history lost on restart.

Memory is per-agent and thread-scoped. No explicit configuration is required - the agent detects PostgreSQL availability at startup.

---

## How agents are exposed

Every agent is automatically available via three interfaces:

| Interface | How |
|-----------|-----|
| REST API | `POST /agents/{agent_name}/completion` and `/stream-completion` |
| MCP tool | Dynamically registered by the MCP server at startup |
| CLI | `abi chat --agent {name}` |

Bearer token authentication is required for all REST endpoints.
