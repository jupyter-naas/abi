# NEXUS Demo Data

This folder contains the seed data for the NEXUS platform. These JSON files define the knowledge graphs, agents, and conversations that demonstrate the platform's capabilities.

## Self-Referential Architecture

**NEXUS models itself in its own knowledge graph.** This means:

1. The platform's components (Chat, Graph, Ontology, API, Database) are graph nodes
2. Agents and their capabilities are graph nodes with relationship edges
3. ABI (the supervisor agent) can **introspect the graph** to understand what exists
4. The demo data you're reading is itself represented in the graph

```
┌─────────────────────────────────────────────────────────────┐
│                    NEXUS Knowledge Graph                    │
│                                                             │
│  ┌─────────────┐      supervises      ┌──────────────┐     │
│  │ ABI Agent   │──────────────────────▶│ AIA Agent    │     │
│  │ (supervisor)│                       │ (assistant)  │     │
│  └──────┬──────┘                       └──────────────┘     │
│         │                                                   │
│         │ has capability                                    │
│         ▼                                                   │
│  ┌──────────────────┐     operates on    ┌──────────────┐  │
│  │ Introspection    │────────────────────▶│ Graph Module │  │
│  │ Capability       │                     └──────────────┘  │
│  └──────────────────┘                                       │
│                                                             │
│  ┌─────────────┐     seeds      ┌──────────────┐           │
│  │ Demo Data   │────────────────▶│ PostgreSQL  │           │
│  │ (graphs/)   │                 └──────────────┘           │
│  └─────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
```

## Folder Structure

```
demo/
├── README.md           # This file
├── users.json          # Demo user accounts
├── workspaces.json     # Workspace definitions
├── agents.json         # AI agent configurations
├── conversations.json  # Sample conversations
└── graphs/             # Named graph files (self-contained)
    ├── nexus.json      # Platform self-model
    ├── aviation.json   # Aviation demo (BFO example)
    └── user.json       # User personal graph
```

## Named Graphs

Each graph is a self-contained JSON file with its own nodes and edges:

```json
{
  "id": "workspace-nexus",
  "name": "Nexus",
  "description": "NEXUS platform knowledge graph",
  "nodes": [...],
  "edges": [...]
}
```

### Nexus Graph (`graphs/nexus.json`)
Contains nodes representing the platform itself:

**Material Entities (WHO)**
- NEXUS Platform, Modules (Chat, Graph, Ontology, Files)
- Backend (FastAPI, PostgreSQL), Frontend (Next.js)
- Agents (ABI, AIA, Content, Growth, Finance, Ontology)

**Processes (WHAT)**
- Chat Request Flow, Graph Query Flow, Database Seeding

**Dispositions (WHY - capabilities)**
- Chat Capability, Query Graph Capability, Introspection Capability

**GDC (HOW WE KNOW)**
- Demo Data Files, BFO 7 Buckets Ontology

### Aviation Graph (`graphs/aviation.json`)
Real-world BFO application showing Flight UA123 from SFO to JFK:
- Aircraft, pilots, airline (Material Entities)
- Flight phases: takeoff, cruise, landing (Processes)
- Airports: SFO, JFK (Sites)
- Times: departure, arrival (Temporal Regions)

### User Graph (`graphs/user.json`)
Personal user graph that can connect to workspace graphs:
- Demo User (Material Entity)
- Interests, goals, session (Dispositions, Roles, Processes)
- Cross-graph edge: User → NEXUS Platform (connects when both visible)

## Multi-Graph Visualization

In the UI, users can toggle visibility of multiple graphs using the Eye icon:
- When only "Nexus" is visible: shows platform graph
- When only "User" is visible: shows user's personal graph  
- When both are visible: graphs merge, showing the connection between User and NEXUS Platform

## Usage

### Seed the database

```bash
cd apps/api
source .venv/bin/activate
python seed.py --reset
```

### Test introspection

After seeding, ABI can answer questions like:
- "What modules does NEXUS have?"
- "What agents are available?"
- "How does the chat flow work?"

Because the answers are in the graph, not hardcoded.

## BFO 7 Buckets

All entities in the graph are categorized using BFO (Basic Formal Ontology):

| Bucket | BFO Category | Question | Examples |
|--------|--------------|----------|----------|
| WHO | Material Entity | Who/what exists? | People, objects, systems |
| WHAT | Process | What happens? | Events, activities |
| WHEN | Temporal Region | When? | Times, durations |
| WHERE | Site | Where? | Locations, workspaces |
| HOW IT IS | Quality | What properties? | Attributes, measurements |
| WHY | Realizable | Why/what can it do? | Roles, dispositions |
| HOW WE KNOW | GDC | How do we know? | Documents, data |

## Adding New Graphs

To add a new graph:

1. Create a new JSON file in `graphs/` (e.g., `my-graph.json`)
2. Define the structure:
   ```json
   {
     "id": "my-graph-id",
     "name": "My Graph",
     "description": "Description of this graph",
     "nodes": [...],
     "edges": [...]
   }
   ```
3. Re-run `python seed.py --reset`

The seed script automatically discovers and loads all `*.json` files in the `graphs/` folder.

## Cross-Graph Edges

Graphs can reference nodes from other graphs in their edges. For example, the User graph has an edge connecting to `node-nexus-platform` which exists in the Nexus graph. When both graphs are visible in the UI, this edge creates a visual connection between them.
