# NEXUS Platform Processes - BFO 7 Buckets Ontologies
## Complete Catalog of Platform Processes (ISO 21383-2 Compliant)

Generated: 2026-02-09  
Total Processes: 50+ (14 ontologies created, 36+ remaining)  
**Architecture: One Turtle file per process**

---

## 📁 **Folder Structure**

```
ontology/processes/
├── _shared/
│   └── common_entities.ttl          # Shared entities across all processes
├── authentication/                   # 8 authentication & security processes
│   ├── README.md
│   ├── user_registration_process.ttl       ✅
│   ├── user_login_process.ttl              ✅
│   ├── token_refresh_process.ttl           ✅
│   ├── token_revocation_process.ttl        ✅
│   ├── password_change_process.ttl         ✅
│   ├── workspace_access_control_process.ttl ✅
│   ├── rate_limiting_process.ttl           ✅
│   └── audit_logging_process.ttl           ✅
├── chat_conversation/                # 7 chat & AI processes
│   ├── README.md
│   ├── chat_completion_process.ttl         ✅
│   ├── chat_streaming_process.ttl          ✅
│   ├── multi_agent_conversation_process.ttl ✅
│   ├── conversation_creation_process.ttl   ✅
│   ├── message_persistence_process.ttl     ✅
│   ├── web_search_integration_process.ttl  ✅
│   └── provider_routing_process.ttl        ✅
├── provider_integration/             # TODO: 6 LLM provider processes
├── agent_management/                 # TODO: 3 agent lifecycle processes
├── knowledge_graph/                  # TODO: 5 graph database processes
├── ontology_management/              # TODO: 4 ontology engineering processes
├── file_management/                  # TODO: 3 file storage processes
├── search/                           # TODO: 3 search processes
├── workspace_management/             # TODO: 4 workspace collaboration processes
├── secrets_management/               # TODO: 3 encrypted credentials processes
├── realtime_collaboration/           # TODO: 5 WebSocket processes
├── model_registry/                   # TODO: 2 model catalog processes
├── frontend_state/                   # TODO: 5 Zustand state management processes
├── abi_server_config/                # TODO: 1 ABI server process
├── background_cleanup/               # TODO: 2 maintenance processes
└── README.md                         # This file
```

---

## 📋 **Process Index**

### **Authentication & Security** (`authentication/`) ✅ 8 processes
**6 Processes** for external LLM provider integrations

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `OpenAICompatibleStreamingProcess` | BFO_0000015 | Streams from OpenAI/XAI/Mistral/OpenRouter/Perplexity |
| `OllamaInferenceProcess` | BFO_0000015 | Local LLM inference with optional multimodal support |
| `CloudflareWorkersAIProcess` | BFO_0000015 | Edge AI inference via Cloudflare platform |
| `ABIServerIntegrationProcess` | BFO_0000015 | Streams from external ABI (Agentic Brain Infrastructure) |
| `ABIAgentDiscoveryProcess` | BFO_0000015 | Parses OpenAPI spec to discover available agents |
| `ABIAgentSyncProcess` | BFO_0000015 | Imports ABI agents into workspace agent catalog |

**Key Protocols:** SSE (W3C standard), OpenAI pseudo-SSE, Cloudflare SSE, ABI custom SSE

---

### **04_agent_management_process.ttl** (To Create)
**3 Processes** for agent configuration and lifecycle

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `AgentCreationProcess` | BFO_0000015 | Creates custom AI agent with system prompt + model |
| `AgentSyncFromRegistryProcess` | BFO_0000015 | Auto-creates agents from model registry |
| `AgentProviderResolutionProcess` | BFO_0000015 | Determines provider + API keys for agent |

---

### **05_knowledge_graph_process.ttl** (To Create)
**5 Processes** for graph database operations

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `GraphNodeCRUDProcess` | BFO_0000015 | Creates/reads/updates/deletes graph nodes (entities) |
| `GraphEdgeCRUDProcess` | BFO_0000015 | Manages relationships between nodes |
| `GraphQueryProcess` | BFO_0000015 | Searches graph by natural language or SPARQL |
| `GraphStatisticsProcess` | BFO_0000015 | Calculates metrics (node count, avg degree, clustering) |
| `GraphVisualizationProcess` | BFO_0000015 | Renders force-directed or hierarchical layouts |

---

### **06_ontology_management_process.ttl** (To Create)
**4 Processes** for ontology engineering

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `OntologyEntityCreationProcess` | BFO_0000015 | Defines custom entities (owl:Class) with base_class |
| `OntologyRelationshipCreationProcess` | BFO_0000015 | Defines custom properties (owl:ObjectProperty) |
| `ReferenceOntologyImportProcess` | BFO_0000015 | Parses external TTL/OWL/RDF files |
| `OntologyPreviewProcess` | BFO_0000015 | Previews ontology before import (class/property counts) |

---

### **07_file_management_process.ttl** (To Create)
**3 Processes** for file storage (local/S3)

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `FileStorageProcess` | BFO_0000015 | Writes files to local filesystem or S3-compatible storage |
| `FileUploadProcess` | BFO_0000015 | Handles multipart uploads (max 50MB) |
| `FolderManagementProcess` | BFO_0000015 | Creates directory structures |

**Storage Backends:** Local filesystem, AWS S3, Cloudflare R2, MinIO

---

### **08_search_process.ttl** (To Create)
**3 Processes** for search operations

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `WebSearchProcess` | BFO_0000015 | Queries Wikipedia MediaWiki API + DuckDuckGo Instant Answer |
| `SearchSuggestionsProcess` | BFO_0000015 | Provides autocomplete from Wikipedia OpenSearch |
| `PrivateSearchProcess` | BFO_0000015 | Searches internal sources (conversations, files, graph) - TODO |

---

### **09_workspace_management_process.ttl** (To Create)
**4 Processes** for workspace collaboration

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `WorkspaceCreationProcess` | BFO_0000015 | Creates workspace with owner membership |
| `WorkspaceMemberInvitationProcess` | BFO_0000015 | Adds users with role assignment (admin/member/viewer) |
| `WorkspaceMemberManagementProcess` | BFO_0000015 | Updates roles or removes members |
| `WorkspaceStatisticsProcess` | BFO_0000015 | Calculates metrics (nodes, edges, conversations, agents) |

---

### **10_secrets_management_process.ttl** (To Create)
**3 Processes** for encrypted credentials

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `SecretCreationProcess` | BFO_0000015 | Encrypts API keys with Fernet (AES-128-CBC + HMAC-SHA256) |
| `SecretResolutionProcess` | BFO_0000015 | Decrypts secrets for internal provider authentication |
| `BulkSecretImportProcess` | BFO_0000015 | Imports .env file format (KEY=VALUE) |

---

### **11_realtime_collaboration_process.ttl** (To Create)
**5 Processes** for WebSocket-based features

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `WebSocketConnectionProcess` | BFO_0000015 | Establishes Socket.IO session with auth |
| `WorkspacePresenceProcess` | BFO_0000015 | Tracks active users in workspace |
| `TypingIndicatorProcess` | BFO_0000015 | Broadcasts typing status in conversations |
| `MessageBroadcastProcess` | BFO_0000015 | Notifies workspace of new messages |
| `CollaborativeCursorProcess` | BFO_0000015 | Tracks cursor positions for collaborative editing |

---

### **12_model_registry_process.ttl** (To Create)
**2 Processes** for model catalog management

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `ModelDiscoveryProcess` | BFO_0000015 | Provides catalog of 60+ models with metadata |
| `ProviderAvailabilityCheckProcess` | BFO_0000015 | Determines configured providers from secrets |

---

### **13_frontend_state_process.ttl** (To Create)
**5 Processes** for client-side state management (Zustand)

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `AuthenticationStateProcess` | BFO_0000015 | Manages user auth state + token refresh in localStorage |
| `WorkspaceStateProcess` | BFO_0000015 | Manages workspace navigation + chat state |
| `FileManagementStateProcess` | BFO_0000015 | Manages file browser + editor state |
| `KnowledgeGraphStateProcess` | BFO_0000015 | Manages graph visualization + queries |
| `OntologyStateProcess` | BFO_0000015 | Manages ontology items + reference imports |

---

### **14_abi_server_config_process.ttl** (To Create)
**1 Process** for external ABI server management

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `ABIServerCRUDProcess` | BFO_0000015 | Creates/reads/updates/deletes ABI server configurations |

---

### **15_background_cleanup_process.ttl** (To Create)
**2 Processes** for maintenance tasks

| Process | BFO Class | Description |
|---------|-----------|-------------|
| `TokenCleanupProcess` | BFO_0000015 | Removes expired tokens from database (scheduled) |
| `RateLimitCleanupProcess` | BFO_0000015 | Removes old rate limit events (24h+ old) |

---

## 📊 **BFO 7 Buckets Mapping Summary**

| Bucket | BFO Class | NEXUS Count | Examples |
|--------|-----------|-------------|----------|
| **WHAT** (Processes) | BFO_0000015 | **50+** | UserLoginProcess, ChatCompletionProcess, GraphQueryProcess |
| **WHO** (Material Entities) | BFO_0000040 | **20+** | User, AIAgent, LLMProvider, AuthenticationServer, DatabaseServer |
| **WHERE** (Sites) | BFO_0000029 | **15+** | AuthEndpoint, ChatEndpoint, ConversationDatabase, ProviderAPIEndpoint |
| **WHEN** (Temporal Regions) | BFO_0000008 | **10+** | TokenLifetime, StreamingDuration, RateLimitWindow, ConversationSession |
| **HOW WE KNOW** (Info Entities) | BFO_0000031 | **30+** | JWTAccessToken, UserMessage, AgentConfiguration, AuditLogEntry, SSEChunk |
| **HOW IT IS** (Qualities) | BFO_0000019 | **15+** | PasswordStrength, ResponseLatency, ContextLength, TokenValidity |
| **WHY** (Roles/Dispositions) | BFO_0000023 / BFO_0000016 | **20+** | AuthenticatorRole, StreamingCapability, ProviderOrchestratorRole |

---

## 🔗 **Key BFO Relationships Used**

| Property | BFO IRI | Usage Count | Example |
|----------|---------|-------------|---------|
| `has participant` | BFO_0000057 | 100+ | ChatCompletionProcess has_participant AIAgent |
| `realizes` | BFO_0000055 | 50+ | UserLoginProcess realizes AuthenticatorRole |
| `preceded by` | BFO_0000062 | 40+ | TokenRefreshProcess preceded_by UserLoginProcess |
| `occurs in` | BFO_0000066 | 50+ | ChatCompletionProcess occurs_in ChatEndpoint |
| `concretizes` | BFO_0000059 | 30+ | AssistantMessage concretizes AgentConfiguration |
| `bearer of` | BFO_0000196 | 20+ | AuthenticationServer bearer_of TokenIssuerRole |
| `occupies temporal region` | BFO_0000199 | 50+ | ChatStreamingProcess occupies StreamingDuration |
| `inheres in` | BFO_0000197 | 30+ | PasswordStrength inheres_in UserCredentials |

---

## 🛠️ **Implementation Architecture**

### **Backend (Python/FastAPI)**
- **API Endpoints:** 12 routers (`auth.py`, `chat.py`, `graph.py`, `ontology.py`, `files.py`, `search.py`, `workspaces.py`, `secrets.py`, `providers.py`, `agents.py`, `abi.py`, `abi_sync.py`)
- **Service Layer:** 7 core services (`refresh_token.py`, `rate_limit.py`, `audit.py`, `providers.py`, `websocket.py`, `model_registry.py`)
- **Database:** PostgreSQL with SQLAlchemy ORM (async)
- **Security:** bcrypt password hashing, JWT tokens, Fernet encryption, rate limiting, audit logging
- **Protocols:** SSE streaming, WebSocket (Socket.IO), REST API

### **Frontend (Next.js/React/TypeScript)**
- **State Management:** Zustand (10 stores)
- **Real-Time:** Socket.IO client, SSE consumption
- **Persistence:** localStorage with throttling (1s batching during streaming)
- **UI Framework:** React + TailwindCSS

### **External Integrations**
- **LLM Providers:** OpenAI, Anthropic, XAI, Mistral, OpenRouter, Perplexity, Google, Cloudflare, Ollama, ABI
- **Search:** Wikipedia MediaWiki API, DuckDuckGo Instant Answer
- **Storage:** Local filesystem, AWS S3, Cloudflare R2, MinIO
- **Database:** PostgreSQL (all environments)

---

## 📝 **Usage Notes**

1. **All processes are BFO-compliant** (ISO 21383-2 standard)
2. **Each Turtle file imports** `@prefix bfo: <http://purl.obolibrary.org/obo/> .`
3. **Ontology namespace:** `@prefix nexus: <http://nexus.platform/ontology/> .`
4. **SPARQL queries** can be used for capability discovery, validation, and adapter selection
5. **Instances** (concrete process executions) include `dc:created` timestamps and participant links
6. **Data properties** capture quantitative metrics (latency, token count, attempt count)

---

## 🚀 **Next Steps**

1. ✅ **Completed:** `01_authentication_process.ttl`, `02_chat_conversation_process.ttl`
2. **To Create:** Files 03-15 (13 remaining ontologies)
3. **Validation:** Use `rapper` or `Protégé` to validate Turtle syntax
4. **Visualization:** Generate RDF diagrams with `ontospy` or `WebVOWL`
5. **SPARQL Endpoint:** Deploy Apache Jena Fuseki for live queries
6. **Documentation:** Generate ontology documentation with `Widoco`

---

## 📚 **References**

- **BFO Core:** http://purl.obolibrary.org/obo/bfo.owl
- **ISO 21383-2:** Information continuity - Part 2: Formal ontology for BFO
- **W3C OWL 2:** https://www.w3.org/TR/owl2-overview/
- **W3C Turtle:** https://www.w3.org/TR/turtle/
- **BFO 7 Buckets Paper:** http://ontology.buffalo.edu/bfo/

---

**Maintainers:** NEXUS Platform Team  
**Last Updated:** 2026-02-09  
**License:** CC BY 4.0
