# NEXUS Process Ontologies - Quick Reference
## One Turtle File Per Process Architecture

**Status:** ✅ 15 processes complete (8 auth + 7 chat), 36+ processes remaining  
**Standard:** BFO 7 Buckets (ISO 21383-2)  
**Format:** RDF/Turtle (.ttl files)

---

## 🚀 **Quick Start**

### Import Shared Entities First
```turtle
@prefix nexus: <http://nexus.platform/ontology/> .
owl:imports <http://nexus.platform/ontology/_shared/common_entities> .
```

### Then Import Specific Processes
```turtle
# Authentication
owl:imports <http://nexus.platform/ontology/authentication/user_login_process> .

# Chat
owl:imports <http://nexus.platform/ontology/chat_conversation/chat_completion_process> .
```

### Query Example
```sparql
PREFIX nexus: <http://nexus.platform/ontology/>
PREFIX bfo: <http://purl.obolibrary.org/obo/>

# Find all processes that have a User as participant
SELECT ?process ?processType ?user WHERE {
    ?process bfo:BFO_0000057 ?user .  # has participant
    ?user a nexus:User .
    ?process a ?processType .
    ?processType rdfs:subClassOf bfo:BFO_0000015 .  # process
}

# Find all processes occurring in a specific site
SELECT ?process ?site WHERE {
    ?process bfo:BFO_0000066 ?site .  # occurs in
    ?site a nexus:AuthEndpoint .
}
```

---

## 📁 **Complete Process List**

### ✅ **Authentication** (8 processes)
1. `user_registration_process.ttl` - Creates user accounts with workspace + tokens
2. `user_login_process.ttl` - Authenticates credentials, issues JWT tokens
3. `token_refresh_process.ttl` - Rotates tokens for session continuity
4. `token_revocation_process.ttl` - Invalidates tokens (logout/security)
5. `password_change_process.ttl` - Updates password, revokes sessions
6. `workspace_access_control_process.ttl` - Validates user permissions (RBAC)
7. `rate_limiting_process.ttl` - Prevents brute force attacks
8. `audit_logging_process.ttl` - Records security events for compliance

### ✅ **Chat & Conversation** (7 processes)
1. `chat_completion_process.ttl` - Generates AI responses (non-streaming)
2. `chat_streaming_process.ttl` - Streams tokens via SSE
3. `multi_agent_conversation_process.ttl` - Manages multi-agent dialogue
4. `conversation_creation_process.ttl` - Creates conversation entities
5. `message_persistence_process.ttl` - Stores messages in database
6. `web_search_integration_process.ttl` - Injects search results as context
7. `provider_routing_process.ttl` - Resolves LLM provider from agent config

### 🔄 **Provider Integration** (6 processes - TODO)
1. `openai_compatible_streaming_process.ttl` - OpenAI/XAI/Mistral/OpenRouter/Perplexity
2. `ollama_inference_process.ttl` - Local LLM with multimodal support
3. `cloudflare_workers_ai_process.ttl` - Edge AI inference
4. `abi_server_integration_process.ttl` - External ABI streaming
5. `abi_agent_discovery_process.ttl` - Parses OpenAPI for agents
6. `abi_agent_sync_process.ttl` - Imports ABI agents to workspace

### 🤖 **Agent Management** (3 processes - TODO)
1. `agent_creation_process.ttl` - Creates custom AI agents
2. `agent_sync_from_registry_process.ttl` - Auto-creates agents from model registry
3. `agent_provider_resolution_process.ttl` - Determines provider + API keys

### 🕸️ **Knowledge Graph** (5 processes - TODO)
1. `graph_node_crud_process.ttl` - Creates/reads/updates/deletes entities
2. `graph_edge_crud_process.ttl` - Manages relationships
3. `graph_query_process.ttl` - Searches graph (NL or SPARQL)
4. `graph_statistics_process.ttl` - Calculates metrics (degree, clustering)
5. `graph_visualization_process.ttl` - Renders force-directed layouts

### 🧬 **Ontology Management** (4 processes - TODO)
1. `ontology_entity_creation_process.ttl` - Defines custom entities (owl:Class)
2. `ontology_relationship_creation_process.ttl` - Defines properties (owl:ObjectProperty)
3. `reference_ontology_import_process.ttl` - Parses external TTL/OWL/RDF
4. `ontology_preview_process.ttl` - Previews before import

### 📁 **File Management** (3 processes - TODO)
1. `file_storage_process.ttl` - Writes to local/S3
2. `file_upload_process.ttl` - Handles multipart uploads (50MB max)
3. `folder_management_process.ttl` - Creates directory structures

### 🔍 **Search** (3 processes - TODO)
1. `web_search_process.ttl` - Queries Wikipedia + DuckDuckGo
2. `search_suggestions_process.ttl` - Autocomplete from Wikipedia OpenSearch
3. `private_search_process.ttl` - Searches conversations/files/graph

### 🏢 **Workspace Management** (4 processes - TODO)
1. `workspace_creation_process.ttl` - Creates workspace with owner
2. `workspace_member_invitation_process.ttl` - Adds users with roles
3. `workspace_member_management_process.ttl` - Updates roles or removes members
4. `workspace_statistics_process.ttl` - Calculates metrics

### 🔐 **Secrets Management** (3 processes - TODO)
1. `secret_creation_process.ttl` - Encrypts API keys (Fernet AES-128-CBC + HMAC)
2. `secret_resolution_process.ttl` - Decrypts for internal use
3. `bulk_secret_import_process.ttl` - Imports .env files

### 🔄 **Real-Time Collaboration** (5 processes - TODO)
1. `websocket_connection_process.ttl` - Establishes Socket.IO session
2. `workspace_presence_process.ttl` - Tracks active users
3. `typing_indicator_process.ttl` - Broadcasts typing status
4. `message_broadcast_process.ttl` - Notifies of new messages
5. `collaborative_cursor_process.ttl` - Tracks cursor positions

### 📚 **Model Registry** (2 processes - TODO)
1. `model_discovery_process.ttl` - Provides 60+ model catalog
2. `provider_availability_check_process.ttl` - Determines configured providers

### 💻 **Frontend State** (5 processes - TODO)
1. `authentication_state_process.ttl` - Manages auth state + token refresh (Zustand)
2. `workspace_state_process.ttl` - Manages workspace navigation + chat
3. `file_management_state_process.ttl` - Manages file browser + editor
4. `knowledge_graph_state_process.ttl` - Manages graph visualization
5. `ontology_state_process.ttl` - Manages ontology items + imports

### 🖥️ **ABI Server Config** (1 process - TODO)
1. `abi_server_crud_process.ttl` - Creates/reads/updates/deletes ABI configs

### 🧹 **Background Cleanup** (2 processes - TODO)
1. `token_cleanup_process.ttl` - Removes expired tokens (scheduled)
2. `rate_limit_cleanup_process.ttl` - Removes old rate limit events

---

## 🎯 **BFO 7 Buckets Quick Reference**

Every process ontology follows this structure:

| Bucket | BFO Class | Meaning | Example |
|--------|-----------|---------|---------|
| **WHAT** | BFO_0000015 | Process itself | `UserLoginProcess` |
| **WHO** | BFO_0000040 | Material entities (participants) | `User`, `AuthenticationServer` |
| **WHERE** | BFO_0000029 | Sites (locations) | `AuthEndpoint`, `SecureDatabase` |
| **WHEN** | BFO_0000008 | Temporal regions | `TokenLifetime`, `RateLimitWindow` |
| **HOW WE KNOW** | BFO_0000031 | Information entities | `JWTAccessToken`, `UserMessage` |
| **HOW IT IS** | BFO_0000019 | Qualities | `PasswordStrength`, `ResponseLatency` |
| **WHY** | BFO_0000023 / BFO_0000016 | Roles & Dispositions | `AuthenticatorRole`, `StreamingCapability` |

### Key BFO Relationships

| Property | BFO IRI | Example |
|----------|---------|---------|
| has participant | `bfo:BFO_0000057` | Process → User |
| realizes | `bfo:BFO_0000055` | Process → Role |
| preceded by | `bfo:BFO_0000062` | TokenRefresh → UserLogin |
| occurs in | `bfo:BFO_0000066` | Process → Site |
| concretizes | `bfo:BFO_0000059` | Token → Credentials |
| bearer of | `bfo:BFO_0000196` | Server → Role |
| occupies temporal region | `bfo:BFO_0000199` | Process → Temporal |
| inheres in | `bfo:BFO_0000197` | Quality → Entity |

---

## 🛠️ **Development Tools**

### Generate New Process Ontologies
```bash
cd /Users/jrvmac/nexus/ontology
python3 scripts/generate_process_ontologies.py
```

### Validate Turtle Syntax
```bash
# Using rapper (install: brew install raptor)
rapper -i turtle -o ntriples authentication/user_login_process.ttl

# Using Apache Jena riot
riot --validate authentication/user_login_process.ttl
```

### Visualize Ontology
```bash
# Using ontospy
ontospy gendocs authentication/user_login_process.ttl -o docs/

# Using WebVOWL
# Upload to: http://vowl.visualdataweb.org/webvowl.html
```

### Query with SPARQL
```bash
# Start Apache Jena Fuseki
fuseki-server --loc=processes /nexus

# Query at http://localhost:3030/nexus/sparql
```

---

## 📖 **Documentation**

- **Main Index:** `README.md` (this file)
- **Auth Processes:** `authentication/README.md`
- **Chat Processes:** `chat_conversation/README.md`
- **Shared Entities:** `_shared/common_entities.ttl`
- **BFO 7 Buckets:** `../BFO7Buckets.ttl`
- **Provider Alignment:** `../../docs/ONTOLOGY_PROVIDER_ALIGNMENT.md`
- **SSE Standards:** `../../docs/SSE_STREAMING_STANDARDS.md`

---

**Last Updated:** 2026-02-09  
**Maintainers:** NEXUS Platform Team  
**License:** CC BY 4.0
