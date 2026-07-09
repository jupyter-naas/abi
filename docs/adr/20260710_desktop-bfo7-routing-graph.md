# Desktop BFO7 routing knowledge graph

## Status

Accepted

## Date

2026-07-10

## Context

ABI Desktop already scaffolds per org/model `ontology.ttl` and `instances.ttl` files and loads them into an embedded Oxigraph store. Chat prompts prepend `AGENTS.md` and `MEMORY.md`, but agent selection still comes only from SQLite settings (`chat_agent`, `code_agent`). Nexus ships BFO7 bucket ontologies that classify processes, agents, and documents along seven BFO continuant/occurrent buckets. The desktop app must stay importable without `naas_abi` / `naas_abi_core`, yet still benefit from the same ontology base for routing hints.

## Decision

1. **System ontology config**

   - `desktop_config.resolve_system_ontology_paths()` resolves TTL files in this order:
     - `ABI_DESKTOP_SYSTEM_ONTOLOGY_PATHS` (explicit override)
     - bundled `ontologies/desktop-routing.ttl`
     - repo or bundled `BFO7BucketsProcessOntology.ttl`
   - Optional full `BFO7Buckets.ttl` is discovered when present in the repo; bundled copy is not required for v1.

2. **Graph loading**

   - `DesktopGraph.load_system_ontology()` loads system TTL into named graph `http://ontology.naas.ai/abi/desktop#system`.
   - `load_org_model_context()` always ensures the system graph is loaded, then loads org/model `ontology.ttl` and `instances.ttl` into `http://ontology.naas.ai/abi/desktop#context/{org}/{model}`.

3. **Routing vocabulary**

   Shared classes in `ontologies/desktop-routing.ttl`:

   - `abid:SectionRoute` with `abid:forSection`, `abid:harnessAgent`, `abid:mapsToBfoProcess`
   - `abid:Organization`, `abid:ModelContext`, `abid:ContextDocument`

   Per org/model scaffold templates declare section route subclasses and seed instances:

   - chat → `plan` agent, maps to `bfo:BFO_0000015` (process / WHAT)
   - code → `build` agent, maps to `bfo:BFO_0000015`
   - `AGENTS.md` and `MEMORY.md` as `ContextDocument` individuals

4. **SPARQL routing query**

   ```sparql
   PREFIX abid: <http://ontology.naas.ai/abi/desktop#>

   SELECT ?agent ?bucketLabel WHERE {
     GRAPH <http://ontology.naas.ai/abi/desktop#context/{org}/{model}> {
       ?route abid:forSection ?section ;
              abid:harnessAgent ?agent .
       FILTER(?section = "chat")
       OPTIONAL { ?route abid:mapsToBfoProcess ?bucket . }
     }
     OPTIONAL {
       GRAPH <http://ontology.naas.ai/abi/desktop#system> {
         ?bucket rdfs:label ?bucketLabel .
       }
     }
   }
   LIMIT 1
   ```

5. **Chat send wiring (v1)**

   On `POST /api/chats/{id}/messages`:

   - `graph.resolve_route_agent(active_org, active_model, section)` overrides settings when instances define a route.
   - `graph.build_routing_prompt_hint(...)` prepends a short routing block to the harness prompt (stored user message stays raw).

## Consequences

- Routing is data-driven: editing `instances.ttl` changes agent selection without code changes.
- BFO7 process bucket labels appear in prompts as lightweight context for the harness.
- Bundle stays lean: only routing vocab + process ontology are vendored under `desktop/ontologies/`.
- `owl:imports` in scaffolded ontologies document intent; Oxigraph loads explicit file paths, not remote imports.
- Iteration 2 enriched instances (distinct BFO7 buckets, model URI, harness, model hints), added `resolve_route()`, wired model hints on send, and surfaced active routing in `/api/health` + Graph UI.
- Iteration 3 can add per-tool routes, settings↔TTL sync, and a seven-bucket visualization.

## Related

- `docs/adr/20260710_desktop-org-model-workspace.md`
