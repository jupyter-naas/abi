# seed.py (NEXUS Database Seed Script)

## What it is
- An async database seeding script that loads demo data from JSON files into a PostgreSQL database using SQLAlchemy.
- Intended for local/dev environments to quickly populate core tables (users, orgs, workspaces, memberships, conversations, graphs).
- Creates demo users with a shared password: `nexus2026`.

## Public API
> This file is primarily a CLI script, but the following functions are importable and usable programmatically.

- `load_json(filename: str) -> list[dict]`
  - Loads a JSON file from the `demo/` directory; prints a warning and returns `[]` if missing.

- `seed_users(conn) -> None` *(async)*
  - Inserts users from `demo/users.json`.
  - Hashes the shared demo password using `bcrypt`.
  - Also inserts optional profile fields: `avatar`, `company`, `role`, `bio`.

- `seed_organizations(conn) -> None` *(async)*
  - Inserts organizations from `demo/organizations.json`.
  - Inserts organization memberships from `demo/org_memberships.json` into `organization_members` with IDs like `om-{org_id}-{user_id}`.

- `seed_workspaces(conn) -> None` *(async)*
  - Inserts workspaces from `demo/workspaces.json`.
  - Links workspaces to organizations via `workspace_ids` listed in `demo/organizations.json`.
  - Inserts optional theme fields (with a default `primary_color` of `#22c55e` if missing).

- `seed_memberships(conn) -> None` *(async)*
  - Inserts workspace memberships from `demo/memberships.json` into `workspace_members` with IDs like `wm-{workspace_id}-{user_id}`.

- `seed_agents(conn) -> None` *(async)*
  - Inserts demo agents from `demo/agents.json` into `agent_configs` (defaults to `provider="ollama"` and `model_id="qwen3-vl:2b"` if not specified).
  - Ensures each workspace has at least one enabled Ollama agent.
  - **Note:** `seed_all()` currently does **not** call this (it is commented out).

- `seed_conversations(conn) -> None` *(async)*
  - Inserts conversations from `demo/conversations.json` and nested messages into `messages`.
  - Stores `metadata` as JSON text when provided.

- `seed_graphs(conn) -> None` *(async)*
  - Loads graph JSON files from `demo/graphs/` matching `world_people_org_*.json`.
  - Deletes existing `graph_nodes`/`graph_edges` for `workspace_id = graph_id` before inserting, to prevent accumulation.
  - Uses the graph file’s `id` (or filename stem) as `workspace_id`.

- `seed_all() -> None` *(async)*
  - Runs seeding steps in foreign-key-safe order:
    1. users
    2. organizations + org members
    3. workspaces
    4. workspace members
    5. conversations + messages
    6. graphs
  - Optionally links an ontology reference (“BFO 7 Buckets”) to all workspaces by inserting rows into `ontologies` if the TTL file is readable.
  - Validates that `users`, `organizations`, and `workspaces` are non-empty after seeding; raises `RuntimeError` if not.

- `print_stats() -> None` *(async)*
  - Prints row counts for a fixed list of tables when they exist.

- `print_access_matrix() -> None`
  - Prints a static “DEMO ACCESS MATRIX” including org login routes and the shared password.

- `ensure_seed_data() -> bool` *(async)*
  - Initializes DB if needed, checks `users` count, seeds only if empty.
  - Returns `True` if seeding ran, `False` if skipped.

- `main()` *(async)*
  - CLI entry point.
  - Supports `--reset` to truncate demo tables before seeding.

## Configuration/Dependencies
- **Database layer (project-specific):**
  - `async_engine`, `init_db`, `table_exists`, `get_row_count` imported from `app.core.database`
- **Timezone helper:**
  - `UTC` imported from `naas_abi.apps.nexus.apps.api.app.core.datetime_compat`
- **External packages:**
  - `sqlalchemy` (uses `text()` and async execution)
  - `bcrypt` (required for `seed_users`)
- **Demo data paths:**
  - Demo directory is resolved as: `.../demo` relative to this file:
    - `DEMO_DIR = Path(__file__).parent.parent.parent / "demo"`
  - Graph files are under: `demo/graphs/`
  - Ontology TTL file path: `.../ontology/BFO7Buckets.ttl`

## Usage

### Run as a script (CLI)
```bash
python libs/naas-abi/naas_abi/apps/nexus/apps/api/seed.py
```

### Reset (truncate) then seed
```bash
python libs/naas-abi/naas_abi/apps/nexus/apps/api/seed.py --reset
```

### Programmatic usage (async)
```python
import asyncio
from naas_abi.apps.nexus.apps.api.seed import ensure_seed_data

async def run():
    await ensure_seed_data()

asyncio.run(run())
```

## Caveats
- `--reset` performs destructive truncation with `TRUNCATE ... RESTART IDENTITY CASCADE` and temporarily sets `session_replication_role = 'replica'`.
- Seeding assumes required tables already exist (or `init_db()` is called when `users` table is missing).
- Graph seeding deletes existing graph data for `workspace_id == graph_id` for each loaded graph file.
- `seed_agents()` exists but is not invoked by `seed_all()` in the current code (commented out).
- Demo password is hard-coded (`nexus2026`) and intended only for local development.
