# NEXUS API Documentation

Complete API reference for the NEXUS platform.

## Base URL

**Development:** `http://localhost:8000`  
**Production:** `https://api.yourdomain.com`

**Interactive Docs:** `/docs` (Swagger UI)  
**OpenAPI Schema:** `/openapi.json`

## Authentication

NEXUS uses JWT (JSON Web Tokens) for authentication.

### Obtaining Tokens

**Endpoint:** `POST /api/auth/login`

**Request:**
```json
{
  "email": "alice@example.com",
  "password": "nexus2026"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user-alice",
    "email": "alice@example.com",
    "name": "Alice Johnson",
    "avatar": "/uploads/avatars/alice.png"
  }
}
```

### Using Tokens

Include the access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

**Example (curl):**
```bash
curl http://localhost:8000/api/workspaces \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Example (JavaScript):**
```javascript
fetch('http://localhost:8000/api/workspaces', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
})
```

### Refreshing Tokens

Access tokens expire after 24 hours. Use the refresh token to get a new one.

**Endpoint:** `POST /api/auth/refresh`

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "access_token": "new_token_here",
  "refresh_token": "new_refresh_token_here",
  "token_type": "bearer"
}
```

## Core Endpoints

### Health Check

Check API health status.

**Endpoint:** `GET /health`

**Authentication:** Not required

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected"
}
```

---

## Users

### Get Current User

**Endpoint:** `GET /api/auth/me`

**Authentication:** Required

**Response:**
```json
{
  "id": "user-alice",
  "email": "alice@example.com",
  "name": "Alice Johnson",
  "avatar": "/uploads/avatars/alice.png",
  "default_workspace": "workspace-platform",
  "created_at": "2026-01-15T10:00:00Z"
}
```

### Update User Profile

**Endpoint:** `PATCH /api/auth/me`

**Authentication:** Required

**Request:**
```json
{
  "name": "Alice M. Johnson",
  "email": "alice.johnson@example.com"
}
```

**Response:** Updated user object

### Upload Avatar

**Endpoint:** `POST /api/auth/upload-avatar`

**Authentication:** Required

**Content-Type:** `multipart/form-data`

**Request:**
```
file: <image file>
```

**Response:**
```json
{
  "avatar_url": "/uploads/avatars/abc123.png",
  "filename": "abc123.png"
}
```

**Constraints:**
- Max size: 2MB
- Formats: PNG, JPG, JPEG, GIF, WebP

---

## Organizations

### List Organizations

**Endpoint:** `GET /api/organizations`

**Authentication:** Required

**Response:**
```json
[
  {
    "id": "org-techcorp",
    "name": "TechCorp Inc",
    "slug": "techcorp",
    "logo_url": "/uploads/logos/techcorp.png",
    "owner_id": "user-alice"
  }
]
```

### Get Organization

**Endpoint:** `GET /api/organizations/{org_id}`

**Authentication:** Required

**Response:** Single organization object

### Create Organization

**Endpoint:** `POST /api/organizations`

**Authentication:** Required

**Request:**
```json
{
  "name": "My Organization",
  "slug": "my-org"
}
```

**Response:** Created organization object

### Update Organization

**Endpoint:** `PATCH /api/organizations/{org_id}`

**Authentication:** Required (owner/admin)

**Request:**
```json
{
  "name": "Updated Name",
  "theme_primary_color": "#3B82F6"
}
```

**Response:** Updated organization object

### Delete Organization

**Endpoint:** `DELETE /api/organizations/{org_id}`

**Authentication:** Required (owner only)

**Response:** `204 No Content`

---

## Workspaces

### List Workspaces

**Endpoint:** `GET /api/workspaces`

**Authentication:** Required

**Query Parameters:**
- `org_id` (optional): Filter by organization

**Response:**
```json
[
  {
    "id": "workspace-platform",
    "name": "Platform",
    "slug": "platform",
    "description": "Main platform workspace",
    "organization_id": "org-techcorp",
    "owner_id": "user-alice",
    "theme_primary_color": "#3B82F6",
    "theme_accent_color": "#1E40AF",
    "logo_url": "/uploads/logos/workspace.png",
    "created_at": "2026-01-15T10:00:00Z"
  }
]
```

### Get Workspace

**Endpoint:** `GET /api/workspaces/{workspace_id}`

**Authentication:** Required

**Response:** Single workspace object

### Create Workspace

**Endpoint:** `POST /api/workspaces`

**Authentication:** Required

**Request:**
```json
{
  "name": "My Workspace",
  "slug": "my-workspace",
  "organization_id": "org-techcorp",
  "description": "Description here"
}
```

**Response:** Created workspace object

### Update Workspace

**Endpoint:** `PATCH /api/workspaces/{workspace_id}`

**Authentication:** Required (owner/admin)

**Request:**
```json
{
  "name": "Updated Name",
  "theme_primary_color": "#10B981"
}
```

**Response:** Updated workspace object

### Upload Workspace Logo

**Endpoint:** `POST /api/workspaces/{workspace_id}/upload-logo`

**Authentication:** Required (owner/admin)

**Content-Type:** `multipart/form-data`

**Request:**
```
file: <image file>
```

**Response:**
```json
{
  "logo_url": "/uploads/logos/xyz789.png",
  "filename": "xyz789.png"
}
```

**Constraints:**
- Max size: 5MB
- Formats: PNG, JPG, JPEG, GIF, WebP, SVG

### Delete Workspace

**Endpoint:** `DELETE /api/workspaces/{workspace_id}`

**Authentication:** Required (owner only)

**Response:** `204 No Content`

---

## Agents

### List Agents

**Endpoint:** `GET /api/agents/`

**Authentication:** Required

**Query Parameters:**
- `workspace_id`: Filter by workspace (required)

**Response:**
```json
[
  {
    "id": "agent-gpt4",
    "name": "GPT-4 Assistant",
    "description": "OpenAI GPT-4 model",
    "model_id": "gpt-4-turbo-preview",
    "provider": "openai",
    "logo_url": "https://example.com/logo.png",
    "system_prompt": "You are a helpful assistant.",
    "enabled": true,
    "source": "model-registry",
    "workspace_id": "workspace-platform",
    "created_at": "2026-01-15T10:00:00Z"
  }
]
```

### Get Agent

**Endpoint:** `GET /api/agents/{agent_id}`

**Authentication:** Required

**Response:** Single agent object

### Create Agent

**Endpoint:** `POST /api/agents/`

**Authentication:** Required

**Request:**
```json
{
  "name": "Custom Agent",
  "description": "My custom agent",
  "model_id": "gpt-4",
  "provider": "openai",
  "system_prompt": "You are a specialized assistant.",
  "workspace_id": "workspace-platform",
  "enabled": true
}
```

**Response:** Created agent object

### Update Agent

**Endpoint:** `PATCH /api/agents/{agent_id}`

**Authentication:** Required

**Request:**
```json
{
  "name": "Updated Agent Name",
  "enabled": false,
  "system_prompt": "New system prompt"
}
```

**Response:** Updated agent object

### Delete Agent

**Endpoint:** `DELETE /api/agents/{agent_id}`

**Authentication:** Required

**Response:** `204 No Content`

### Sync Agents from Model Registry

**Endpoint:** `POST /api/agents/sync`

**Authentication:** Required

**Query Parameters:**
- `workspace_id`: Target workspace (required)
- `server_id` (optional): Sync from specific ABI server instead of Model Registry

**Response:**
```json
{
  "synced": 5,
  "created": 3,
  "updated": 2,
  "failed": 0,
  "source": "model-registry"
}
```

---

## Conversations

### List Conversations

**Endpoint:** `GET /api/conversations/`

**Authentication:** Required

**Query Parameters:**
- `workspace_id`: Filter by workspace (required)

**Response:**
```json
[
  {
    "id": "conv-123",
    "title": "My Conversation",
    "agent_id": "agent-gpt4",
    "workspace_id": "workspace-platform",
    "user_id": "user-alice",
    "created_at": "2026-01-15T10:00:00Z",
    "updated_at": "2026-01-15T10:05:00Z"
  }
]
```

### Get Conversation

**Endpoint:** `GET /api/conversations/{conversation_id}`

**Authentication:** Required

**Response:** Single conversation object with messages:
```json
{
  "id": "conv-123",
  "title": "My Conversation",
  "agent_id": "agent-gpt4",
  "workspace_id": "workspace-platform",
  "user_id": "user-alice",
  "messages": [
    {
      "id": "msg-1",
      "conversation_id": "conv-123",
      "role": "user",
      "content": "Hello!",
      "created_at": "2026-01-15T10:00:00Z"
    },
    {
      "id": "msg-2",
      "conversation_id": "conv-123",
      "role": "assistant",
      "content": "Hi! How can I help?",
      "created_at": "2026-01-15T10:00:05Z"
    }
  ],
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-01-15T10:05:00Z"
}
```

### Create Conversation

**Endpoint:** `POST /api/conversations/`

**Authentication:** Required

**Request:**
```json
{
  "title": "New Conversation",
  "agent_id": "agent-gpt4",
  "workspace_id": "workspace-platform"
}
```

**Response:** Created conversation object

### Update Conversation

**Endpoint:** `PATCH /api/conversations/{conversation_id}`

**Authentication:** Required

**Request:**
```json
{
  "title": "Updated Title"
}
```

**Response:** Updated conversation object

### Delete Conversation

**Endpoint:** `DELETE /api/conversations/{conversation_id}`

**Authentication:** Required

**Response:** `204 No Content`

### Export Conversation

**Endpoint:** `GET /api/conversations/{conversation_id}/export`

**Authentication:** Required

**Response:** Plain text export:
```
Conversation: My Conversation
Date: 2026-01-15 10:00:00
Agent: GPT-4 Assistant
Workspace: Platform

---

[User - 2026-01-15 10:00:00]
Hello!

[Assistant - 2026-01-15 10:00:05]
Hi! How can I help?
```

---

## Chat

### Send Message (Streaming)

**Endpoint:** `POST /api/chat/stream`

**Authentication:** Required

**Content-Type:** `application/json`

**Request:**
```json
{
  "message": "Hello, how are you?",
  "agent_id": "agent-gpt4",
  "workspace_id": "workspace-platform",
  "conversation_id": "conv-123"
}
```

**Response:** Server-Sent Events (SSE) stream

**Event Types:**

```
event: token
data: {"content": "Hello"}

event: token
data: {"content": "!"}

event: done
data: {"message_id": "msg-456", "conversation_id": "conv-123"}

event: error
data: {"error": "Rate limit exceeded"}
```

**Example (JavaScript):**
```javascript
const eventSource = new EventSource('/api/chat/stream', {
  headers: { 'Authorization': `Bearer ${token}` }
});

eventSource.addEventListener('token', (e) => {
  const data = JSON.parse(e.data);
  console.log(data.content);
});

eventSource.addEventListener('done', (e) => {
  const data = JSON.parse(e.data);
  console.log('Message ID:', data.message_id);
  eventSource.close();
});

eventSource.addEventListener('error', (e) => {
  console.error(JSON.parse(e.data));
  eventSource.close();
});
```

---

## Inference Servers

### List Servers

**Endpoint:** `GET /api/inference-servers/`

**Authentication:** Required

**Query Parameters:**
- `workspace_id`: Filter by workspace (required)

**Response:**
```json
[
  {
    "id": "server-ollama",
    "name": "Ollama",
    "type": "ollama",
    "endpoint": "http://localhost:11434",
    "health_path": "/",
    "models_path": "/api/tags",
    "status": "online",
    "workspace_id": "workspace-platform",
    "created_at": "2026-01-15T10:00:00Z"
  }
]
```

### Get Server

**Endpoint:** `GET /api/inference-servers/{server_id}`

**Authentication:** Required

**Response:** Single server object

### Create Server

**Endpoint:** `POST /api/inference-servers/`

**Authentication:** Required

**Request:**
```json
{
  "name": "My Ollama",
  "type": "ollama",
  "endpoint": "http://localhost:11434",
  "health_path": "/",
  "models_path": "/api/tags",
  "workspace_id": "workspace-platform"
}
```

**Server Types:**
- `ollama` - Local Ollama instance
- `openai` - OpenAI-compatible API
- `abi` - ABI server

**Response:** Created server object

### Update Server

**Endpoint:** `PATCH /api/inference-servers/{server_id}`

**Authentication:** Required

**Request:**
```json
{
  "name": "Updated Name",
  "endpoint": "http://new-endpoint:11434"
}
```

**Response:** Updated server object

### Delete Server

**Endpoint:** `DELETE /api/inference-servers/{server_id}`

**Authentication:** Required

**Response:** `204 No Content`

### Check Server Health

**Endpoint:** `GET /api/inference-servers/{server_id}/health`

**Authentication:** Required

**Response:**
```json
{
  "status": "online",
  "latency_ms": 45,
  "checked_at": "2026-01-15T10:00:00Z"
}
```

---

## Secrets

### List Secrets

**Endpoint:** `GET /api/secrets/`

**Authentication:** Required

**Query Parameters:**
- `workspace_id`: Filter by workspace (required)

**Response:**
```json
[
  {
    "id": "secret-123",
    "name": "OPENAI_API_KEY",
    "value": "***",
    "workspace_id": "workspace-platform",
    "created_at": "2026-01-15T10:00:00Z"
  }
]
```

**Note:** `value` is never returned in full (always masked)

### Create Secret

**Endpoint:** `POST /api/secrets/`

**Authentication:** Required

**Request:**
```json
{
  "name": "MY_API_KEY",
  "value": "sk-1234567890abcdef",
  "workspace_id": "workspace-platform"
}
```

**Response:** Created secret object (value masked)

### Update Secret

**Endpoint:** `PATCH /api/secrets/{secret_id}`

**Authentication:** Required

**Request:**
```json
{
  "value": "new-secret-value"
}
```

**Response:** Updated secret object (value masked)

### Delete Secret

**Endpoint:** `DELETE /api/secrets/{secret_id}`

**Authentication:** Required

**Response:** `204 No Content`

---

## Graph (Knowledge Graph)

### Get Workspace Graph

**Endpoint:** `GET /api/graph/workspaces/{workspace_id}`

**Authentication:** Required

**Response:**
```json
{
  "nodes": [
    {
      "id": "node-1",
      "label": "PostgreSQL Database",
      "type": "database",
      "metadata": {}
    }
  ],
  "edges": [
    {
      "id": "edge-1",
      "source": "node-1",
      "target": "node-2",
      "label": "stores data in",
      "metadata": {}
    }
  ]
}
```

### Create Node

**Endpoint:** `POST /api/graph/nodes/`

**Authentication:** Required

**Request:**
```json
{
  "label": "New Node",
  "type": "entity",
  "workspace_id": "workspace-platform",
  "metadata": {
    "description": "Node description"
  }
}
```

**Response:** Created node object

### Create Edge

**Endpoint:** `POST /api/graph/edges/`

**Authentication:** Required

**Request:**
```json
{
  "source": "node-1",
  "target": "node-2",
  "label": "connects to",
  "workspace_id": "workspace-platform",
  "metadata": {}
}
```

**Response:** Created edge object

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message"
}
```

### HTTP Status Codes

- `200 OK` - Success
- `201 Created` - Resource created
- `204 No Content` - Success with no body
- `400 Bad Request` - Invalid request
- `401 Unauthorized` - Missing or invalid token
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `422 Unprocessable Entity` - Validation error
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### Example Errors

**401 Unauthorized:**
```json
{
  "detail": "Not authenticated"
}
```

**403 Forbidden:**
```json
{
  "detail": "User does not have access to this workspace"
}
```

**422 Validation Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Rate Limiting

NEXUS implements rate limiting to prevent abuse:

- **Login:** 5 requests per minute per IP
- **Chat:** 20 requests per minute per user
- **API:** 100 requests per minute per user

When rate limited, you'll receive:

**Response:** `429 Too Many Requests`
```json
{
  "detail": "Rate limit exceeded. Try again in 30 seconds."
}
```

**Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1642176000
```

---

## Pagination

List endpoints support pagination:

**Query Parameters:**
- `skip` (default: 0): Number of items to skip
- `limit` (default: 50, max: 100): Number of items to return

**Example:**
```
GET /api/conversations/?workspace_id=workspace-platform&skip=0&limit=20
```

**Response includes:**
```json
{
  "items": [...],
  "total": 150,
  "skip": 0,
  "limit": 20
}
```

---

## WebSocket (Coming Soon)

Real-time updates via WebSocket:

**Endpoint:** `ws://localhost:8000/ws`

**Events:**
- `conversation.created`
- `conversation.updated`
- `message.created`
- `agent.updated`

---

## SDKs & Client Libraries

### JavaScript/TypeScript

```typescript
// Already implemented in apps/web/src/lib/api/
import { authApi } from '@/lib/api/auth';
import { workspacesApi } from '@/lib/api/workspaces';

// Login
const { access_token } = await authApi.login({
  email: 'alice@example.com',
  password: 'nexus2026'
});

// Get workspaces
const workspaces = await workspacesApi.getAll();
```

### Python (Coming Soon)

```python
from nexus import NexusClient

client = NexusClient(api_url='http://localhost:8000')
client.login(email='alice@example.com', password='nexus2026')

workspaces = client.workspaces.list()
```

---

## Interactive Documentation

Visit `/docs` when the API is running to explore and test all endpoints interactively using Swagger UI.

**Example:** http://localhost:8000/docs

Features:
- Try out API calls directly
- See request/response schemas
- Authentication built-in
- Code generation for multiple languages

---

## Need Help?

- **GitHub Issues:** [Report bugs](https://github.com/jravenel/nexus/issues)
- **Discussions:** [Ask questions](https://github.com/jravenel/nexus/discussions)
- **Email:** support@naas.ai

---

**Last updated:** February 10, 2026
