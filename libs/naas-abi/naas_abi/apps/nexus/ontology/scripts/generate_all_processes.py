#!/usr/bin/env python3
"""
NEXUS Process Ontology Generator
Generates ALL BFO 7 Buckets compliant Turtle files from codebase analysis.
Each process maps to real Python functions and React components.
"""

from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "processes"

PREFIXES = """@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dc: <http://purl.org/dc/terms/> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix nexus: <http://nexus.platform/ontology/> .
"""

def ttl_string(s: str) -> str:
    """Escape a string for Turtle literals."""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def write_process(folder, filename, label, definition, impl,
                  who, where, when, how_know, how_is, why_roles, why_disps,
                  steps, data_props=None, precedes=None, preceded_by=None):
    """Write a single BFO 7 Buckets process ontology file."""
    outdir = OUTPUT_DIR / folder
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{filename}.ttl"
    
    cls = label.replace(" ", "")
    onto_id = filename
    
    lines = [PREFIXES]
    lines.append(f"""
# ======================================================================
# {label}
# BFO 7 Buckets Compliant (ISO 21383-2)
# ======================================================================

nexus:{onto_id} a owl:Ontology ;
    dc:title "{ttl_string(label)}"@en ;
    dc:description "{ttl_string(definition)}"@en ;
    dc:created "2026-02-09"^^xsd:date ;
    owl:imports <http://ontology.naas.ai/abi/BFO7Buckets> ,
                <http://nexus.platform/ontology/_shared/common_entities> .
""")
    
    # WHAT: Process
    steps_str = "\\n".join(f"{i+1}. {ttl_string(s)}" for i, s in enumerate(steps))
    lines.append(f"""
# ======================================================================
# WHAT: Process (BFO_0000015)
# ======================================================================

nexus:{cls} a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000015 ;
    rdfs:label "{ttl_string(label)}"@en ;
    skos:definition "{ttl_string(definition)}"@en ;
    rdfs:comment "Implements: {ttl_string(impl)}" ;
    skos:example "{steps_str}"@en .
""")
    
    # WHO: Material Entities
    if who:
        lines.append("""# ======================================================================
# WHO: Material Entities (BFO_0000040)
# ======================================================================
""")
        for name, defn in who.items():
            lines.append(f"""nexus:{name} a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000040 ;
    rdfs:label "{ttl_string(name)}"@en ;
    skos:definition "{ttl_string(defn)}"@en .
""")

    # WHERE: Sites
    if where:
        lines.append("""# ======================================================================
# WHERE: Sites (BFO_0000029)
# ======================================================================
""")
        for name, defn in where.items():
            lines.append(f"""nexus:{name} a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000029 ;
    rdfs:label "{ttl_string(name)}"@en ;
    skos:definition "{ttl_string(defn)}"@en .
""")

    # WHEN: Temporal Regions
    if when:
        lines.append("""# ======================================================================
# WHEN: Temporal Regions (BFO_0000008)
# ======================================================================
""")
        for name, defn in when.items():
            lines.append(f"""nexus:{name} a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000008 ;
    rdfs:label "{ttl_string(name)}"@en ;
    skos:definition "{ttl_string(defn)}"@en .
""")

    # HOW WE KNOW: Information Entities (GDC)
    if how_know:
        lines.append("""# ======================================================================
# HOW WE KNOW: Information Entities (BFO_0000031)
# ======================================================================
""")
        for name, defn in how_know.items():
            lines.append(f"""nexus:{name} a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000031 ;
    rdfs:label "{ttl_string(name)}"@en ;
    skos:definition "{ttl_string(defn)}"@en .
""")

    # HOW IT IS: Qualities
    if how_is:
        lines.append("""# ======================================================================
# HOW IT IS: Qualities (BFO_0000019)
# ======================================================================
""")
        for name, defn in how_is.items():
            lines.append(f"""nexus:{name} a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000019 ;
    rdfs:label "{ttl_string(name)}"@en ;
    skos:definition "{ttl_string(defn)}"@en .
""")

    # WHY: Roles
    if why_roles:
        lines.append("""# ======================================================================
# WHY: Roles (BFO_0000023)
# ======================================================================
""")
        for name, defn in why_roles.items():
            lines.append(f"""nexus:{name} a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000023 ;
    rdfs:label "{ttl_string(name)}"@en ;
    skos:definition "{ttl_string(defn)}"@en .
""")

    # WHY: Dispositions
    if why_disps:
        lines.append("""# ======================================================================
# WHY: Dispositions (BFO_0000016)
# ======================================================================
""")
        for name, defn in why_disps.items():
            lines.append(f"""nexus:{name} a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000016 ;
    rdfs:label "{ttl_string(name)}"@en ;
    skos:definition "{ttl_string(defn)}"@en .
""")

    # Process Relationships
    rels = []
    if who:
        first_who = list(who.keys())[0]
        rels.append(f"""nexus:{filename}_has_{first_who.lower()} a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000057 ;
    rdfs:domain nexus:{cls} ;
    rdfs:range nexus:{first_who} ;
    rdfs:label "{cls} has participant {first_who}"@en .""")
    if where:
        first_where = list(where.keys())[0]
        rels.append(f"""nexus:{filename}_occurs_in a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000066 ;
    rdfs:domain nexus:{cls} ;
    rdfs:range nexus:{first_where} ;
    rdfs:label "{cls} occurs in {first_where}"@en .""")
    if when:
        first_when = list(when.keys())[0]
        rels.append(f"""nexus:{filename}_occupies a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000199 ;
    rdfs:domain nexus:{cls} ;
    rdfs:range nexus:{first_when} ;
    rdfs:label "{cls} occupies {first_when}"@en .""")
    if why_roles:
        first_role = list(why_roles.keys())[0]
        rels.append(f"""nexus:{filename}_realizes a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000055 ;
    rdfs:domain nexus:{cls} ;
    rdfs:range nexus:{first_role} ;
    rdfs:label "{cls} realizes {first_role}"@en .""")
    if preceded_by:
        rels.append(f"""nexus:{filename}_preceded_by a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000062 ;
    rdfs:domain nexus:{cls} ;
    rdfs:range nexus:{preceded_by} ;
    rdfs:label "{cls} preceded by {preceded_by}"@en .""")

    if rels:
        lines.append("""# ======================================================================
# Process Relationships (BFO Object Properties)
# ======================================================================
""")
        for r in rels:
            lines.append(r + "\n")

    # Data Properties
    if data_props:
        lines.append("""# ======================================================================
# Data Properties
# ======================================================================
""")
        for prop, xsd_type in data_props.items():
            lines.append(f"""nexus:{prop} a owl:DatatypeProperty ;
    rdfs:label "{prop}"@en ;
    rdfs:range xsd:{xsd_type} .
""")

    path.write_text("\n".join(lines))
    return path


# =====================================================================
# ALL PROCESS DEFINITIONS
# Based on real codebase analysis of Python functions + React components
# =====================================================================

ALL_PROCESSES = []

def p(**kwargs):
    ALL_PROCESSES.append(kwargs)

# ----- PROVIDER INTEGRATION (6 processes) -----

p(folder="provider_integration", filename="provider_discovery_process",
  label="Provider Discovery Process",
  definition="A process that discovers available AI providers by checking workspace secrets for API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.) and querying the in-memory MODEL_REGISTRY for each provider's model catalog.",
  impl="apps/api/app/api/endpoints/providers.py:66-212 list_available_providers()",
  who={"ProviderDiscoveryServer": "FastAPI server executing provider enumeration",
       "UserRequester": "Authenticated user requesting available providers"},
  where={"ProvidersEndpoint": "API endpoint GET /api/providers/available",
         "SecretsTable": "PostgreSQL secrets table storing encrypted API keys",
         "ModelRegistry": "In-memory MODEL_REGISTRY dict with 60+ model definitions"},
  when={"DiscoveryDuration": "Temporal region of 50-200ms for secret queries and registry lookup"},
  how_know={"APIKeySecret": "Encrypted API key stored in secrets table (Fernet AES-128-CBC)",
            "ProviderCatalog": "List of Provider objects with has_api_key flag and model list",
            "ModelInfo": "Model metadata: id, name, context_window, supports_streaming, supports_vision"},
  how_is={"ProviderAvailability": "Boolean quality indicating if a provider has a configured API key",
          "ModelCount": "Integer quality counting available models per provider"},
  why_roles={"ProviderEnumeratorRole": "Role realized when system scans secrets for provider API keys"},
  why_disps={"AlwaysIncludeOllamaDisposition": "Disposition to always include Ollama provider regardless of API key presence"},
  steps=["Query user workspace memberships from workspace_members table",
         "Query secrets table for API key patterns (OPENAI_API_KEY, ANTHROPIC_API_KEY, XAI_API_KEY, etc.)",
         "Check environment variables as fallback for each provider",
         "For each provider with key: query MODEL_REGISTRY for models with capabilities",
         "Always include Ollama (local, no API key required)",
         "Return list of Provider objects with has_api_key and models"],
  data_props={"hasAPIKey": "boolean", "modelCount": "integer", "providerName": "string"})

p(folder="provider_integration", filename="openai_compatible_streaming_process",
  label="OpenAI Compatible Streaming Process",
  definition="A process that streams AI responses from OpenAI-compatible APIs (OpenAI, XAI, Mistral, OpenRouter, Perplexity, Google) using Server-Sent Events with Authorization Bearer headers.",
  impl="apps/api/app/services/providers.py:202-302 stream_with_openai_compatible()",
  who={"OpenAICompatibleProvider": "External LLM API implementing OpenAI chat completions interface",
       "ChatBackendProxy": "FastAPI server proxying streaming requests to provider"},
  where={"ChatCompletionsEndpoint": "Provider endpoint {base_url}/chat/completions",
         "StreamEndpoint": "NEXUS endpoint POST /api/chat/stream"},
  when={"FirstTokenLatency": "200-2000ms from request to first token depending on provider and model",
        "StreamingWindow": "1-30 seconds total streaming duration"},
  how_know={"ProviderMessages": "Array of {role, content} messages formatted for provider API",
            "SSEDataLine": "Server-Sent Event line: data: {choices:[{delta:{content:token}}]}",
            "DoneSignal": "Terminal SSE line: data: [DONE]",
            "AuthorizationHeader": "HTTP header: Authorization: Bearer {api_key}"},
  how_is={"StreamingThroughput": "10-100 tokens/second depending on model and load",
          "ResponseCompleteness": "Quality measuring whether full response was received before timeout"},
  why_roles={"StreamProxyRole": "Role realized when backend proxies SSE from provider to frontend"},
  why_disps={"OpenRouterRefererDisposition": "Disposition to add HTTP-Referer header when provider is OpenRouter",
             "TimeoutDisposition": "Disposition to timeout after 120 seconds of no data"},
  steps=["Build messages array with system prompt as first message",
         "Set Authorization: Bearer {api_key} header",
         "POST to {endpoint}/chat/completions with stream=true, model, messages, temperature",
         "Parse SSE stream line by line",
         "For each data: line, extract choices[0].delta.content",
         "Yield content chunks to caller",
         "Stop on data: [DONE] signal",
         "Handle HTTP errors with user-friendly messages"],
  data_props={"streamTimeout": "integer", "tokenCount": "integer"})

p(folder="provider_integration", filename="ollama_inference_process",
  label="Ollama Inference Process",
  definition="A process that performs local LLM inference via Ollama API at localhost:11434, supporting both streaming and non-streaming modes with optional multimodal (image) input.",
  impl="apps/api/app/services/providers.py:122-199 complete_with_ollama(), stream_with_ollama()",
  who={"OllamaServer": "Local Ollama server running at http://localhost:11434",
       "LocalGPU": "Local GPU hardware executing model inference"},
  where={"OllamaChatEndpoint": "Ollama API endpoint POST /api/chat at localhost:11434",
         "OllamaTagsEndpoint": "Ollama API endpoint GET /api/tags for model listing"},
  when={"OllamaInferenceDuration": "1-60 seconds depending on model size (2B-70B parameters) and prompt length"},
  how_know={"OllamaMessage": "Message with role, content, and optional images array (base64)",
            "OllamaStreamLine": "JSON line: {message: {content: chunk, role: assistant}, done: false}",
            "ModelTag": "Ollama model identifier like llama3:8b, qwen3-vl:2b, gemma3:4b"},
  how_is={"ModelAvailability": "Quality indicating if model is pulled and ready locally",
          "VisionSupport": "Boolean quality indicating multimodal image input support"},
  why_roles={"LocalInferenceRole": "Role realized when Ollama executes model inference on local hardware"},
  why_disps={"MultimodalDisposition": "Disposition to accept base64 images when model supports vision (llava, qwen3-vl, gemma3)",
             "ToolCallingDisposition": "Disposition to execute tool calls when model supports function calling"},
  steps=["Build messages array with system prompt",
         "If images present and model supports vision: encode images as base64 array",
         "POST to http://localhost:11434/api/chat with model, messages, stream flag",
         "If streaming: iterate JSON lines, yield message.content chunks",
         "If non-streaming: return message.content from response",
         "Handle connection errors (Ollama not running)"],
  data_props={"modelName": "string", "supportsVision": "boolean", "supportsTools": "boolean"})

p(folder="provider_integration", filename="cloudflare_workers_ai_process",
  label="Cloudflare Workers AI Process",
  definition="A process that executes AI inference on Cloudflare's edge network using Workers AI API, supporting both streaming SSE and non-streaming responses.",
  impl="apps/api/app/services/providers.py:305-421 complete_with_cloudflare(), stream_with_cloudflare()",
  who={"CloudflareEdgeNetwork": "Cloudflare's global edge infrastructure executing AI inference",
       "WorkersAIRuntime": "Cloudflare Workers AI model runtime"},
  where={"CloudflareAIEndpoint": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/{model}",
         "CloudflareModelsEndpoint": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search"},
  when={"EdgeInferenceDuration": "500-5000ms depending on model and edge location proximity"},
  how_know={"CloudflareRequest": "JSON body with messages array and optional stream:true flag",
            "CloudflareResponse": "JSON with result.response (non-streaming) or SSE data lines",
            "AccountId": "Cloudflare account identifier required for API routing"},
  how_is={"EdgeLatency": "Quality measuring response time based on edge node proximity",
          "ModelPathFormat": "Quality: model path format @cf/meta/llama-3.1-8b-instruct"},
  why_roles={"EdgeInferenceRole": "Role realized when Cloudflare executes inference at the edge"},
  why_disps={"SSEStreamingDisposition": "Disposition to stream via SSE when stream:true is set"},
  steps=["Extract account_id from provider config or secrets",
         "Format model path as @cf/{provider}/{model}",
         "Set Authorization: Bearer {api_token} header",
         "POST to Cloudflare AI run endpoint with messages",
         "If streaming: parse SSE data lines with response field",
         "If non-streaming: extract result.response from JSON",
         "Handle Cloudflare-specific error formats"],
  data_props={"accountId": "string", "modelPath": "string"})

p(folder="provider_integration", filename="abi_server_streaming_process",
  label="ABI Server Streaming Process",
  definition="A process that streams AI responses from external ABI (Agentic Brain Infrastructure) servers using custom SSE format with event: ai_message events, extracting prompt from messages and authenticating via query parameter token.",
  impl="apps/api/app/services/providers.py:702-796 stream_with_abi()",
  who={"ABIServer": "External Agentic Brain Infrastructure server (e.g., Forvis Mazars)",
       "ABIAgent": "Named agent on ABI server discovered via OpenAPI spec"},
  where={"ABIStreamEndpoint": "ABI endpoint POST /agents/{agent_name}/stream-completion?token={token}",
         "ABIOpenAPIEndpoint": "ABI endpoint GET /openapi.json for agent discovery"},
  when={"ABIStreamDuration": "1-30 seconds depending on agent complexity and query type",
        "ABIFirstTokenLatency": "200-2000ms for first ai_message event"},
  how_know={"ABIRequest": "JSON body: {prompt: latest_user_message, thread_id: message_hash}",
            "ABISSEEvent": "Custom SSE: event: ai_message followed by data: content lines",
            "ABIDuplicateEvent": "ABI sends both ai_message and message events with same content",
            "ABITokenParam": "Authentication via query parameter ?token={api_key}"},
  how_is={"DuplicateFilteringQuality": "Quality of filtering: only yield from ai_message events, skip message events",
          "MultiLineDataQuality": "Quality: handle multiple data: lines per single event (W3C SSE standard)"},
  why_roles={"ABIProxyRole": "Role realized when NEXUS proxies requests to external ABI server"},
  why_disps={"DuplicateFilteringDisposition": "Disposition to only yield ai_message events to prevent duplicate content",
             "MultiLineDataDisposition": "Disposition to not reset current_event until next event: line arrives"},
  steps=["Extract latest user message as prompt from messages array",
         "Generate thread_id from message content hash",
         "Extract agent_name from model_id in provider config",
         "Build URL: {endpoint}/agents/{agent_name}/stream-completion?token={token}",
         "POST with {prompt, thread_id} body",
         "Parse SSE stream: track current_event from event: lines",
         "Only yield content from data: lines when current_event == ai_message",
         "Do NOT reset current_event until next event: line (handles multi-line data)",
         "Stop on data: [DONE]"],
  data_props={"agentName": "string", "threadId": "string", "promptText": "string"})

p(folder="provider_integration", filename="abi_agent_discovery_process",
  label="ABI Agent Discovery Process",
  definition="A process that discovers all available agents from an external ABI server by fetching and parsing its OpenAPI specification, extracting agent names from /agents/{name}/stream-completion paths.",
  impl="apps/api/app/api/endpoints/abi_sync.py:29-80 discover_abi_agents()",
  who={"ABIOpenAPIServer": "External ABI server serving OpenAPI/Swagger specification",
       "DiscoveryClient": "httpx async client fetching and parsing OpenAPI JSON"},
  where={"OpenAPIEndpoint": "ABI endpoint GET /openapi.json or GET /redoc",
         "AgentConfigsTable": "PostgreSQL table agent_configs where discovered agents are stored"},
  when={"DiscoveryDuration": "200-1000ms for HTTP fetch + JSON parsing"},
  how_know={"OpenAPISpec": "JSON document containing paths, operations, and descriptions",
            "AgentPath": "OpenAPI path pattern: /agents/{agent_name}/stream-completion",
            "AgentInfo": "Discovered agent metadata: name, description, model_id"},
  how_is={"AgentCount": "Integer quality: number of agents discovered from OpenAPI spec",
          "SpecCompleteness": "Quality measuring if spec contains descriptions for agents"},
  why_roles={"AgentDiscovererRole": "Role realized when system parses OpenAPI to find agents"},
  why_disps={"OpenAPIParsingDisposition": "Disposition to extract agent names from path patterns"},
  steps=["Fetch OpenAPI spec from {endpoint}/openapi.json using httpx async client",
         "Parse JSON response",
         "Iterate paths looking for /agents/{name}/stream-completion pattern",
         "Extract agent names from path parameters",
         "Extract descriptions from operation summaries",
         "Generate model_id by normalizing agent name (lowercase, replace spaces with hyphens)",
         "Return list of {name, description, model_id} dicts"],
  data_props={"endpointUrl": "string", "agentCount": "integer"})

# ----- AGENT MANAGEMENT (3 processes) -----

p(folder="agent_management", filename="agent_creation_process",
  label="Agent Creation Process",
  definition="A process that creates a custom AI agent in a workspace with name, system_prompt, model_id, provider, and optional logo_url, persisting to the agent_configs PostgreSQL table.",
  impl="apps/api/app/api/endpoints/agents.py:168-203 create_agent()",
  who={"AgentCreator": "Authenticated user with workspace access creating the agent",
       "AgentConfigStore": "PostgreSQL agent_configs table storing agent definitions"},
  where={"AgentsEndpoint": "API endpoint POST /api/agents/",
         "AgentConfigsTable": "PostgreSQL table agent_configs with workspace_id FK"},
  when={"CreationDuration": "50-100ms for validation and database insert"},
  how_know={"AgentCreateRequest": "Pydantic model: name, description, system_prompt, model (default gpt-4), temperature (0.7), max_tokens (4096), workspace_id",
            "AgentConfigRecord": "Database row: id, workspace_id, name, description, system_prompt, provider, model_id, logo_url, is_default, created_at",
            "AgentConfigResponse": "API response with full agent configuration"},
  how_is={"AgentNameUniqueness": "Quality: agent names should be unique within workspace (not enforced)",
          "DefaultTemperature": "Quality: default temperature of 0.7 for balanced creativity"},
  why_roles={"AgentDesignerRole": "Role realized when user defines agent personality and capabilities"},
  why_disps={"ModelRegistryLookupDisposition": "Disposition to infer provider from model_id via model registry"},
  steps=["Validate workspace access via require_workspace_access(user_id, workspace_id)",
         "Generate UUID for agent ID",
         "Infer provider from model_id using model registry lookup",
         "Look up logo_url from provider logo mapping",
         "Create AgentConfigModel ORM instance",
         "Insert into agent_configs table",
         "Commit transaction",
         "Return AgentConfig response"],
  data_props={"agentName": "string", "modelId": "string", "temperature": "float", "maxTokens": "integer"})

p(folder="agent_management", filename="agent_sync_from_registry_process",
  label="Agent Sync From Registry Process",
  definition="A process that automatically creates agents from the MODEL_REGISTRY, creating one agent per model for a workspace, skipping models that already have agents.",
  impl="apps/api/app/api/endpoints/agents.py:297-383 sync_agents_from_models()",
  who={"ModelRegistry": "In-memory MODEL_REGISTRY containing 60+ model definitions across 9 providers",
       "WorkspaceAgentStore": "PostgreSQL agent_configs table for the target workspace"},
  where={"AgentSyncEndpoint": "API endpoint POST /api/agents/sync?workspace_id={id}",
         "AgentConfigsTable": "PostgreSQL table agent_configs"},
  when={"SyncDuration": "100-300ms for registry scan + batch insert of 60+ agents"},
  how_know={"ModelRegistryEntry": "ModelInfo: id, name, provider, context_window, capabilities, released date",
            "SyncResult": "AgentSyncResult: created count, skipped count, total_models, agent_ids list",
            "ProviderLogo": "Logo URL mapping from get_logo_for_provider()"},
  how_is={"SyncCompleteness": "Quality: all registry models should have corresponding agents",
          "DuplicateSkipping": "Quality: existing agents (by model_id) are skipped, not duplicated"},
  why_roles={"AgentProvisionerRole": "Role realized when system auto-creates agents from model catalog"},
  why_disps={"BatchInsertDisposition": "Disposition to batch-insert multiple agents in single transaction"},
  steps=["Validate workspace access",
         "Call get_all_models() to retrieve 60+ models from MODEL_REGISTRY",
         "Query existing agents for workspace from agent_configs table",
         "For each model not yet represented: generate agent with name, description, system_prompt",
         "Set provider, model_id, logo_url from registry metadata",
         "Batch insert new AgentConfigModel rows",
         "Commit transaction",
         "Return AgentSyncResult with created/skipped counts"],
  data_props={"createdCount": "integer", "skippedCount": "integer", "totalModels": "integer"})

p(folder="agent_management", filename="agent_provider_resolution_process",
  label="Agent Provider Resolution Process",
  definition="A process that resolves which LLM provider, API key, and model to use for a given agent by checking agent_configs, workspace secrets, and falling back to Ollama auto-detection.",
  impl="apps/api/app/api/endpoints/chat.py:202-319 _resolve_provider()",
  who={"ProviderResolver": "Backend logic determining optimal provider for chat request",
       "SecretStore": "Encrypted secrets providing API keys for cloud providers",
       "OllamaFallback": "Local Ollama server as fallback when no cloud provider is configured"},
  where={"AgentConfigsTable": "PostgreSQL agent_configs table with provider and model_id columns",
         "SecretsTable": "PostgreSQL secrets table with encrypted API keys",
         "ABIServersTable": "PostgreSQL abi_servers table for ABI provider resolution"},
  when={"ResolutionDuration": "50-600ms: 50ms for DB queries, up to 500ms for Ollama health check"},
  how_know={"ProviderConfigRequest": "Pydantic model: type, model, endpoint, api_key, enabled",
            "SecretKeyMapping": "Provider to secret key mapping: xai->XAI_API_KEY, openai->OPENAI_API_KEY",
            "DecryptedAPIKey": "Fernet-decrypted API key from secrets table",
            "OllamaStatus": "Ollama health check result with available models list"},
  how_is={"ResolutionPriority": "Quality: explicit provider > agent config > secrets > Ollama fallback",
          "VisionModelSelection": "Quality: if has_images=true, prefer vision-capable models"},
  why_roles={"ProviderResolverRole": "Role realized when system determines optimal provider for request"},
  why_disps={"FallbackDisposition": "Disposition to fall back to Ollama when no cloud provider configured",
             "VisionAwareDisposition": "Disposition to select vision-capable model when images are attached"},
  steps=["If provider explicitly provided and enabled: return it directly",
         "If agent_id provided: query agent_configs for provider and model_id",
         "If agent provider is abi: query abi_servers for workspace's enabled ABI server",
         "If agent provider is cloud (openai, xai, etc.): map to secret key name",
         "Query secrets table and decrypt API key with Fernet",
         "Build ProviderConfigRequest with endpoint, api_key, model",
         "If no provider resolved: check Ollama status at localhost:11434/api/tags",
         "Select best Ollama model based on has_images flag (vision-capable models preferred)",
         "Return resolved ProviderConfigRequest or None"],
  data_props={"providerType": "string", "hasImages": "boolean", "agentId": "string"})

# ----- KNOWLEDGE GRAPH (5 processes) -----

p(folder="knowledge_graph", filename="graph_node_creation_process",
  label="Graph Node Creation Process",
  definition="A process that creates a new node entity in the knowledge graph with type, label, and JSON properties, storing it in the graph_nodes PostgreSQL table with workspace isolation.",
  impl="apps/api/app/api/endpoints/graph.py:161-178 create_node()",
  who={"GraphAuthor": "Authenticated user creating the node",
       "GraphDatabase": "PostgreSQL database storing graph_nodes table"},
  where={"GraphNodesEndpoint": "API endpoint POST /api/graph/nodes",
         "GraphNodesTable": "PostgreSQL table graph_nodes with workspace_id index"},
  when={"NodeCreationDuration": "10-30ms for single row insert"},
  how_know={"GraphNodeCreate": "Pydantic model: workspace_id, type (1-100 chars), label (1-500 chars), properties (JSON dict)",
            "GraphNodeRecord": "Database row: id (node-{uuid}), workspace_id, type, label, properties (JSON text), created_at, updated_at",
            "GraphNodeResponse": "API response with full node data"},
  how_is={"NodeTypeCardinality": "Quality: unlimited node types per workspace",
          "PropertyFlexibility": "Quality: properties stored as free-form JSON"},
  why_roles={"GraphBuilderRole": "Role realized when user adds entities to the knowledge graph"},
  why_disps={"JSONSerializationDisposition": "Disposition to serialize properties dict to JSON string for storage"},
  steps=["Validate workspace access",
         "Generate node ID: node-{uuid.hex[:12]}",
         "Serialize properties dict to JSON string",
         "Insert GraphNodeModel into graph_nodes table",
         "Commit transaction",
         "Return GraphNode response"],
  data_props={"nodeType": "string", "nodeLabel": "string", "propertyCount": "integer"})

p(folder="knowledge_graph", filename="graph_edge_creation_process",
  label="Graph Edge Creation Process",
  definition="A process that creates a relationship (edge) between two nodes in the knowledge graph, validating both source and target node existence before inserting into graph_edges.",
  impl="apps/api/app/api/endpoints/graph.py:267-292 create_edge()",
  who={"GraphAuthor": "User creating the relationship",
       "SourceNode": "Existing graph node at the start of the edge",
       "TargetNode": "Existing graph node at the end of the edge"},
  where={"GraphEdgesEndpoint": "API endpoint POST /api/graph/edges",
         "GraphEdgesTable": "PostgreSQL table graph_edges with FKs to graph_nodes"},
  when={"EdgeCreationDuration": "30-60ms: node existence checks (2x) + insert"},
  how_know={"GraphEdgeCreate": "Pydantic model: workspace_id, source_id, target_id, type (1-100 chars), properties (JSON)",
            "EdgeRecord": "Database row: id (edge-{uuid}), workspace_id, source_id, target_id, type, properties"},
  how_is={"ReferentialIntegrity": "Quality: both source and target nodes must exist (404 if not)",
          "CascadeDeleteBehavior": "Quality: deleting a node cascades to delete all connected edges"},
  why_roles={"RelationshipCreatorRole": "Role realized when user defines connections between entities"},
  why_disps={"NodeExistenceValidationDisposition": "Disposition to verify source and target node existence before edge creation"},
  steps=["Validate workspace access",
         "Verify source_id exists in graph_nodes (404 if not)",
         "Verify target_id exists in graph_nodes (404 if not)",
         "Generate edge ID: edge-{uuid.hex[:12]}",
         "Serialize properties to JSON",
         "Insert GraphEdgeModel into graph_edges table",
         "Return GraphEdge response"],
  data_props={"edgeType": "string", "sourceId": "string", "targetId": "string"})

p(folder="knowledge_graph", filename="graph_query_process",
  label="Graph Query Process",
  definition="A process that searches the knowledge graph using ILIKE pattern matching on node labels and types, returning matching nodes and their connecting edges, limited to a configurable result count.",
  impl="apps/api/app/api/endpoints/graph.py:322-358 query_graph()",
  who={"QueryExecutor": "Backend logic executing graph searches",
       "GraphDatabase": "PostgreSQL database with graph_nodes and graph_edges tables"},
  where={"GraphQueryEndpoint": "API endpoint POST /api/graph/query?workspace_id={id}",
         "GraphNodesTable": "PostgreSQL graph_nodes searched with ILIKE",
         "GraphEdgesTable": "PostgreSQL graph_edges for connecting edges"},
  when={"QueryDuration": "50-250ms depending on graph size and query complexity"},
  how_know={"GraphQuery": "Pydantic model: query (1-10000 chars), language (natural/sparql), limit (1-5000, default 100)",
            "GraphQueryResult": "Response: nodes list, edges list, query_explanation",
            "ILIKEPattern": "SQL pattern: WHERE label ILIKE %query% OR type ILIKE %query%"},
  how_is={"ResultLimit": "Quality: max 5000 nodes per query result",
          "CaseInsensitivity": "Quality: ILIKE provides case-insensitive matching",
          "NoSPARQLYet": "Quality: SPARQL language option exists but falls back to text search"},
  why_roles={"GraphSearcherRole": "Role realized when system searches knowledge graph for matching entities"},
  why_disps={"TextSearchDisposition": "Disposition to use ILIKE text matching (not semantic search)"},
  steps=["Validate workspace access",
         "Query graph_nodes: WHERE workspace_id=? AND (label ILIKE ? OR type ILIKE ?)",
         "Apply LIMIT from request (default 100, max 5000)",
         "Extract node IDs from results",
         "Query graph_edges: WHERE workspace_id=? AND source_id IN (?) AND target_id IN (?)",
         "Return GraphQueryResult with nodes, edges, and explanation"],
  data_props={"queryText": "string", "resultNodeCount": "integer", "resultEdgeCount": "integer"})

p(folder="knowledge_graph", filename="graph_statistics_process",
  label="Graph Statistics Process",
  definition="A process that calculates workspace-level graph metrics including total nodes, total edges, type distributions, and average degree using SQL aggregate queries.",
  impl="apps/api/app/api/endpoints/graph.py:361-400 get_graph_statistics()",
  who={"StatisticsEngine": "SQL aggregate query executor",
       "GraphDatabase": "PostgreSQL with graph_nodes and graph_edges tables"},
  where={"StatisticsEndpoint": "API endpoint GET /api/graph/statistics/{workspace_id}"},
  when={"StatisticsDuration": "50-200ms for 4 aggregate queries"},
  how_know={"StatisticsResult": "Dict: total_nodes, total_edges, nodes_by_type, edges_by_type, avg_degree",
            "TypeDistribution": "Dict mapping type string to count integer",
            "AverageDegree": "Float: 2 * total_edges / total_nodes (0 if no nodes)"},
  how_is={"DegreeCalculation": "Quality: average degree formula = 2 * edges / nodes",
          "EmptyGraphHandling": "Quality: returns 0 for all metrics when graph is empty"},
  why_roles={"MetricsCollectorRole": "Role realized when system aggregates graph statistics"},
  why_disps={"SQLAggregateDisposition": "Disposition to use SQL COUNT and GROUP BY for efficient statistics"},
  steps=["Validate workspace access",
         "SELECT COUNT(*) FROM graph_nodes WHERE workspace_id = ?",
         "SELECT COUNT(*) FROM graph_edges WHERE workspace_id = ?",
         "SELECT type, COUNT(*) FROM graph_nodes GROUP BY type",
         "SELECT type, COUNT(*) FROM graph_edges GROUP BY type",
         "Calculate avg_degree = 2 * total_edges / total_nodes",
         "Return statistics dict"],
  data_props={"totalNodes": "integer", "totalEdges": "integer", "avgDegree": "float"})

p(folder="knowledge_graph", filename="graph_workspace_load_process",
  label="Graph Workspace Load Process",
  definition="A process that loads the complete knowledge graph for a workspace including all nodes and edges, optionally filtered by node type, with configurable limit up to 5000 nodes.",
  impl="apps/api/app/api/endpoints/graph.py:106-139 get_workspace_graph()",
  who={"GraphLoader": "Backend logic fetching full workspace graph",
       "GraphDatabase": "PostgreSQL storing nodes and edges"},
  where={"WorkspaceGraphEndpoint": "API endpoint GET /api/graph/workspaces/{workspace_id}",
         "GraphNodesTable": "PostgreSQL graph_nodes table",
         "GraphEdgesTable": "PostgreSQL graph_edges table"},
  when={"LoadDuration": "50-500ms depending on graph size"},
  how_know={"GraphData": "Response: nodes list + edges list",
            "NodeTypeFilter": "Optional query param to filter by node type",
            "LoadLimit": "Default 1000, max 5000 nodes"},
  how_is={"FilterSupport": "Quality: optional node_type parameter for type-based filtering",
          "SizeLimit": "Quality: configurable limit prevents loading excessively large graphs"},
  why_roles={"GraphDataProviderRole": "Role realized when system provides full graph for visualization"},
  why_disps={"LazyEdgeLoadingDisposition": "Disposition to only load edges connecting returned nodes"},
  steps=["Validate workspace access",
         "Query graph_nodes filtered by workspace_id and optional node_type",
         "Apply limit (default 1000, max 5000)",
         "Extract node IDs",
         "Query graph_edges where source and target are in node IDs",
         "Convert ORM models to response schema",
         "Return GraphData with nodes and edges"],
  data_props={"nodeLimit": "integer", "nodeTypeFilter": "string"})

# ----- ONTOLOGY MANAGEMENT (4 processes) -----

p(folder="ontology_management", filename="ontology_entity_creation_process",
  label="Ontology Entity Creation Process",
  definition="A process that creates a custom ontology entity (owl:Class) with optional base_class IRI reference, stored in an in-memory list (future: PostgreSQL ontologies table).",
  impl="apps/api/app/api/endpoints/ontology.py:138-149 create_entity()",
  who={"OntologyDesigner": "User defining custom ontology entities",
       "InMemoryStore": "Python list storing ontology items (not yet persisted to DB)"},
  where={"OntologyEntityEndpoint": "API endpoint POST /api/ontology/entity"},
  when={"EntityCreationDuration": "Less than 1ms (in-memory list append)"},
  how_know={"EntityCreate": "Pydantic model: name (1-200 chars), description (max 2000), base_class (max 500, IRI)",
            "OntologyItem": "Response: id (entity-{timestamp}), name, type=entity, description, base_class, created_at"},
  how_is={"InMemoryPersistence": "Quality: items stored in memory only, lost on server restart",
          "IRIValidation": "Quality: base_class accepts any string (no IRI validation)"},
  why_roles={"OntologyEngineerRole": "Role realized when user defines domain-specific entities"},
  why_disps={"TimestampIDDisposition": "Disposition to generate entity ID from timestamp milliseconds"},
  steps=["Generate entity ID: entity-{timestamp_ms}",
         "Create OntologyItem with type=entity",
         "Set description and base_class from request",
         "Append to in-memory ontology_items list",
         "Return created OntologyItem"],
  data_props={"entityName": "string", "baseClassIRI": "string"})

p(folder="ontology_management", filename="ontology_relationship_creation_process",
  label="Ontology Relationship Creation Process",
  definition="A process that creates a custom ontology relationship (owl:ObjectProperty) with optional base_property IRI reference, stored in the in-memory ontology items list.",
  impl="apps/api/app/api/endpoints/ontology.py:152-163 create_relationship()",
  who={"OntologyDesigner": "User defining custom ontology relationships"},
  where={"OntologyRelationshipEndpoint": "API endpoint POST /api/ontology/relationship"},
  when={"RelationshipCreationDuration": "Less than 1ms (in-memory)"},
  how_know={"RelationshipCreate": "Pydantic model: name (1-200 chars), description, base_property IRI",
            "OntologyItem": "Response: id (rel-{timestamp}), name, type=relationship"},
  how_is={"PropertyDirectionality": "Quality: relationships are unidirectional (no inverse auto-creation)"},
  why_roles={"PropertyDesignerRole": "Role realized when user defines ontology relationships"},
  why_disps={"SimpleStorageDisposition": "Disposition to store as simple list item without RDF graph backing"},
  steps=["Generate relationship ID: rel-{timestamp_ms}",
         "Create OntologyItem with type=relationship",
         "Set description and base_property",
         "Append to in-memory list",
         "Return OntologyItem"],
  data_props={"propertyName": "string", "basePropertyIRI": "string"})

p(folder="ontology_management", filename="reference_ontology_import_process",
  label="Reference Ontology Import Process",
  definition="A process that parses external ontology files (TTL/OWL/RDF) using regex patterns to extract owl:Class and owl:ObjectProperty definitions with their labels, definitions, and examples.",
  impl="apps/api/app/api/endpoints/ontology.py:67-197 parse_ttl(), import_reference_ontology()",
  who={"OntologyParser": "Regex-based TTL parser extracting classes and properties",
       "ExternalOntologyFile": "User-provided ontology file content (up to 5MB)"},
  where={"OntologyImportEndpoint": "API endpoint POST /api/ontology/import"},
  when={"ParseDuration": "10-500ms depending on file size (max 5MB, ~5M characters)"},
  how_know={"ImportRequest": "Pydantic model: content (1-5000000 chars), filename (validated pattern)",
            "ReferenceOntology": "Parsed result: id, name, file_path, format, classes list, properties list",
            "ReferenceClass": "Extracted class: iri, label, definition, examples, subClassOf list",
            "ReferenceProperty": "Extracted property: iri, label, definition, inverseOf, domain, range"},
  how_is={"ParserLimitation": "Quality: basic regex parsing, not full Turtle parser",
          "MaxFileSize": "Quality: 5MB maximum file size for import"},
  why_roles={"OntologyImporterRole": "Role realized when system parses external ontology specifications"},
  why_disps={"RegexParsingDisposition": "Disposition to use regex patterns for TTL class/property extraction",
             "FormatDetectionDisposition": "Disposition to detect format from filename extension (.ttl, .owl, .rdf)"},
  steps=["Determine format from filename extension (.ttl, .owl, .rdf)",
         "Parse content using regex for owl:Class patterns",
         "Extract rdfs:label, skos:definition, skos:example for each class",
         "Parse content using regex for owl:ObjectProperty patterns",
         "Extract labels and definitions for each property",
         "Extract ontology name from dc:title triple",
         "Return ReferenceOntology with classes and properties lists"],
  data_props={"classCount": "integer", "propertyCount": "integer", "fileFormat": "string"})

p(folder="ontology_management", filename="ontology_preview_process",
  label="Ontology Preview Process",
  definition="A process that previews an ontology file before full import, showing name, class count, property count, and first 5 items of each, allowing users to review before committing.",
  impl="apps/api/app/api/endpoints/ontology.py:200-220 preview_ontology_file()",
  who={"PreviewEngine": "Parser generating summary statistics from ontology content"},
  where={"OntologyPreviewEndpoint": "API endpoint POST /api/ontology/import/preview"},
  when={"PreviewDuration": "Same as import: 10-500ms"},
  how_know={"PreviewResult": "Dict: name, classCount, propertyCount, preview (first 5 classes + 5 properties)"},
  how_is={"PreviewLimit": "Quality: shows maximum 5 items of each type as preview"},
  why_roles={"PreviewProviderRole": "Role realized when system generates ontology summary for user review"},
  why_disps={"TruncationDisposition": "Disposition to truncate preview to first 5 items"},
  steps=["Parse ontology file (same as import process)",
         "Count total classes and properties",
         "Slice first 5 classes and first 5 properties",
         "Return preview dict with name, counts, and sliced items"],
  data_props={"previewClassCount": "integer", "previewPropertyCount": "integer"})

# ----- FILE MANAGEMENT (3 processes) -----

p(folder="file_management", filename="file_upload_process",
  label="File Upload Process",
  definition="A process that handles multipart file uploads (max 50MB) to either local filesystem (LOCAL_STORAGE_PATH) or S3-compatible storage (MinIO, Cloudflare R2, AWS S3) based on STORAGE_TYPE configuration.",
  impl="apps/api/app/api/endpoints/files.py:410-472 upload_file()",
  who={"UploadHandler": "FastAPI multipart parser processing file upload",
       "StorageBackend": "Local filesystem or S3-compatible object storage"},
  where={"FileUploadEndpoint": "API endpoint POST /api/files/upload",
         "LocalStorage": "Local filesystem at LOCAL_STORAGE_PATH (/tmp/nexus-files default)",
         "S3Bucket": "S3-compatible bucket configured via S3_BUCKET, S3_ENDPOINT env vars"},
  when={"UploadDuration": "50-5000ms: 50ms for small local files, up to 5s for large S3 uploads"},
  how_know={"UploadFile": "FastAPI UploadFile: filename, content_type, file bytes",
            "FileInfo": "Response: name, path, type=file, size (bytes), modified (datetime), content_type",
            "PathSanitization": "Validated path preventing directory traversal attacks"},
  how_is={"MaxFileSize": "Quality: 50MB upload limit enforced before storage",
          "PathSafety": "Quality: path sanitization prevents ../ directory traversal"},
  why_roles={"FileReceiverRole": "Role realized when system accepts and stores uploaded files"},
  why_disps={"S3FallbackDisposition": "Disposition to use S3 when STORAGE_TYPE=s3, local otherwise",
             "ContentTypePreservation": "Disposition to preserve original Content-Type in storage"},
  steps=["Construct full path: {path}/{filename}",
         "Sanitize path (prevent directory traversal)",
         "Read file content asynchronously from multipart",
         "Check size limit: reject if > 50MB (HTTP 413)",
         "If STORAGE_TYPE=local: write to LOCAL_STORAGE_PATH/{clean_path}",
         "If STORAGE_TYPE=s3: s3.put_object(Bucket, Key, Body, ContentType)",
         "Get file stats (size, modified)",
         "Return FileInfo response"],
  data_props={"fileSize": "integer", "contentType": "string", "storagePath": "string"})

p(folder="file_management", filename="file_list_process",
  label="File List Process",
  definition="A process that lists files and folders in a directory path, supporting both local filesystem listing and S3 prefix-based listing with CommonPrefixes for folder simulation.",
  impl="apps/api/app/api/endpoints/files.py:143-228 list_files()",
  who={"DirectoryLister": "Backend logic enumerating directory contents",
       "StorageBackend": "Local filesystem or S3-compatible storage"},
  where={"FileListEndpoint": "API endpoint GET /api/files/?path={path}"},
  when={"ListDuration": "10-500ms: 10ms local, 100-500ms S3"},
  how_know={"FileListResponse": "Response: files list + current path",
            "FileInfo": "Item: name, path, type (file/folder), size, modified, content_type",
            "S3ListResponse": "S3 response with CommonPrefixes (folders) and Contents (files)"},
  how_is={"SortOrder": "Quality: files sorted alphabetically by name",
          "S3FolderSimulation": "Quality: S3 folders simulated via CommonPrefixes with / delimiter"},
  why_roles={"DirectoryEnumeratorRole": "Role realized when system lists storage contents"},
  why_disps={"S3PrefixDisposition": "Disposition to use S3 list_objects_v2 with Delimiter=/ for folder emulation"},
  steps=["If local: resolve full path, iterate directory contents, build FileInfo for each",
         "If S3: normalize prefix, call list_objects_v2 with Prefix and Delimiter=/",
         "Process CommonPrefixes as folders and Contents as files",
         "Skip S3 directory marker objects",
         "Sort results and return FileListResponse"],
  data_props={"directoryPath": "string", "fileCount": "integer", "folderCount": "integer"})

p(folder="file_management", filename="file_crud_process",
  label="File CRUD Process",
  definition="A process encompassing file creation, reading, updating, and deletion operations for both local filesystem and S3-compatible storage backends.",
  impl="apps/api/app/api/endpoints/files.py:231-639 create_file(), read_file(), update_file(), delete_file()",
  who={"FileManager": "Backend logic executing file operations",
       "StorageBackend": "Local filesystem or S3 storage"},
  where={"FileCRUDEndpoints": "POST /api/files/, GET /api/files/{path}, PUT /api/files/{path}, DELETE /api/files/{path}"},
  when={"CRUDDuration": "10-2000ms depending on operation and file size"},
  how_know={"CreateFileRequest": "Pydantic model: path (max 500), content (optional text)",
            "FileContent": "Response for read: name, path, content (text), size",
            "CreateFolderRequest": "Pydantic model: path for folder creation"},
  how_is={"PathTraversalProtection": "Quality: all paths sanitized to prevent ../ attacks",
          "ContentTypeDetection": "Quality: content type inferred from file extension"},
  why_roles={"FileOperatorRole": "Role realized when system performs CRUD on stored files"},
  why_disps={"DualStorageDisposition": "Disposition to support both local and S3 storage transparently"},
  steps=["Create: write content to path (local mkdir -p, S3 put_object)",
         "Read: read file content (local open(), S3 get_object)",
         "Update: overwrite existing file content",
         "Delete: remove file/folder (local unlink/rmtree, S3 delete_object)",
         "Folder: create directory (local mkdir, S3 empty marker object)"],
  data_props={"operationType": "string", "filePath": "string", "fileSize": "integer"})

# ----- SEARCH (3 processes) -----

p(folder="search", filename="wikipedia_search_process",
  label="Wikipedia Search Process",
  definition="A process that searches Wikipedia using their public MediaWiki API, returning article titles, extracts (3 sentences), thumbnail URLs, and fullurl links with relevance scoring.",
  impl="apps/api/app/api/endpoints/search.py:112-167 search_wikipedia()",
  who={"WikipediaAPI": "Wikipedia MediaWiki public API at en.wikipedia.org",
       "SearchClient": "httpx async client executing search request"},
  where={"WikipediaEndpoint": "https://en.wikipedia.org/w/api.php with action=query&generator=search",
         "WebSearchEndpoint": "NEXUS API endpoint POST /api/search/web"},
  when={"SearchDuration": "200-1000ms for Wikipedia API response"},
  how_know={"WikipediaParams": "API params: gsrsearch, gsrlimit, prop=extracts|pageimages|info, exsentences=3",
            "WebSearchResult": "Result: id (md5 hash), title, snippet (extract), url, relevance (1.0-0.95), thumbnail",
            "RelevanceScore": "Float: 1.0 for first result, decreasing by 0.05 per position"},
  how_is={"SnippetLength": "Quality: maximum 3 sentences per snippet via exsentences=3",
          "ThumbnailSize": "Quality: thumbnails requested at 200px via pithumbsize=200"},
  why_roles={"WebSearcherRole": "Role realized when system queries Wikipedia for knowledge"},
  why_disps={"RelevanceScoringDisposition": "Disposition to assign decreasing relevance: 1.0, 0.95, 0.90..."},
  steps=["Build Wikipedia API URL with query parameters",
         "HTTP GET to en.wikipedia.org/w/api.php (timeout: 10s)",
         "Parse JSON response, extract pages from query.pages",
         "Sort pages by search index (relevance)",
         "For each page: extract title, extract (snippet), fullurl",
         "Generate result ID: md5(wikipedia:{pageid})[:12]",
         "Calculate relevance: 1.0 - (index * 0.05)",
         "Include thumbnail URL if available",
         "Return list of WebSearchResult"],
  data_props={"searchQuery": "string", "resultCount": "integer", "maxResults": "integer"})

p(folder="search", filename="duckduckgo_search_process",
  label="DuckDuckGo Search Process",
  definition="A process that searches DuckDuckGo using their Instant Answer API, extracting abstract, related topics, and subtopics with structured result formatting.",
  impl="apps/api/app/api/endpoints/search.py:170-257 search_duckduckgo()",
  who={"DuckDuckGoAPI": "DuckDuckGo Instant Answer public API",
       "SearchClient": "httpx async client"},
  where={"DDGEndpoint": "https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"},
  when={"SearchDuration": "200-800ms for DuckDuckGo API response"},
  how_know={"DDGResponse": "JSON with AbstractText, AbstractURL, RelatedTopics array, Image",
            "RelatedTopic": "Topic with Text, FirstURL, Icon, optional nested Topics array"},
  how_is={"AbstractPriority": "Quality: abstract gets relevance 1.0, topics get 0.9-0.7",
          "NestedTopicSupport": "Quality: handles nested Topics arrays within RelatedTopics"},
  why_roles={"InstantAnswerRole": "Role realized when DDG provides instant answer with abstract"},
  why_disps={"HTMLStrippingDisposition": "Disposition to request no_html=1 for clean text results"},
  steps=["Build DuckDuckGo API URL with q, format=json, no_html=1",
         "HTTP GET to api.duckduckgo.com",
         "If AbstractText exists: create result with relevance 1.0",
         "Iterate RelatedTopics: create results with relevance 0.9-0.7",
         "Handle nested Topics arrays (subtopics)",
         "Limit results to requested count",
         "Return list of WebSearchResult"],
  data_props={"hasAbstract": "boolean", "topicCount": "integer"})

p(folder="search", filename="search_suggestions_process",
  label="Search Suggestions Process",
  definition="A process that provides autocomplete search suggestions by querying Wikipedia's OpenSearch API with partial query strings, returning up to 20 suggestion strings.",
  impl="apps/api/app/api/endpoints/search.py:281-312 get_suggestions()",
  who={"WikipediaOpenSearch": "Wikipedia OpenSearch API for autocomplete suggestions"},
  where={"SuggestionsEndpoint": "NEXUS API GET /api/search/suggestions?query={q}&limit={n}",
         "WikipediaOpenSearchEndpoint": "en.wikipedia.org/w/api.php?action=opensearch"},
  when={"SuggestionDuration": "100-500ms for Wikipedia OpenSearch response"},
  how_know={"OpenSearchResponse": "JSON array: [query, [suggestions], [descriptions], [urls]]",
            "SuggestionList": "Array of suggestion strings (index 1 of response)"},
  how_is={"MaxSuggestions": "Quality: maximum 20 suggestions (configurable 1-20)",
          "MinQueryLength": "Quality: minimum 1 character for query"},
  why_roles={"AutocompletProviderRole": "Role realized when system provides search suggestions"},
  why_disps={"WikipediaOnlyDisposition": "Disposition to only use Wikipedia for suggestions (no DDG)"},
  steps=["Build Wikipedia OpenSearch URL: action=opensearch, search={query}, limit={n}",
         "HTTP GET with 5-second timeout",
         "Parse JSON array response",
         "Extract suggestions from index 1",
         "Limit to requested count",
         "Return list of suggestion strings"],
  data_props={"partialQuery": "string", "suggestionCount": "integer"})

# ----- WORKSPACE MANAGEMENT (4 processes) -----

p(folder="workspace_management", filename="workspace_creation_process",
  label="Workspace Creation Process",
  definition="A process that creates a new workspace with unique slug, automatically adding the creating user as owner in workspace_members table within a single transaction.",
  impl="apps/api/app/api/endpoints/workspaces.py:96-124 create_workspace()",
  who={"WorkspaceCreator": "Authenticated user creating the workspace",
       "WorkspaceDatabase": "PostgreSQL with workspaces and workspace_members tables"},
  where={"WorkspacesEndpoint": "API endpoint POST /api/workspaces",
         "WorkspacesTable": "PostgreSQL workspaces table",
         "WorkspaceMembersTable": "PostgreSQL workspace_members table"},
  when={"CreationDuration": "40-80ms: uniqueness check + 2 inserts"},
  how_know={"WorkspaceCreate": "Pydantic model: name (1-200 chars), slug (regex: ^[a-z0-9][a-z0-9-]*[a-z0-9]$)",
            "WorkspaceRecord": "DB row: id (ws-{uuid}), name, slug (unique), owner_id, timestamps",
            "MemberRecord": "DB row: id, workspace_id, user_id, role=owner, created_at"},
  how_is={"SlugUniqueness": "Quality: slug must be unique across all workspaces (400 if duplicate)",
          "OwnerAutoMembership": "Quality: creator automatically added as member with owner role"},
  why_roles={"WorkspaceOwnerRole": "Role realized when user creates and owns a workspace"},
  why_disps={"TransactionalDisposition": "Disposition to create workspace + membership in single transaction"},
  steps=["Check slug uniqueness in workspaces table",
         "Generate workspace ID: ws-{uuid.hex[:12]}",
         "Create WorkspaceModel with name, slug, owner_id=current_user.id",
         "Create WorkspaceMemberModel with role=owner",
         "Insert both in single transaction",
         "Commit and return Workspace"],
  data_props={"workspaceName": "string", "workspaceSlug": "string"})

p(folder="workspace_management", filename="workspace_member_invitation_process",
  label="Workspace Member Invitation Process",
  definition="A process that invites a user to a workspace by email, assigning them a role (admin/member/viewer), requiring the inviter to have admin or owner permissions.",
  impl="apps/api/app/api/endpoints/workspaces.py:237-279 invite_workspace_member()",
  who={"InvitingAdmin": "Admin or owner user sending the invitation",
       "InvitedUser": "User being added to the workspace (must exist by email)"},
  where={"InviteEndpoint": "API endpoint POST /api/workspaces/{id}/members/invite",
         "UsersTable": "PostgreSQL users table for email lookup",
         "WorkspaceMembersTable": "PostgreSQL workspace_members for membership creation"},
  when={"InvitationDuration": "40-80ms: user lookup + member check + insert"},
  how_know={"WorkspaceMemberInvite": "Pydantic model: email (3-255 chars), role (admin|member|viewer, default: member)",
            "InvitationResult": "Dict: status=invited, member_id"},
  how_is={"PermissionRequirement": "Quality: only admins and owners can invite members",
          "UniqueConstraint": "Quality: unique(workspace_id, user_id) prevents duplicate memberships"},
  why_roles={"MemberInviterRole": "Role realized when admin adds users to workspace"},
  why_disps={"EmailLookupDisposition": "Disposition to find user by email (404 if not registered)"},
  steps=["Check current user role is admin or owner (403 if not)",
         "Query users table for email (404 if not found)",
         "Check if user already a member (400 if duplicate)",
         "Create WorkspaceMemberModel with workspace_id, user_id, role",
         "Insert and commit",
         "Return success with member_id"],
  data_props={"inviteeEmail": "string", "assignedRole": "string"})

p(folder="workspace_management", filename="workspace_member_management_process",
  label="Workspace Member Management Process",
  definition="A process that updates member roles or removes members from a workspace, requiring admin or owner permissions and preventing owner self-removal.",
  impl="apps/api/app/api/endpoints/workspaces.py:282-348 remove_workspace_member(), update_workspace_member()",
  who={"WorkspaceAdmin": "Admin/owner managing workspace membership",
       "TargetMember": "Member whose role is being changed or who is being removed"},
  where={"MemberEndpoints": "DELETE /api/workspaces/{id}/members/{user_id}, PATCH /api/workspaces/{id}/members/{user_id}"},
  when={"ManagementDuration": "30-60ms per operation"},
  how_know={"RoleUpdate": "Dict: role (admin|member|viewer)",
            "RemovalResult": "Dict: status=removed"},
  how_is={"OwnerProtection": "Quality: workspace owner cannot be removed",
          "AdminRequirement": "Quality: only admins/owners can manage members"},
  why_roles={"MemberManagerRole": "Role realized when admin changes roles or removes members"},
  why_disps={"OwnerProtectionDisposition": "Disposition to prevent removal of workspace owner"},
  steps=["Validate current user is admin or owner",
         "For removal: check target is not owner, delete from workspace_members",
         "For update: modify role column (admin/member/viewer)",
         "Commit transaction",
         "Return result"],
  data_props={"targetUserId": "string", "newRole": "string"})

p(folder="workspace_management", filename="workspace_statistics_process",
  label="Workspace Statistics Process",
  definition="A process that calculates workspace-level counts for graph nodes, graph edges, conversations, and agents using SQL COUNT queries across 4 tables.",
  impl="apps/api/app/api/endpoints/workspaces.py:147-176 get_workspace_stats()",
  who={"StatisticsAggregator": "SQL query executor counting workspace resources"},
  where={"StatsEndpoint": "API endpoint GET /api/workspaces/{workspace_id}/stats"},
  when={"StatsDuration": "40-160ms for 4 COUNT queries"},
  how_know={"WorkspaceStats": "Dict: nodes (int), edges (int), conversations (int), agents (int)"},
  how_is={"QueryEfficiency": "Quality: 4 independent COUNT queries, could be optimized to 1"},
  why_roles={"ResourceCounterRole": "Role realized when system counts workspace resources"},
  why_disps={"SimpleCOUNTDisposition": "Disposition to use simple COUNT(*) per table"},
  steps=["Validate workspace access",
         "COUNT graph_nodes WHERE workspace_id = ?",
         "COUNT graph_edges WHERE workspace_id = ?",
         "COUNT conversations WHERE workspace_id = ?",
         "COUNT agent_configs WHERE workspace_id = ?",
         "Return statistics dict"],
  data_props={"nodeCount": "integer", "edgeCount": "integer", "conversationCount": "integer", "agentCount": "integer"})

# ----- SECRETS MANAGEMENT (3 processes) -----

p(folder="secrets_management", filename="secret_creation_process",
  label="Secret Creation Process",
  definition="A process that creates an encrypted secret (API key, credential, token) in a workspace using Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256), returning a masked value to the client.",
  impl="apps/api/app/api/endpoints/secrets.py:139-174 create_secret()",
  who={"SecretCreator": "Admin/owner user storing a secret",
       "FernetEncryptor": "Fernet encryption engine derived from settings.secret_key"},
  where={"SecretsEndpoint": "API endpoint POST /api/secrets",
         "SecretsTable": "PostgreSQL secrets table with encrypted_value column"},
  when={"EncryptionDuration": "30-60ms: uniqueness check + encryption + insert"},
  how_know={"SecretCreate": "Pydantic model: workspace_id, key (pattern ^[\\w-. ]+$), value (1-50000 chars), description, category",
            "EncryptedValue": "Fernet-encrypted string stored in encrypted_value column",
            "MaskedValue": "First 4 + **** + last 4 chars of value (or **** if <= 8 chars)",
            "SecretResponse": "Response: id, key, masked_value, description, category, timestamps"},
  how_is={"EncryptionStrength": "Quality: Fernet AES-128-CBC + HMAC-SHA256 encryption",
          "CategoryInference": "Quality: auto-infer category from key name (API_KEY->api_keys, TOKEN->tokens)"},
  why_roles={"SecretKeeperRole": "Role realized when system encrypts and stores sensitive values"},
  why_disps={"FernetEncryptionDisposition": "Disposition to encrypt values using Fernet derived from SHA-256 of secret_key",
             "CategoryInferenceDisposition": "Disposition to auto-categorize based on key name patterns"},
  steps=["Validate workspace access (admin/owner required)",
         "Check uniqueness: SELECT FROM secrets WHERE workspace_id=? AND key=?",
         "Infer category if not provided (API_KEY->api_keys, TOKEN->tokens, PASSWORD->credentials)",
         "Encrypt value: Fernet(base64(sha256(settings.secret_key))).encrypt(value)",
         "Generate secret ID (uuid4)",
         "Insert into secrets table: id, workspace_id, key, encrypted_value, description, category",
         "Mask value for response: value[:4] + **** + value[-4:]",
         "Return SecretResponse"],
  data_props={"secretKey": "string", "secretCategory": "string", "isEncrypted": "boolean"})

p(folder="secrets_management", filename="secret_resolution_process",
  label="Secret Resolution Process",
  definition="A process that decrypts a secret value by workspace_id and key for internal use (provider API key resolution), using Fernet symmetric decryption. Never exposed to API clients.",
  impl="apps/api/app/api/endpoints/secrets.py:332-343 resolve_secret_async()",
  who={"ProviderResolver": "Internal service needing decrypted API key",
       "FernetDecryptor": "Fernet decryption engine"},
  where={"SecretsTable": "PostgreSQL secrets table queried by workspace_id + key"},
  when={"ResolutionDuration": "15-25ms: query + decryption"},
  how_know={"DecryptedValue": "Plaintext API key after Fernet decryption",
            "SecretKeyLookup": "Query: SELECT * FROM secrets WHERE workspace_id=? AND key=?"},
  how_is={"InternalOnly": "Quality: this function is never exposed as an API endpoint",
          "NullSafety": "Quality: returns None if secret not found or decryption fails"},
  why_roles={"SecretDecryptorRole": "Role realized when system decrypts secrets for internal provider authentication"},
  why_disps={"GracefulFailureDisposition": "Disposition to return None on decryption error instead of raising"},
  steps=["Query secrets table: WHERE workspace_id=? AND key=?",
         "If not found: return None",
         "Decrypt: Fernet(derived_key).decrypt(encrypted_value)",
         "Return plaintext value",
         "On error: log warning, return None"],
  data_props={"lookupKey": "string", "foundSecret": "boolean"})

p(folder="secrets_management", filename="bulk_secret_import_process",
  label="Bulk Secret Import Process",
  definition="A process that imports multiple secrets from .env file format (KEY=VALUE lines), parsing, encrypting, and upserting each key-value pair into the secrets table.",
  impl="apps/api/app/api/endpoints/secrets.py:226-283 bulk_import_secrets()",
  who={"EnvFileParser": "Parser extracting KEY=VALUE pairs from .env content",
       "BulkEncryptor": "Fernet encryption applied to each value"},
  where={"ImportEndpoint": "API endpoint POST /api/secrets/import"},
  when={"ImportDuration": "100ms + 30ms per secret for parsing + encryption + upsert"},
  how_know={"SecretBulkImport": "Pydantic model: workspace_id, env_content (1-500000 chars)",
            "ImportResult": "Dict: imported (new count), updated (existing count)",
            "EnvFormat": "Format: KEY=VALUE or KEY='VALUE' or KEY=\"VALUE\" per line, # for comments"},
  how_is={"QuoteHandling": "Quality: strips single and double quotes from values",
          "CommentSkipping": "Quality: skips empty lines and lines starting with #"},
  why_roles={"BulkImporterRole": "Role realized when system imports multiple secrets at once"},
  why_disps={"UpsertDisposition": "Disposition to update existing secrets or create new ones"},
  steps=["Validate workspace access (admin/owner)",
         "Parse .env content line by line",
         "Skip empty lines and comments (#)",
         "Split each line by = to get key and value",
         "Strip quotes from value",
         "Encrypt value with Fernet",
         "Check if secret exists (by workspace_id + key)",
         "If exists: update encrypted_value and updated_at",
         "If new: insert new secret row",
         "Track imported and updated counts",
         "Commit transaction and return counts"],
  data_props={"importedCount": "integer", "updatedCount": "integer", "totalLines": "integer"})

# ----- REALTIME COLLABORATION (5 processes) -----

p(folder="realtime_collaboration", filename="websocket_connection_process",
  label="WebSocket Connection Process",
  definition="A process that establishes a Socket.IO WebSocket connection, authenticating the user and initializing session data with user_id and empty workspace set.",
  impl="apps/api/app/services/websocket.py:34-58 connect handler",
  who={"WebSocketClient": "Browser Socket.IO client connecting from frontend",
       "SocketIOServer": "Python-socketio AsyncServer handling connections"},
  where={"WebSocketEndpoint": "Socket.IO endpoint at /socket.io/ path"},
  when={"ConnectionDuration": "Less than 1ms for session initialization"},
  how_know={"SessionData": "Dict: user_id (str), workspaces (empty set)",
            "AuthPayload": "Dict from client: {user_id: string}",
            "SessionId": "Socket.IO sid (unique per connection)"},
  how_is={"AuthenticationLevel": "Quality: currently allows all connections (debugging mode)",
          "SessionIsolation": "Quality: each connection has independent session data"},
  why_roles={"ConnectionManagerRole": "Role realized when server accepts WebSocket connections"},
  why_disps={"DebugModeDisposition": "Disposition to allow all connections without JWT validation (temporary)"},
  steps=["Extract user_id from auth dict (or query string fallback)",
         "Store session data: session[user_id] = user_id",
         "Initialize empty workspaces set in session",
         "Return True to allow connection"],
  data_props={"sessionId": "string", "userId": "string"})

p(folder="realtime_collaboration", filename="workspace_presence_process",
  label="Workspace Presence Process",
  definition="A process that tracks which users are currently active in each workspace using Socket.IO rooms and in-memory presence dictionaries, broadcasting join/leave events.",
  impl="apps/api/app/services/websocket.py:92-164 join_workspace, leave_workspace, disconnect handlers",
  who={"PresenceTracker": "In-memory presence tracking system",
       "WorkspaceRoom": "Socket.IO room grouping users in same workspace"},
  where={"PresenceEndpoints": "Socket.IO events: join_workspace, leave_workspace, disconnect"},
  when={"PresenceUpdateDuration": "Less than 1ms (in-memory set operations)"},
  how_know={"WorkspacePresence": "Dict[str, Set[str]]: workspace_id -> set of user_ids",
            "UserWorkspaces": "Dict[str, Set[str]]: user_id -> set of workspace_ids",
            "JoinEvent": "Broadcast: {user_id, workspace_id, timestamp}",
            "LeaveEvent": "Broadcast: {user_id, workspace_id, timestamp}"},
  how_is={"RealTimeAccuracy": "Quality: presence updates immediately on join/leave/disconnect",
          "DisconnectCleanup": "Quality: user removed from all workspaces on disconnect"},
  why_roles={"PresenceManagerRole": "Role realized when system tracks active users per workspace"},
  why_disps={"BroadcastDisposition": "Disposition to broadcast user_joined/user_left events to room"},
  steps=["Join: enter Socket.IO room workspace:{id}, add to presence dicts, broadcast user_joined",
         "Leave: leave room, remove from presence dicts, broadcast user_left",
         "Disconnect: remove from all workspace rooms and presence dicts, broadcast user_left for each",
         "Return current presence list for joined workspace"],
  data_props={"activeUserCount": "integer", "workspaceId": "string"})

p(folder="realtime_collaboration", filename="typing_indicator_process",
  label="Typing Indicator Process",
  definition="A process that broadcasts real-time typing status indicators to all users in a workspace, showing who is currently typing in which conversation.",
  impl="apps/api/app/services/websocket.py:168-207 typing_start, typing_stop handlers",
  who={"TypingUser": "User currently composing a message",
       "WorkspaceParticipants": "Other users in the workspace who see the indicator"},
  where={"TypingEvents": "Socket.IO events: typing_start, typing_stop"},
  when={"TypingLatency": "Less than 1ms for event broadcast"},
  how_know={"TypingEvent": "Broadcast: {user_id, conversation_id, typing: true/false}",
            "TypingData": "Input: {workspace_id, conversation_id}"},
  how_is={"SenderExclusion": "Quality: typing indicator not sent back to the typing user (skip_sid)",
          "ConversationScoping": "Quality: typing is scoped to specific conversation within workspace"},
  why_roles={"TypingNotifierRole": "Role realized when system broadcasts typing status"},
  why_disps={"SkipSenderDisposition": "Disposition to exclude sender from receiving their own typing event"},
  steps=["Get user_id from session",
         "On typing_start: broadcast user_typing {user_id, conversation_id, typing: true}",
         "On typing_stop: broadcast user_typing {user_id, conversation_id, typing: false}",
         "Broadcast to workspace:{workspace_id} room, excluding sender"],
  data_props={"conversationId": "string", "isTyping": "boolean"})

p(folder="realtime_collaboration", filename="message_broadcast_process",
  label="Message Broadcast Process",
  definition="A process that notifies all users in a workspace when a new message is created in any conversation, broadcasting the message content in real-time via Socket.IO.",
  impl="apps/api/app/services/websocket.py:211-226 new_message handler",
  who={"MessageSender": "User or system that created the new message",
       "WorkspaceSubscribers": "All connected users in the workspace room"},
  where={"MessageEvent": "Socket.IO event: new_message"},
  when={"BroadcastLatency": "Less than 1ms for event emission"},
  how_know={"NewMessageEvent": "Broadcast: {conversation_id, message (dict), timestamp}",
            "MessageData": "Input: {workspace_id, conversation_id, message}"},
  how_is={"IncludeSender": "Quality: sender receives their own message broadcast (no skip_sid)",
          "RealtimeDelivery": "Quality: message delivered instantly to all workspace subscribers"},
  why_roles={"MessageNotifierRole": "Role realized when system broadcasts new messages"},
  why_disps={"InclusiveBroadcastDisposition": "Disposition to include sender in broadcast (unlike typing)"},
  steps=["Receive new_message event with workspace_id, conversation_id, message",
         "Broadcast to workspace:{workspace_id} room",
         "Include conversation_id, message, and timestamp",
         "Do NOT exclude sender (all users see the message)"],
  data_props={"conversationId": "string", "messageRole": "string"})

p(folder="realtime_collaboration", filename="collaborative_cursor_process",
  label="Collaborative Cursor Process",
  definition="A process that broadcasts cursor position updates for collaborative editing, showing where each user's cursor is positioned in shared documents.",
  impl="apps/api/app/services/websocket.py:230-249 cursor_update handler",
  who={"CursorOwner": "User whose cursor position is being tracked",
       "Collaborators": "Other users viewing the same document"},
  where={"CursorEvent": "Socket.IO event: cursor_update"},
  when={"CursorLatency": "Less than 1ms for position broadcast"},
  how_know={"CursorUpdate": "Broadcast: {user_id, document_id, position (dict)}",
            "Position": "Cursor coordinates: line, column, or x, y depending on editor"},
  how_is={"SenderExclusion": "Quality: cursor position not sent back to cursor owner (skip_sid)",
          "DocumentScoping": "Quality: cursor updates scoped to specific document_id"},
  why_roles={"CursorBroadcasterRole": "Role realized when system shares cursor positions"},
  why_disps={"PositionTrackingDisposition": "Disposition to broadcast cursor coordinates in real-time"},
  steps=["Get user_id from session",
         "Receive cursor_update with workspace_id, document_id, position",
         "Broadcast to workspace:{workspace_id} room, excluding sender",
         "Include user_id, document_id, position in event"],
  data_props={"documentId": "string", "cursorLine": "integer", "cursorColumn": "integer"})

# ----- MODEL REGISTRY (2 processes) -----

p(folder="model_registry", filename="model_discovery_process",
  label="Model Discovery Process",
  definition="A process that provides a catalog of 60+ AI models from the in-memory MODEL_REGISTRY dictionary, supporting filtering by provider and returning full model metadata including capabilities.",
  impl="apps/api/app/services/model_registry.py:488-512 get_models_for_provider(), get_all_models(), get_model_by_id()",
  who={"ModelRegistry": "In-memory Python dict with MODEL_REGISTRY[provider] = list[ModelInfo]"},
  where={"RegistryModule": "apps/api/app/services/model_registry.py (in-memory, no database)"},
  when={"DiscoveryLatency": "Less than 1ms (in-memory dict lookup)"},
  how_know={"ModelInfo": "Dict: id, name, provider, context_window, supports_streaming, supports_vision, supports_function_calling, max_output_tokens, released",
            "ProviderList": "9 providers: openai, anthropic, xai, mistral, perplexity, google, openrouter, cloudflare, ollama",
            "ProviderLogo": "Logo URL from PROVIDER_LOGOS mapping via get_logo_for_provider()"},
  how_is={"CatalogCompleteness": "Quality: 60+ models manually cataloged across 9 providers",
          "ManualMaintenance": "Quality: registry requires manual updates for new models"},
  why_roles={"ModelCatalogRole": "Role realized when system provides model information for UI and routing"},
  why_disps={"StaticRegistryDisposition": "Disposition to use static in-memory registry (not auto-discovered)"},
  steps=["If provider specified: return MODEL_REGISTRY[provider] list",
         "If no provider: flatten all provider lists into single list",
         "For model lookup: iterate all providers to find by model ID",
         "Return ModelInfo objects with full capability metadata"],
  data_props={"totalModels": "integer", "providerCount": "integer"})

p(folder="model_registry", filename="provider_availability_check_process",
  label="Provider Availability Check Process",
  definition="A process that determines which AI providers are configured and available for a user by checking workspace secrets for API keys and environment variables, returning providers with their model catalogs.",
  impl="apps/api/app/api/endpoints/providers.py:66-212 list_available_providers()",
  who={"AvailabilityChecker": "Backend logic scanning secrets and environment for provider keys",
       "SecretStore": "PostgreSQL secrets table with encrypted API keys"},
  where={"ProvidersEndpoint": "API endpoint GET /api/providers/available"},
  when={"CheckDuration": "100-250ms: workspace queries + secret lookups + registry"},
  how_know={"Provider": "Response object: id, name, type, has_api_key (bool), models list",
            "APIKeyPatterns": "Secret key patterns checked: OPENAI_API_KEY, ANTHROPIC_API_KEY, XAI_API_KEY, MISTRAL_API_KEY, etc."},
  how_is={"FallbackChain": "Quality: checks secrets first, then environment variables",
          "OllamaInclusion": "Quality: Ollama always included (no API key needed)"},
  why_roles={"AvailabilityReporterRole": "Role realized when system reports which providers are usable"},
  why_disps={"EnvironmentFallbackDisposition": "Disposition to check env vars when no database secret found"},
  steps=["Get user workspace IDs from workspace_members",
         "For each provider: check has_api_key_configured(key_name, workspace_ids, db)",
         "has_api_key_configured: query secrets table, fallback to os.environ.get()",
         "For providers with keys: get models from MODEL_REGISTRY",
         "Always include Ollama with its models",
         "Return list of Provider objects with has_api_key and models"],
  data_props={"configuredProviderCount": "integer", "totalModelCount": "integer"})

# ----- FRONTEND STATE (5 processes) -----

p(folder="frontend_state", filename="auth_state_process",
  label="Authentication State Process",
  definition="A process managing user authentication state in the frontend Zustand store, handling login, register, logout, token persistence, and automatic 401 detection with redirect to /login.",
  impl="apps/web/src/stores/auth.ts useAuthStore, authFetch()",
  who={"ZustandAuthStore": "Zustand store managing auth state in browser",
       "LocalStorage": "Browser localStorage persisting auth tokens"},
  where={"AuthStorageKey": "localStorage key: nexus-auth"},
  when={"LoginDuration": "200-1000ms for API call + state update + localStorage write"},
  how_know={"AuthState": "State: user (User|null), token (string|null), isAuthenticated (bool), isLoading, error",
            "AuthActions": "login(email, password), register(email, password, name), logout(), checkAuth()",
            "AuthFetch": "Global fetch wrapper that auto-detects 401 and redirects to /login"},
  how_is={"TokenPersistence": "Quality: token persisted in localStorage, survives page refresh",
          "AutoLogoutOn401": "Quality: any 401 response triggers automatic logout + redirect"},
  why_roles={"SessionManagerRole": "Role realized when frontend manages user session lifecycle"},
  why_disps={"Auto401DetectionDisposition": "Disposition to intercept 401 responses and force re-authentication"},
  steps=["Login: POST /api/auth/login, store user+token in state and localStorage",
         "Register: POST /api/auth/register, same flow as login",
         "Logout: clear auth state, remove 6 localStorage keys, redirect",
         "authFetch: wrapper that adds Authorization header and detects 401",
         "checkAuth: validate token on app load"],
  data_props={"isAuthenticated": "boolean", "tokenPresent": "boolean"})

p(folder="frontend_state", filename="workspace_state_process",
  label="Workspace State Process",
  definition="A process managing workspace navigation, conversations, messages, and agent selection in the Zustand store with throttled localStorage persistence to prevent browser freeze during streaming.",
  impl="apps/web/src/stores/workspace.ts useWorkspaceStore",
  who={"ZustandWorkspaceStore": "Zustand store managing workspace state",
       "ThrottledLocalStorage": "Custom storage wrapper batching writes to max 1/second"},
  where={"WorkspaceStorageKey": "localStorage key: nexus-workspace-storage"},
  when={"StreamingThrottle": "1000ms batching interval for localStorage writes during streaming"},
  how_know={"WorkspaceState": "State: conversations, activeConversationId, selectedAgent, workspaces, currentWorkspaceId, projects, branches",
            "ConversationActions": "createConversation(), addMessage(), updateLastMessage(), deleteConversation()",
            "WorkspaceActions": "fetchWorkspaces(), setCurrentWorkspace(), createWorkspace(), deleteWorkspace()",
            "BranchActions": "createBranch(), deleteBranch(), checkoutBranch(), commit(), mergeBranch()"},
  how_is={"ThrottlePerformance": "Quality: prevents JSON.stringify + localStorage.setItem on every streaming token",
          "WorkspaceIsolation": "Quality: conversations filtered by currentWorkspaceId"},
  why_roles={"StateOrchestratorRole": "Role realized when store coordinates navigation, chat, and workspace data"},
  why_disps={"ThrottledPersistDisposition": "Disposition to batch localStorage writes during high-frequency updates"},
  steps=["On mount: fetchWorkspaces() from /api/workspaces/",
         "Validate currentWorkspaceId against fetched workspaces",
         "On message: addMessage() appends to conversation, triggers throttled persist",
         "On streaming: updateLastMessage() appends token to last message content",
         "On workspace change: setCurrentWorkspace(), re-filter conversations",
         "Persist: throttled to max 1 write/second to prevent browser freeze"],
  data_props={"conversationCount": "integer", "activeConversationId": "string", "selectedAgent": "string"})

p(folder="frontend_state", filename="agents_state_process",
  label="Agents State Process",
  definition="A process managing the list of available AI agents in the frontend, fetching from API per workspace and syncing selected agent validity when workspace changes.",
  impl="apps/web/src/stores/agents.ts useAgentsStore",
  who={"ZustandAgentsStore": "Zustand store managing agent list and selection"},
  where={"AgentsStorageKey": "localStorage key: nexus-agents"},
  when={"FetchDuration": "100-300ms for API call to /api/agents/?workspace_id={id}"},
  how_know={"Agent": "Interface: id, name, description, icon, systemPrompt, provider, modelId, logoUrl, tools, capabilities",
            "AgentActions": "fetchAgents(workspaceId), addAgent(), updateAgent(), deleteAgent(), syncAgentsFromProviders()"},
  how_is={"WorkspaceScopedFetch": "Quality: agents fetched per workspace, filtered server-side",
          "SelectedAgentValidation": "Quality: resets selectedAgent if current selection invalid after fetch"},
  why_roles={"AgentCatalogRole": "Role realized when store provides agent list for UI selection"},
  why_disps={"AutoResetDisposition": "Disposition to reset selected agent to first available if current becomes invalid"},
  steps=["On workspace change: fetchAgents(workspaceId) from /api/agents/?workspace_id={id}",
         "Format API response to Agent[] array",
         "Check if selectedAgent still valid in new list",
         "If invalid: reset to first available agent",
         "Persist agent list to localStorage"],
  data_props={"agentCount": "integer", "selectedAgentId": "string"})

p(folder="frontend_state", filename="knowledge_graph_state_process",
  label="Knowledge Graph State Process",
  definition="A process managing knowledge graph visualization state including named graphs, nodes, edges, views, saved queries, zoom level, and selection in the frontend Zustand store.",
  impl="apps/web/src/stores/knowledge-graph.ts useKnowledgeGraphStore",
  who={"ZustandGraphStore": "Zustand store managing graph visualization state"},
  where={"GraphStorageKey": "localStorage key: nexus-knowledge-graph"},
  when={"GraphLoadDuration": "50-500ms for workspace graph load from API"},
  how_know={"GraphState": "State: graphs, nodes, edges, selectedNodeId, selectedEdgeId, views, activeViewType, queries, zoomLevel",
            "GraphViewTypes": "Types: visual, table, sparql, schema, statistics",
            "SavedQuery": "Interface: name, query, language (sparql/cypher/natural), results, lastRun"},
  how_is={"PositionPersistence": "Quality: node x,y positions persisted across sessions",
          "MultiGraphSupport": "Quality: supports multiple named graphs with visibility toggling"},
  why_roles={"GraphVisualizerRole": "Role realized when store manages graph display and interaction"},
  why_disps={"BFOColorSchemeDisposition": "Disposition to color nodes by BFO 7 Buckets category"},
  steps=["Load graph from API: GET /api/graph/workspaces/{workspace_id}",
         "Create/manage named graphs with node and edge counts",
         "Track selected node/edge for detail panel",
         "Manage view types (visual/table/sparql/schema/statistics)",
         "Execute queries via POST /api/graph/query",
         "Persist graphs, views, queries to localStorage"],
  data_props={"nodeCount": "integer", "edgeCount": "integer", "zoomLevel": "float", "viewType": "string"})

p(folder="frontend_state", filename="files_state_process",
  label="Files State Process",
  definition="A process managing file browser state including directory listing, open files, file contents, unsaved changes, and dual storage source support (local + cloud) in the Zustand store.",
  impl="apps/web/src/stores/files.ts useFilesStore",
  who={"ZustandFilesStore": "Zustand store managing file browser and editor state"},
  where={"FileBrowserUI": "Sidebar files section + lab section",
         "FileAPI": "Backend endpoints /api/files/*"},
  when={"FileListDuration": "50-500ms for directory listing from API",
        "FileReadDuration": "50-2000ms depending on file size"},
  how_know={"FilesState": "State: files, currentPath, openFiles, activeFile, fileContents, unsavedChanges, storageSources",
            "FileActions": "fetchFiles(), createFile(), createFolder(), uploadFile(), readFile(), saveFile(), deleteFile(), renameFile()",
            "StorageSource": "Interface: id, name, category (local/cloud), enabled, connected",
            "SyncedFolder": "Interface: id, name, localPath, handle (FileSystemDirectoryHandle), syncEnabled"},
  how_is={"DualStorageSupport": "Quality: supports both local filesystem and cloud (S3) storage",
          "UnsavedTracking": "Quality: tracks per-file unsaved changes for save prompts",
          "FileSystemAccessAPI": "Quality: uses browser File System Access API for local folder sync"},
  why_roles={"FileManagerRole": "Role realized when store manages file browsing, editing, and storage"},
  why_disps={"LazyContentLoadDisposition": "Disposition to load file contents only when file is opened (not on list)"},
  steps=["fetchFiles(path): GET /api/files/?path={path}",
         "openFile(path): add to openFiles, set as activeFile",
         "readFile(path): GET /api/files/{path}, cache in fileContents",
         "saveFile(path): PUT /api/files/{path} with cached content",
         "uploadFile(file): POST /api/files/upload with multipart",
         "syncLocalFolder(): use File System Access API to sync browser folder"],
  data_props={"openFileCount": "integer", "currentPath": "string", "hasUnsavedChanges": "boolean"})

# ----- ABI SERVER CONFIG (1 process) -----

p(folder="abi_server_config", filename="abi_server_crud_process",
  label="ABI Server CRUD Process",
  definition="A process that manages external ABI (Agentic Brain Infrastructure) server configurations per workspace, including create, read, update, and delete operations on the abi_servers PostgreSQL table.",
  impl="apps/api/app/api/endpoints/abi.py:65-205 list/create/get/update/delete_abi_server()",
  who={"ABIServerManager": "Backend logic managing ABI server configurations",
       "WorkspaceAdmin": "Admin/owner user configuring ABI servers"},
  where={"ABIEndpoints": "API endpoints /api/abi/workspaces/{id}/abi-servers/*",
         "ABIServersTable": "PostgreSQL abi_servers table with workspace_id FK"},
  when={"CRUDDuration": "30-60ms per operation"},
  how_know={"ABIServerCreate": "Pydantic model: name (1-255), endpoint (URL), api_key (optional)",
            "ABIServerRecord": "DB row: id (abi-{uuid}), workspace_id, name, endpoint, api_key, enabled, timestamps",
            "ABIServerUpdate": "Partial update: name, endpoint, api_key, enabled"},
  how_is={"EndpointUniqueness": "Quality: unique(workspace_id, endpoint) prevents duplicate server configs",
          "APIKeyStorage": "Quality: api_key stored in plaintext (TODO: encrypt with Fernet)"},
  why_roles={"ServerConfiguratorRole": "Role realized when admin configures external ABI server connections"},
  why_disps={"CascadeDeleteDisposition": "Disposition to cascade delete when workspace is deleted"},
  steps=["List: SELECT FROM abi_servers WHERE workspace_id=?",
         "Create: validate endpoint uniqueness, generate ID abi-{uuid}, insert row",
         "Get: SELECT by server_id and workspace_id (404 if not found)",
         "Update: modify name/endpoint/api_key/enabled, set updated_at",
         "Delete: remove server row (agents remain in agent_configs)"],
  data_props={"serverName": "string", "serverEndpoint": "string", "isEnabled": "boolean"})

# ----- BACKGROUND CLEANUP (2 processes) -----

p(folder="background_cleanup", filename="token_cleanup_process",
  label="Token Cleanup Process",
  definition="A process that removes expired refresh tokens and revoked access tokens from the database to prevent unbounded table growth, intended to run as a scheduled background task.",
  impl="apps/api/app/services/refresh_token.py:217-231 cleanup functions",
  who={"CleanupScheduler": "Background task executor (not yet scheduled, manual call)"},
  where={"RefreshTokensTable": "PostgreSQL refresh_tokens table",
         "RevokedTokensTable": "PostgreSQL revoked_tokens table"},
  when={"CleanupDuration": "50-200ms for 2 DELETE queries",
        "ScheduleFrequency": "Intended: daily (not yet implemented)"},
  how_know={"ExpiredRefreshTokens": "Rows WHERE expires_at < NOW() in refresh_tokens",
            "ExpiredRevokedTokens": "Rows WHERE expires_at < NOW() in revoked_tokens",
            "DeletedCount": "Number of rows removed per table"},
  how_is={"TableGrowthPrevention": "Quality: prevents unbounded growth of token tables",
          "NotYetScheduled": "Quality: requires manual invocation or future cron job"},
  why_roles={"DatabaseJanitorRole": "Role realized when system cleans expired security tokens"},
  why_disps={"ExpirationBasedDisposition": "Disposition to delete based on expires_at timestamp comparison"},
  steps=["Get current timestamp",
         "DELETE FROM refresh_tokens WHERE expires_at < NOW()",
         "DELETE FROM revoked_tokens WHERE expires_at < NOW()",
         "Log number of deleted rows"],
  data_props={"deletedRefreshTokens": "integer", "deletedRevokedTokens": "integer"})

p(folder="background_cleanup", filename="rate_limit_cleanup_process",
  label="Rate Limit Cleanup Process",
  definition="A process that removes rate limit events older than 24 hours from the rate_limit_events table to prevent unbounded growth, intended as a daily background task.",
  impl="apps/api/app/services/rate_limit.py:66-75 cleanup_old_rate_limit_events()",
  who={"CleanupScheduler": "Background task executor (not yet scheduled)"},
  where={"RateLimitEventsTable": "PostgreSQL rate_limit_events table"},
  when={"CleanupDuration": "50-200ms for single DELETE query",
        "RetentionWindow": "24 hours of rate limit history retained"},
  how_know={"CutoffTimestamp": "datetime: NOW() - 24 hours",
            "DeletedEvents": "Rows WHERE created_at < cutoff"},
  how_is={"RetentionPeriod": "Quality: 24-hour retention window for rate limit forensics",
          "NotYetScheduled": "Quality: requires manual invocation or cron job setup"},
  why_roles={"EventCleanerRole": "Role realized when system purges old rate limit records"},
  why_disps={"TimeBasedPurgeDisposition": "Disposition to delete events older than 24-hour threshold"},
  steps=["Calculate cutoff: NOW() - 24 hours",
         "DELETE FROM rate_limit_events WHERE created_at < cutoff",
         "Log number of deleted events"],
  data_props={"deletedEventCount": "integer", "retentionHours": "integer"})


# =====================================================================
# MAIN EXECUTION
# =====================================================================

def main():
    print(f"Generating {len(ALL_PROCESSES)} process ontology files...")
    print(f"Output directory: {OUTPUT_DIR}\n")
    
    folders = {}
    for proc in ALL_PROCESSES:
        path = write_process(**proc)
        folder = proc['folder']
        folders.setdefault(folder, []).append(path.name)
        print(f"  ✓ {folder}/{path.name}")
    
    print(f"\n{'='*60}")
    print(f"Generated {len(ALL_PROCESSES)} process ontology files")
    print(f"Across {len(folders)} folders:\n")
    for folder, files in sorted(folders.items()):
        print(f"  {folder}/ ({len(files)} processes)")
        for f in files:
            print(f"    - {f}")

if __name__ == "__main__":
    main()
