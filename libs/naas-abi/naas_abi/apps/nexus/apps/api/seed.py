#!/usr/bin/env python3
"""
NEXUS Database Seed Script

Loads demo data from JSON files into the PostgreSQL database.
Creates 5 demo users with a shared password for easy testing.

Usage:
    python seed.py          # Seed database
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import (async_engine, get_row_count, init_db,
                               table_exists)
from sqlalchemy import text

# Demo data directory
DEMO_DIR = Path(__file__).parent.parent.parent / "demo"

# Shared password for all demo users — easy to remember, only for local dev
DEMO_PASSWORD = "nexus2026"


def load_json(filename: str) -> list[dict]:
    """Load a JSON file from the demo directory."""
    path = DEMO_DIR / filename
    if not path.exists():
        print(f"Warning: {filename} not found, skipping")
        return []

    with open(path) as f:
        return json.load(f)


async def seed_users(conn) -> None:
    """Seed users table. All users get the shared demo password.

    Adds optional profile metadata (avatar, company, role, bio)
    so the Account page can display realistic profiles out-of-the-box.
    """
    import bcrypt

    users = load_json("users.json")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    hashed = bcrypt.hashpw(DEMO_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    for user in users:
        await conn.execute(
            text("""
                INSERT INTO users (
                    id,
                    email,
                    name,
                    hashed_password,
                    avatar,
                    company,
                    role,
                    bio,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :email,
                    :name,
                    :hashed_password,
                    :avatar,
                    :company,
                    :role,
                    :bio,
                    :created_at,
                    :updated_at
                )
            """),
            {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "hashed_password": hashed,
                "avatar": user.get("avatar"),
                "company": user.get("company"),
                "role": user.get("role"),
                "bio": user.get("bio"),
                "created_at": now,
                "updated_at": now,
            }
        )

    print(f"  ✓ Seeded {len(users)} users (password: {DEMO_PASSWORD})")


async def seed_organizations(conn) -> None:
    """Seed organizations and organization_members tables."""
    orgs = load_json("organizations.json")
    org_memberships = load_json("org_memberships.json")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for org in orgs:
        await conn.execute(
            text("""
                INSERT INTO organizations (
                    id, name, slug, owner_id,
                    logo_url, logo_rectangle_url, logo_emoji,
                    primary_color, accent_color,
                    background_color, font_family, font_url,
                    login_card_max_width, login_card_padding, login_card_color, login_text_color, login_input_color, login_border_radius, login_bg_image_url,
                    login_footer_text, secondary_logo_url, default_theme,
                    created_at, updated_at
                )
                VALUES (
                    :id, :name, :slug, :owner_id,
                    :logo_url, :logo_rectangle_url, :logo_emoji,
                    :primary_color, :accent_color,
                    :background_color, :font_family, :font_url,
                    :login_card_max_width, :login_card_padding, :login_card_color, :login_text_color, :login_input_color, :login_border_radius, :login_bg_image_url,
                    :login_footer_text, :secondary_logo_url, :default_theme,
                    :created_at, :updated_at
                )
            """),
            {
                "id": org["id"],
                "name": org["name"],
                "slug": org["slug"],
                "owner_id": org["owner_id"],
                "logo_url": org.get("logo_url"),
                "logo_rectangle_url": org.get("logo_rectangle_url"),
                "logo_emoji": org.get("logo_emoji"),
                "primary_color": org.get("primary_color", "#22c55e"),
                "accent_color": org.get("accent_color"),
                "background_color": org.get("background_color"),
                "font_family": org.get("font_family"),
                "font_url": org.get("font_url"),
                "login_card_max_width": org.get("login_card_max_width"),
                "login_card_padding": org.get("login_card_padding"),
                "login_card_color": org.get("login_card_color"),
                "login_text_color": org.get("login_text_color"),
                "login_input_color": org.get("login_input_color"),
                "login_border_radius": org.get("login_border_radius"),
                "login_bg_image_url": org.get("login_bg_image_url"),
                "login_footer_text": org.get("login_footer_text"),
                "secondary_logo_url": org.get("secondary_logo_url"),
                "default_theme": org.get("default_theme"),
                "created_at": now,
                "updated_at": now,
            }
        )

    print(f"  ✓ Seeded {len(orgs)} organizations")

    for m in org_memberships:
        member_id = f"om-{m['organization_id']}-{m['user_id']}"
        await conn.execute(
            text("""
                INSERT INTO organization_members (id, organization_id, user_id, role, created_at)
                VALUES (:id, :organization_id, :user_id, :role, :created_at)
            """),
            {
                "id": member_id,
                "organization_id": m["organization_id"],
                "user_id": m["user_id"],
                "role": m["role"],
                "created_at": now,
            }
        )

    print(f"  ✓ Seeded {len(org_memberships)} organization memberships")


async def seed_workspaces(conn) -> None:
    """Seed workspaces table with organization links and theme fields."""
    workspaces = load_json("workspaces.json")
    orgs = load_json("organizations.json")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Build workspace->org mapping from organizations.json
    ws_to_org = {}
    for org in orgs:
        for ws_id in org.get("workspace_ids", []):
            ws_to_org[ws_id] = org["id"]

    for ws in workspaces:
        org_id = ws_to_org.get(ws["id"])
        await conn.execute(
            text("""
                INSERT INTO workspaces (
                    id, name, slug, owner_id, organization_id,
                    logo_url, logo_emoji, primary_color, accent_color, background_color, sidebar_color, font_family,
                    created_at, updated_at
                )
                VALUES (
                    :id, :name, :slug, :owner_id, :organization_id,
                    :logo_url, :logo_emoji, :primary_color, :accent_color, :background_color, :sidebar_color, :font_family,
                    :created_at, :updated_at
                )
            """),
            {
                "id": ws["id"],
                "name": ws["name"],
                "slug": ws["slug"],
                "owner_id": ws["owner_id"],
                "organization_id": org_id,
                # Optional theme fields
                "logo_url": ws.get("logo_url"),
                "logo_emoji": ws.get("logo_emoji"),
                "primary_color": ws.get("primary_color", "#22c55e"),
                "accent_color": ws.get("accent_color"),
                "background_color": ws.get("background_color"),
                "sidebar_color": ws.get("sidebar_color"),
                "font_family": ws.get("font_family"),
                # Timestamps
                "created_at": now,
                "updated_at": now,
            }
        )

    linked = sum(1 for ws in workspaces if ws["id"] in ws_to_org)
    print(f"  ✓ Seeded {len(workspaces)} workspaces ({linked} linked to organizations)")


async def seed_memberships(conn) -> None:
    """Seed workspace_members from memberships.json."""
    memberships = load_json("memberships.json")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for m in memberships:
        member_id = f"wm-{m['workspace_id']}-{m['user_id']}"
        await conn.execute(
            text("""
                INSERT INTO workspace_members (id, workspace_id, user_id, role, created_at)
                VALUES (:id, :workspace_id, :user_id, :role, :created_at)
            """),
            {
                "id": member_id,
                "workspace_id": m["workspace_id"],
                "user_id": m["user_id"],
                "role": m["role"],
                "created_at": now,
            }
        )

    print(f"  ✓ Seeded {len(memberships)} workspace memberships")


async def seed_agents(conn) -> None:
    """Seed agent_configs table (demo agents) and default Ollama agents.

    - Inserts demo agents from demo/agents.json
    - Ensures each workspace has at least one enabled agent that uses
      the local Ollama model 'qwen3-vl:2b' so chat works out of the box.
    """
    agents = load_json("agents.json")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Insert demo agents, defaulting to Ollama Qwen3 VL if not specified
    for agent in agents:
        await conn.execute(
            text("""
                INSERT INTO agent_configs (
                    id, workspace_id, name, description, icon, system_prompt,
                    provider, model_id, enabled, is_default, created_at, updated_at
                )
                VALUES (
                    :id, :workspace_id, :name, :description, :icon, :system_prompt,
                    :provider, :model_id, :enabled, :is_default, :created_at, :updated_at
                )
            """),
            {
                "id": agent["id"],
                "workspace_id": agent["workspace_id"],
                "name": agent["name"],
                "description": agent.get("description"),
                "icon": agent.get("icon"),
                "system_prompt": agent.get("system_prompt"),
                # If not provided in JSON, default to local Ollama vision model
                "provider": agent.get("provider", "ollama"),
                "model_id": agent.get("model", "qwen3-vl:2b"),
                # Enable demo agents so they appear in the selector by default
                "enabled": True,
                "is_default": True if agent.get("is_default") else False,
                "created_at": now,
                "updated_at": now,
            }
        )

    # Ensure each workspace has at least one enabled Ollama agent
    workspaces = load_json("workspaces.json")
    created_per_ws = 0
    for ws in workspaces:
        ws_id = ws["id"]
        # Skip if an enabled agent already exists in this workspace
        result = await conn.execute(
            text("""
                SELECT 1 FROM agent_configs 
                WHERE workspace_id = :ws AND enabled = true
                LIMIT 1
            """),
            {"ws": ws_id},
        )
        if result.first():
            continue

        await conn.execute(
            text("""
                INSERT INTO agent_configs (
                    id, workspace_id, name, description, icon, system_prompt,
                    provider, model_id, enabled, is_default, created_at, updated_at
                ) VALUES (
                    :id, :workspace_id, :name, :description, :icon, :system_prompt,
                    :provider, :model_id, :enabled, :is_default, :created_at, :updated_at
                )
            """),
            {
                "id": f"agent-qwen3-vl-{ws_id}",
                "workspace_id": ws_id,
                "name": "Qwen3 Vision 2B",
                "description": "Local vision model via Ollama (qwen3-vl:2b)",
                "icon": "sparkles",
                "system_prompt": "You are a helpful AI assistant with vision capabilities.",
                "provider": "ollama",
                "model_id": "qwen3-vl:2b",
                "enabled": True,
                "is_default": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        created_per_ws += 1

    print(f"  ✓ Seeded {len(agents)} demo agents; ensured enabled Ollama agent in {created_per_ws} workspaces")


async def seed_conversations(conn) -> None:
    """Seed conversations and messages tables."""
    conversations = load_json("conversations.json")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    conv_count = 0
    msg_count = 0

    for conv in conversations:
        await conn.execute(
            text("""
                INSERT INTO conversations (id, workspace_id, user_id, title, agent, created_at, updated_at)
                VALUES (:id, :workspace_id, :user_id, :title, :agent, :created_at, :updated_at)
            """),
            {
                "id": conv["id"],
                "workspace_id": conv["workspace_id"],
                "user_id": conv["user_id"],
                "title": conv["title"],
                "agent": conv.get("agent", "aia"),
                "created_at": now,
                "updated_at": now,
            }
        )
        conv_count += 1

        # Seed messages for this conversation
        for msg in conv.get("messages", []):
            await conn.execute(
                text("""
                    INSERT INTO messages (id, conversation_id, role, content, agent, metadata, created_at)
                    VALUES (:id, :conversation_id, :role, :content, :agent, :metadata, :created_at)
                """),
                {
                    "id": msg["id"],
                    "conversation_id": conv["id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "agent": msg.get("agent"),
                    "metadata": json.dumps(msg.get("metadata")) if msg.get("metadata") else None,
                    "created_at": now,
                }
            )
            msg_count += 1

    print(f"  ✓ Seeded {conv_count} conversations with {msg_count} messages")


async def seed_graphs(conn) -> None:
    """Seed graph_nodes and graph_edges tables from named graph files."""
    graphs_dir = DEMO_DIR / "graphs"
    if not graphs_dir.exists():
        print("Warning: demo/graphs/ not found, skipping graphs")
        return

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    total_nodes = 0
    total_edges = 0
    graph_count = 0

    # Process each graph file
    # To avoid demo graphs accumulating noisy data, only load the scoped
    # world_people_org_* graphs by default. This yields clean per-workspace
    # person/org world models that can be overlaid without extra modules.
    for graph_file in sorted(graphs_dir.glob("world_people_org_*.json")):
        with open(graph_file) as f:
            graph_data = json.load(f)

        graph_id = graph_data.get("id", graph_file.stem)
        graph_name = graph_data.get("name", graph_file.stem)

        # Clear any previously-seeded nodes/edges for this workspace graph id to prevent accumulation
        await conn.execute(text("DELETE FROM graph_edges WHERE workspace_id = :wid"), {"wid": graph_id})
        await conn.execute(text("DELETE FROM graph_nodes WHERE workspace_id = :wid"), {"wid": graph_id})

        # Seed nodes
        for node in graph_data.get("nodes", []):
            await conn.execute(
                text("""
                    INSERT INTO graph_nodes (id, workspace_id, type, label, properties, created_at, updated_at)
                    VALUES (:id, :workspace_id, :type, :label, :properties, :created_at, :updated_at)
                """),
                {
                    "id": node["id"],
                    "workspace_id": graph_id,
                    "type": node["type"],
                    "label": node["label"],
                    "properties": json.dumps(node.get("properties", {})),
                    "created_at": now,
                    "updated_at": now,
                }
            )
            total_nodes += 1

        # Seed edges
        for edge in graph_data.get("edges", []):
            await conn.execute(
                text("""
                    INSERT INTO graph_edges (id, workspace_id, source_id, target_id, type, properties, created_at)
                    VALUES (:id, :workspace_id, :source_id, :target_id, :type, :properties, :created_at)
                """),
                {
                    "id": edge["id"],
                    "workspace_id": graph_id,
                    "source_id": edge["source"],
                    "target_id": edge["target"],
                    "type": edge["type"],
                    "properties": json.dumps(edge.get("properties", {})),
                    "created_at": now,
                }
            )
            total_edges += 1

        graph_count += 1
        print(f"  ✓ Loaded graph '{graph_name}' ({len(graph_data.get('nodes', []))} nodes, {len(graph_data.get('edges', []))} edges)")

    print(f"  ✓ Seeded {graph_count} graphs with {total_nodes} nodes and {total_edges} edges total")


async def seed_all() -> None:
    """Seed all tables with demo data."""
    print("\nSeeding database with demo data...")
    print(f"Demo data directory: {DEMO_DIR}\n")

    async with async_engine.begin() as conn:
        # Seed in order (respecting foreign keys)
        await seed_users(conn)
        await seed_organizations(conn)
        await seed_workspaces(conn)
        await seed_memberships(conn)
        await seed_agents(conn)
        await seed_conversations(conn)
        await seed_graphs(conn)
        
        # Load BFO 7 Buckets as a reference ontology item per workspace (simple stub in ontologies table)
        try:
            from pathlib import Path
            ttl_path = Path(__file__).parent.parent.parent / 'ontology' / 'BFO7Buckets.ttl'
            content = ttl_path.read_text(encoding='utf-8')
            import json as _json
            schema_stub = _json.dumps({
                "id": "reference-bfo7",
                "name": "BFO 7 Buckets",
                "format": "ttl",
                "file": "/ontology/BFO7Buckets.ttl",
                "classCount": 7
            })
            # Insert one ontology reference per workspace
            ws_result = await conn.execute(text("SELECT id FROM workspaces"))
            for (ws_id,) in ws_result.fetchall():
                await conn.execute(
                    text("""
                        INSERT INTO ontologies (id, workspace_id, name, description, schema, created_at, updated_at)
                        VALUES (:id, :ws, :name, :desc, :schema, :now, :now)
                    """),
                    {
                        "id": f"ontology-bfo7-{ws_id}",
                        "ws": ws_id,
                        "name": "BFO 7 Buckets",
                        "desc": "Reference ontology loaded by default",
                        "schema": schema_stub,
                        "now": datetime.now(timezone.utc).replace(tzinfo=None),
                    }
                )
            print(f"  ✓ Linked BFO 7 Buckets reference to all workspaces")
        except Exception as e:
            print(f"  ⚠️  Skipped BFO 7 Buckets seeding: {e}")

        # Fail hard if core seed data did not get inserted.
        users_count = int((await conn.execute(text("SELECT COUNT(*) FROM users"))).scalar_one() or 0)
        organizations_count = int((await conn.execute(text("SELECT COUNT(*) FROM organizations"))).scalar_one() or 0)
        workspaces_count = int((await conn.execute(text("SELECT COUNT(*) FROM workspaces"))).scalar_one() or 0)
        if users_count == 0 or organizations_count == 0 or workspaces_count == 0:
            raise RuntimeError(
                "Seed validation failed: expected non-empty core tables after seeding "
                f"(users={users_count}, organizations={organizations_count}, workspaces={workspaces_count}). "
                "Check demo data files and runtime paths."
            )

    print("\n✅ Database seeded successfully!")
    await print_stats()
    print_access_matrix()


async def print_stats() -> None:
    """Print database statistics."""
    print("\nDatabase statistics:")
    tables = ["users", "organizations", "organization_members", "workspaces", "workspace_members", "agent_configs", "conversations", "messages", "graph_nodes", "graph_edges", "workspace_secrets"]

    for table in tables:
        if await table_exists(table):
            count = await get_row_count(table)
            print(f"  {table}: {count} rows")


def print_access_matrix() -> None:
    """Print the user-workspace access matrix for quick reference."""
    print("\n┌──────────────────────────────────────────────────────────────────────────────────┐")
    print("│  DEMO ACCESS MATRIX                                                              │")
    print("│  Password for all users: nexus2026                                               │")
    print("├──────────────────────────────────────────────────────────────────────────────────┤")
    print("│  Organizations:                                                                   │")
    print("│    TechCorp Inc (org-techcorp)           → /org/techcorp/auth/login              │")
    print("│    Global Consulting (org-globalconsulting) → /org/global-consulting/auth/login  │")
    print("│    Innovate Solutions (org-innovate)     → /org/innovate/auth/login              │")
    print("│    Research Lab (org-researchlab)        → /org/research-lab/auth/login          │")
    print("├──────────────────────────────────────────────────────────────────────────────────┤")
    print("│  User                              │ Org (role)         │ Workspaces (role)       │")
    print("├────────────────────────────────────-┼────────────────────┼─────────────────────────┤")
    print("│  alice@example.com                 │ TechCorp (owner)   │ Platform (owner)        │")
    print("│                                    │ ResearchLab (mem)  │ TechCorp (owner)        │")
    print("│                                    │ Innovate (member)  │ Research (member)       │")
    print("│                                    │                    │ Innovate (member)       │")
    print("├────────────────────────────────────-┼────────────────────┼─────────────────────────┤")
    print("│  bob@example.com                   │ TechCorp (admin)   │ Platform (admin)        │")
    print("│                                    │ ResearchLab (mem)  │ TechCorp (admin)        │")
    print("│                                    │                    │ Research (member)       │")
    print("├────────────────────────────────────-┼────────────────────┼─────────────────────────┤")
    print("│  jeremy@example.com                │ TechCorp (admin)   │ Platform (admin)        │")
    print("│                                    │ ResearchLab (mem)  │ TechCorp (admin)        │")
    print("│                                    │ Innovate (member)  │ Research (member)       │")
    print("│                                    │                    │ Innovate (member)       │")
    print("├────────────────────────────────────-┼────────────────────┼─────────────────────────┤")
    print("│  diana@example.com                 │ ResearchLab (own)  │ Research (owner)        │")
    print("│                                    │ Innovate (owner)   │ Innovate (owner)        │")
    print("├────────────────────────────────────-┼────────────────────┼─────────────────────────┤")
    print("│  eve@example.com                   │ GlobalConsulting   │ Consulting (owner)      │")
    print("│                                    │ (owner)            │                         │")
    print("└──────────────────────────────────────────────────────────────────────────────────┘")


async def ensure_seed_data() -> bool:
    """
    Ensure demo seed data exists.

    Returns:
        True if seeding was executed, False if data already existed.
    """
    if not await table_exists("users"):
        await init_db()

    async with async_engine.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM users"))
        user_count = int(result.scalar_one() or 0)

    if user_count > 0:
        print(f"✓ Demo seed check: users already present ({user_count}), skipping seed")
        return False

    print("No users found, running initial demo seed...")
    await seed_all()
    return True


async def main():
    parser = argparse.ArgumentParser(description="NEXUS Database Seed Script")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate demo tables before seeding (destructive)",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("NEXUS Database Seed Script")
    print("=" * 50)

    if not await table_exists("users"):
        print("\nInitializing database...")
        await init_db()

    if args.reset:
        print("\nResetting demo tables (TRUNCATE ... CASCADE)...")
        tables = [
            "graph_edges",
            "graph_nodes",
            "messages",
            "conversations",
            "agent_configs",
            "workspace_members",
            "workspaces",
            "organization_members",
            "organizations",
            "users",
        ]
        async with async_engine.begin() as conn:
            # Temporarily disable FK checks for faster truncation
            await conn.execute(text("SET session_replication_role = 'replica'"))
            try:
                for t in tables:
                    await conn.execute(text(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE"))
            finally:
                await conn.execute(text("SET session_replication_role = 'origin'"))
        print("✓ Tables truncated")

    await seed_all()


if __name__ == "__main__":
    asyncio.run(main())
