# NEXUS Essentials

One-page reference for everything you need to know.

## Architecture

```
User → Next.js (3000) → FastAPI (8000) → PostgreSQL (5432)
                            ↓
                    AI Providers (OpenAI, Claude, etc.)
```

## Database Schema (Core Tables)

```sql
users                 # Who can login
organizations         # Companies
organization_members  # Who belongs to which org
workspaces           # Projects/teams within orgs
workspace_members    # Who has access to which workspace
agent_configs        # AI agents (model + prompt + settings)
conversations        # Chat threads
messages             # Individual chat messages
inference_servers    # Custom AI endpoints (Ollama, ABI, etc.)
secrets              # Encrypted API keys
graph_nodes          # Knowledge graph nodes
graph_edges          # Knowledge graph relationships
```

## API Endpoints (Most Used)

```
POST   /api/auth/login                 # Login
GET    /api/auth/me                    # Current user
GET    /api/workspaces                 # List workspaces
GET    /api/agents/?workspace_id=...   # List agents
POST   /api/chat/stream                # Send message (SSE)
GET    /api/conversations/             # List conversations
POST   /api/conversations/             # Create conversation
```

Full reference: http://localhost:8000/docs

## Environment Variables (Required)

```bash
# Backend (.env or apps/api/.env)
DATABASE_URL=postgresql+asyncpg://nexus:nexus@localhost:5432/nexus
SECRET_KEY=your-secret-key-min-32-chars
CORS_ORIGINS_STR=http://localhost:3000

# Optional (AI providers)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## State Management (Frontend)

```typescript
// Zustand stores (apps/web/src/stores/)
useAuthStore()        // User, login, logout
useWorkspaceStore()   // Current workspace
useAgentStore()       // Available agents
useConversationStore() // Chat history
useServerStore()      // Inference servers
```

## Streaming Response Format

NEXUS uses Server-Sent Events (SSE):

```javascript
// Frontend
const eventSource = new EventSource('/api/chat/stream');

eventSource.addEventListener('token', (e) => {
  const data = JSON.parse(e.data);
  console.log(data.content); // "Hello", " ", "world"
});

eventSource.addEventListener('done', (e) => {
  const data = JSON.parse(e.data);
  console.log(data.message_id); // Save to DB
  eventSource.close();
});
```

**Event Types:**
- `token` - Text chunk
- `thinking` - Chain-of-thought reasoning
- `tool_call` - Function invocation
- `link` - URL reference
- `file` - Attachment
- `error` - Something failed
- `done` - Stream complete

## Provider Protocols (See ontology/)

**OpenAI:** Custom JSON-per-line (not true SSE)
```
data: {"content": "Hello"}
data: {"content": " world"}
```

**Anthropic:** W3C SSE with event types
```
event: content_block_delta
data: {"delta": {"text": "Hello"}}
```

**ABI/Naas:** Strict W3C SSE (multi-line data)
```
event: ai_message
data: First line
data: Second line
data: https://example.com

```

NEXUS adapters normalize all formats to unified `StreamEvent` objects.

## Database Migrations

Migrations auto-run on API startup from `apps/api/migrations/*.sql`

**Create new migration:**
```bash
# Create: apps/api/migrations/0023_add_field.sql
ALTER TABLE users ADD COLUMN timezone VARCHAR(50);
```

**Migrations are idempotent** (use `IF NOT EXISTS`).

## Authentication Flow

1. User submits email/password → `POST /api/auth/login`
2. Backend validates → Returns JWT `access_token` + `refresh_token`
3. Frontend stores tokens in `localStorage`
4. All requests include `Authorization: Bearer <access_token>`
5. Token expires (24h) → Use `refresh_token` to get new `access_token`

## Workspaces & Multi-tenancy

Everything is scoped to workspaces:
- Agents belong to workspace
- Conversations belong to workspace
- Users have roles per workspace (owner/admin/member)
- Secrets are workspace-scoped

**Switching workspaces = switching context** (all data filtered by `workspace_id`).

## Adding AI Providers

1. **Configure server** (UI: Settings → Servers):
   - Type: OpenAI / Ollama / ABI
   - Endpoint URL
   - Health/Models paths

2. **Add API key** (Settings → Secrets):
   - Name: `OPENAI_API_KEY`
   - Value: `sk-...`

3. **Sync models** (Settings → Agents):
   - Click "Sync Agents"
   - Select source (Model Registry or ABI server)

4. **Enable agents** (toggle on)

5. **Chat** (select agent from dropdown)

## Knowledge Graph

Optional feature for entity/relationship tracking:

```typescript
// Nodes = Entities (users, docs, concepts)
// Edges = Relationships (knows, references, depends_on)

// API
POST /api/graph/nodes/
POST /api/graph/edges/
GET  /api/graph/workspaces/{id}
```

## Testing

```bash
make test              # All tests
cd apps/web && pnpm test        # Frontend only
cd apps/api && uv run pytest    # Backend only
```

## Deployment Checklist

```bash
# Production .env
DEBUG=false
SECRET_KEY=<strong-random-32-chars>
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/nexus
CORS_ORIGINS_STR=https://your-domain.com

# Database
# Use managed PostgreSQL (AWS RDS, DigitalOcean, etc.)
# Enable SSL, backups, monitoring

# Containers
docker-compose up -d  # Or Kubernetes/ECS/Cloud Run

# Reverse proxy (Nginx/Caddy)
# - HTTPS/SSL (Let's Encrypt)
# - Rate limiting
# - Static file serving

# Monitoring
# - Health check: GET /health
# - Logs: docker-compose logs -f
# - Metrics: Prometheus/Grafana (optional)
```

## Common Patterns

**Fetch with auth:**
```typescript
const response = await fetch('/api/endpoint', {
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});
```

**Database query (backend):**
```python
from sqlalchemy import select
result = await db.execute(select(User).where(User.email == email))
user = result.scalar_one_or_none()
```

**Add new API endpoint:**
```python
# apps/api/app/api/endpoints/my_feature.py
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/my-endpoint")
async def get_data(user = Depends(get_current_user_required)):
    return {"data": "value"}

# Register in apps/api/app/main.py
app.include_router(my_feature.router, prefix="/api/my-feature")
```

## Performance Tips

- **Database:** Add indexes on frequently queried columns
- **Frontend:** Use React.memo() for expensive components
- **API:** Enable Redis caching for repeated queries
- **Streaming:** Keep connections alive with SSE keep-alive comments

## Security Hardening

```bash
# Strong secrets
openssl rand -hex 32  # Generate SECRET_KEY

# Database
# - Strong password
# - No public access
# - SSL enabled

# Rate limiting (already built-in)
# - Login: 5/min
# - Chat: 20/min
# - API: 100/min

# HTTPS only in production
# No DEBUG=true in production
# Review SECURITY.md
```

## File Structure Explained

```
apps/api/
  app/
    api/endpoints/     # Routes (workspaces.py, agents.py, chat.py)
    core/              # Config, database, auth
    services/          # Business logic
    models.py          # SQLAlchemy ORM models
    main.py            # FastAPI app + CORS + routes
  migrations/          # SQL files (auto-run on startup)
  uploads/            # User-uploaded files (logos, avatars)

apps/web/
  src/
    app/              # Next.js pages (file-based routing)
      workspace/[workspaceId]/  # Workspace pages
      auth/                     # Login/register
    components/       # React components
      chat/          # Chat interface
      settings/      # Settings panels
      shell/         # Layout (header, sidebar)
    stores/          # Zustand state management
    lib/            # Utilities, API clients
```

## Ontology (Advanced)

NEXUS uses BFO (Basic Formal Ontology) to model AI providers:

**7 Buckets:**
1. **Process** (WHAT) = StreamEvent types (content, thinking, tool_call)
2. **Temporal** (WHEN) = Event timestamps, ordering
3. **Material Entity** (WHO) = Providers, models, agents
4. **Site** (WHERE) = API endpoints, workspaces
5. **Information** (HOW WE KNOW) = Protocols (W3C SSE, OpenAI format)
6. **Quality** (HOW IT IS) = Latency, token count
7. **Role/Disposition** (WHY) = Capabilities (vision, function calling)

**Why?** Enables SPARQL queries for provider discovery, capability validation, adapter selection.

**Details:** See [ontology/research/](../ontology/research/) for BFO/RDF specifications.

## Troubleshooting (Top 5)

1. **Database won't start:** `docker ps` → `docker-compose down -v && docker-compose up -d postgres`
2. **CORS errors:** Check `CORS_ORIGINS_STR` in `.env` includes frontend URL
3. **401 Unauthorized:** Token expired → Logout/login or implement refresh
4. **Port in use:** `lsof -i :3000` or `:8000` → `kill -9 <PID>`
5. **Migrations fail:** Check sequential numbering in `migrations/` folder

Full guide: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)


