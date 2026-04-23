# seed.py (NEXUS Database Seed Script)

## What it is
- An async database seeding script for the NEXUS API demo environment.
- Loads demo data from JSON files under `demo/` into a PostgreSQL database via SQLAlchemy.
- Creates demo users with a shared password (`nexus2026`) and seeds related entities (orgs, workspaces, memberships, agents, conversations, graphs).

## Public API
> This file is primarily a CLI script, but the following functions are importable and usable programmatically.

- `load_json(filename: str) -> list[dict]`
  - Loads `demo/<filename>` and returns parsed JSON, or `[]` if missing (prints a warning).

- `seed_users(conn) -> None` *(async)*
  - Inserts rows into `users` from `demo/users.json`.
  - Hashes a shared demo password using `bcrypt`.
  - Supports optional profile fields: `avatar`, `company`, `role`, `bio`.

- `seed_organizations(conn) -> None` *(async)*
  - Inserts rows into `organizations` from `demo/organizations.json`.
  - Inserts rows into `organization_members` from `demo/org_memberships.json`.

- `seed_workspaces(conn) -> None` *(async)*
  - Inserts rows into `workspaces` from `demo/workspaces.json`.
  - Links workspaces to organizations using `workspace_ids` declared in `demo/organizations.json`.

- `seed_memberships(conn) -> None` *(async)*
  - Inserts rows into `workspace_members` from `demo/memberships.json`.

- `seed_agents(conn) -> None` *(async)*
  - Inserts rows into `agent_configs` from `demo/agents.json`.
  - Defaults missing agent config fields to Ollama provider/model (`provider="ollama"`, `model_id="qwen3-vl:2b"`).
  - Ensures each workspace has at least one enabled agent; if none exists, inserts a default "Qwen3 Vision 2B" agent.

- `seed_conversations(conn) -> None` *(async)*
  - Inserts rows into `conversations` (and nested `messages`) from `demo/conversations.json`.
  - Message `metadata` is JSON-encoded when present.

- `seed_graphs(conn) -> None` *(async)*
  - Loads graph JSON files from `demo/graphs/` matching `world_people_org_*.json`.
  - Clears existing `graph_nodes`/`graph_edges` for each `workspace_id == graph_id` before inserting.
  - Inserts into `graph_nodes` and `graph_edges`.

- `seed_all() -> None` *(async)*
  - Runs all seed steps in foreign-key-safe order.
  - Attempts to link a BFO “7 Buckets” ontology reference to all workspaces (reads `ontology/BFO7Buckets.ttl` and inserts stubs into `ontologies`); failures are caught and logged.
  - Validates that `users`, `organizations`, and `workspaces` are non-empty after seeding; raises `RuntimeError` if not.

- `print_stats() -> None` *(async)*
  - Prints row counts for a fixed list of tables (only if each table exists).

- `print_access_matrix() -> None`
  - Prints a static demo access matrix and login URLs.

- `ensure_seed_data() -> bool` *(async)*
  - Ensures the DB is initialized and demo users exist.
  - If `users` is empty, runs `seed_all()` and returns `True`; otherwise returns `False`.

- `main()` *(async)*
  - CLI entrypoint; supports `--reset` to truncate seed tables before seeding.

## Configuration/Dependencies
- Database/SQLAlchemy:
  - Uses `async_engine`, `init_db`, `table_exists`, `get_row_count` from `app.core.database`.
  - Uses `sqlalchemy.text` and executes raw SQL inserts/truncates.
- Demo data directory:
  - `DEMO_DIR = <this file>/../../../demo`
  - Expected JSON files (depending on what you seed):
    - `users.json`, `organizations.json`, `org_memberships.json`, `workspaces.json`, `memberships.json`, `agents.json`, `conversations.json`
    - `graphs/world_people_org_*.json` (optional)
- Password hashing:
  - `bcrypt` is imported inside `seed_users`.
- Time handling:
  - Uses `UTC` from `naas_abi.apps.nexus.apps.api.app.core.datetime_compat`.
  - Inserts naive timestamps via `datetime.now(UTC).replace(tzinfo=None)`.
- Optional ontology file:
  - Reads `ontology/BFO7Buckets.ttl` relative to repository layout; seeding is skipped on any exception.

## Usage
### CLI
```bash
python libs/naas-abi/naas_abi/apps/nexus/apps/api/seed.py
```

Reset (destructive truncate) then seed:
```bash
python libs/naas-abi/naas_abi/apps/nexus/apps/api/seed.py --reset
```

### Programmatic (async)
```python
import asyncio
from naas_abi.apps.nexus.apps.api.seed import ensure_seed_data

async def run():
    await ensure_seed_data()

asyncio.run(run())
```

## Caveats
- `--reset` truncates tables using `TRUNCATE ... RESTART IDENTITY CASCADE` and temporarily sets `session_replication_role = 'replica'` (PostgreSQL-specific).
- Graph seeding only loads files matching `demo/graphs/world_people_org_*.json` and deletes existing graph rows for each corresponding `workspace_id`.
- Timestamps inserted are naive (timezone removed) even though they originate from UTC.
- The script inserts directly via SQL text statements; schema/table mismatches will error at runtime.
