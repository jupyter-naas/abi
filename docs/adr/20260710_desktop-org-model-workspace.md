# Desktop org/model workspace layout

## Status

Accepted

## Date

2026-07-10

## Context

ABI Desktop needs a canonical way to organize agent instructions, persistent memory, and RDF knowledge per organization and model context. The workspace root may contain multiple organizations (for example a monorepo like `/Users/jrvmac/abi`), and each organization may host multiple model-specific contexts.

## Decision

1. **Path schema**

   ```
   {workspace_root}/{org}/{model}/AGENTS.md
   {workspace_root}/{org}/{model}/MEMORY.md
   {workspace_root}/{org}/{model}/ontology.ttl
   {workspace_root}/{org}/{model}/instances.ttl
   ```

   Organizations are directories directly under `workspace_root`. Model contexts are directories under each org. Infrastructure directories (`.git`, `node_modules`, virtualenvs, caches) are excluded from org discovery.

2. **Settings keys** (SQLite `settings` table via `DesktopStore`)

   - `active_org` — selected organization folder name (default: `default`)
   - `active_model` — selected model context folder name (default: `default`)

   These are separate keys, not a combined `org/model` path string.

3. **Scaffolding**

   - `workspace_layout.scaffold_org_model()` creates missing dirs and template files idempotently.
   - `ensure_workspace()` scaffolds `default/default` on first workspace creation.
   - Settings save and `POST /api/workspace/orgs/{org}/models/{model}/scaffold` also scaffold on demand.

4. **API**

   - `GET /api/workspace/orgs` — list orgs + active org/model
   - `GET /api/workspace/orgs/{org}/models` — list models for an org
   - `POST /api/workspace/orgs/{org}/models/{model}/scaffold` — create templates + load graph
   - `PUT /api/settings` accepts `active_org` and `active_model`

5. **Chat context**

   On `POST /api/chats/{id}/messages`, the server reads `AGENTS.md` and `MEMORY.md` from the active org/model path and prepends them to the harness prompt. The user message stored in SQLite remains the raw user text.

6. **Graph loading**

   `DesktopGraph.load_org_model_context()` loads `ontology.ttl` and `instances.ttl` into a named Oxigraph graph `http://ontology.naas.ai/abi/desktop#context/{org}/{model}`. Switching active context clears the previous context graph before loading the new one. Activity triples (chats/messages) remain in the default graph.

7. **UI**

   Settings → General exposes org/model selectors and a scaffold button. The Code explorer auto-expands the active org/model folders.

## Consequences

- Multiple org/model contexts can coexist inside one git workspace without replacing the workspace root.
- Agent instructions are versionable alongside code when the workspace is a git repo.
- SPARQL queries can target context graphs with `GRAPH <...#context/{org}/{model}> { ... }`.
- Org/model names are restricted to safe path segments (`[A-Za-z0-9][A-Za-z0-9._-]*`).
- Legacy workspaces without org folders continue to work; `default/default` is created automatically.
