# AIA — Personal AI Assistant

> **AIA controls perception. ABI controls reality.**  
> Intelligence = alignment between both.

---

## What is AIA?

AIA is your **personal AI assistant** — the layer that knows *you*: your persona, your preferences, your data, your context. It translates your intent into actions executed by ABI.

ABI ([naas-abi](https://github.com/jupyter-naas/abi)) is the **agentic brain infrastructure** — ontologies, knowledge graphs, multi-agent orchestration, workflows, and connections to the real world.

```
YOU
 │  intent · context · goals
 ▼
AIA  ←── this project
 │  persona · memory · interface · intent translation
 ▼
ABI  ←── .abi/ (naas-abi engine)
 │  ontologies · knowledge graph · agents · workflows · APIs
 ▼
REAL WORLD
 │  data systems · documents · people · OSINT · market
 ▼
FEEDBACK LOOP
   learning · adaptation
```

---

## The Key Distinction

| Layer | Role | Lives in |
|-------|------|----------|
| **AIA** | Translates YOU → system | `src/` |
| **ABI** | Translates system → reality | `.abi/` |

**Copilot world:** `User → Chat → LLM → Answer`

**AIA × ABI world:** `User → AIA → ABI → Agents → Reality → Feedback → Learning`

---

## AIA Modules (`src/`)

| Module | Domain | What it gives AIA |
|--------|--------|-------------------|
| [abi-app](modules/abi-app.md) | Knowledge | 3D filesystem graph — your entire machine as RDF |
| [cuas](modules/cuas.md) | Intelligence | Counter-UAS OSINT fusion — spatiotemporal threat graph |
| [gmail](modules/gmail.md) | Communication | AI email triage and bulk management |
| [whisper](modules/whisper.md) | Voice | Local audio transcription — private, on-device |
| [gladia](modules/gladia.md) | Voice | Cloud voice memo transcription from iPhone |
| [qdrant](modules/qdrant.md) | Search | Semantic document search across all local files |
| [wikileaks](modules/wikileaks.md) | OSINT | WikiLeaks document intelligence |
| [personaplex](modules/personaplex.md) | Voice AI | Real-time voice conversation AI |
| [storage](modules/storage.md) | System | macOS disk usage analyzer |
| [aws](modules/aws.md) | Infrastructure | Cloud infra — Neptune graph, S3, Terraform |
| [cursor](modules/cursor.md) | Productivity | Cursor IDE conversation archive |
| [claude](modules/claude.md) | AI Config | Claude + MCP server settings |
| [qonto](modules/financial.md) | Finance | Qonto, N26, Revolut financial data |
| [iphone-jrv](modules/iphone.md) | Personal data | iPhone voice memos and exports |

---

## Quick Start

```bash
# Start the ABI engine
cd .abi && uv run abi stack start

# AIA is accessible at:
# Nexus UI    → http://localhost:3042
# Agent API   → http://localhost:9879
# MCP server  → http://localhost:8000 (for Claude Desktop)
```

---

## Documentation

- [Architecture](architecture/overview.md) — AIA × ABI deep dive
- [Getting Started](guides/getting-started.md) — run AIA in 5 minutes
- [naas-abi Integration](guides/naas-abi-integration.md) — how src/ connects to .abi/
- [Adding a Module](guides/new-module.md) — migrate an existing src/ module to ABI-native
