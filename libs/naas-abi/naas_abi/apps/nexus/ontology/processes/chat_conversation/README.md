# Chat & Conversation Processes
## BFO 7 Buckets Compliant Ontologies

This folder contains individual Turtle ontology files for each chat, conversation, and AI-powered dialogue process in the NEXUS platform.

## Process Files

| File | Process | Description |
|------|---------|-------------|
| `chat_completion_process.ttl` | **Chat Completion** | Generates AI response via OpenAI/Anthropic/Ollama/Cloudflare/ABI |
| `chat_streaming_process.ttl` | **Chat Streaming** | Streams tokens incrementally via Server-Sent Events (SSE) |
| `multi_agent_conversation_process.ttl` | **Multi-Agent Chat** | Manages multi-agent dialogue with identity markers |
| `conversation_creation_process.ttl` | **Conversation Creation** | Creates conversation entity with workspace linkage |
| `message_persistence_process.ttl` | **Message Persistence** | Stores user/assistant messages in database |
| `web_search_integration_process.ttl` | **Web Search** | Injects Wikipedia/DuckDuckGo results as context |
| `provider_routing_process.ttl` | **Provider Routing** | Resolves LLM provider from agent config + secrets |

## Implementation

**Backend:** `apps/api/app/api/endpoints/chat.py`, `apps/api/app/services/providers.py`

## Supported Providers

- **OpenAI:** GPT-4, GPT-4 Turbo, GPT-3.5
- **Anthropic:** Claude 3 (Opus, Sonnet, Haiku)
- **Ollama:** Local LLMs (Llama 3, Mistral, Gemma, Qwen)
- **Cloudflare:** Workers AI (edge inference)
- **ABI:** External Agentic Brain Infrastructure servers
- **XAI:** Grok models
- **Mistral:** Mistral Large, Medium, Small
- **OpenRouter:** Multi-provider routing
- **Perplexity:** Search-augmented generation
- **Google:** Gemini 1.5 Pro/Flash

## Features

- **Streaming:** Real-time token-by-token SSE delivery
- **Multi-Agent:** Handle conversations with multiple AI agents
- **Multimodal:** Image input support (GPT-4 Vision, Claude 3, Llama 3.2 Vision)
- **Web Search:** Automatic Wikipedia + DuckDuckGo integration
- **Context Management:** Respects model context windows (8K-200K tokens)
- **Provider Fallback:** Ollama auto-detection if no API key configured

## BFO 7 Buckets Structure

1. **WHAT (Process):** BFO_0000015 - Chat completion, streaming, routing
2. **WHO (Material Entity):** BFO_0000040 - HumanUser, AIAgent, LLMProvider, ChatBackend
3. **WHERE (Site):** BFO_0000029 - Chat endpoints (/api/chat/*), provider APIs
4. **WHEN (Temporal Region):** BFO_0000008 - Streaming duration (1-30s), conversation session
5. **HOW WE KNOW (GDC):** BFO_0000031 - Messages, system prompts, SSE chunks, agent config
6. **HOW IT IS (Quality):** BFO_0000019 - Response latency, streaming throughput, context length
7. **WHY (Role/Disposition):** BFO_0000023/BFO_0000016 - Participant role, streaming capability

## Streaming Protocol

NEXUS supports multiple SSE formats:

- **W3C Standard SSE:** `event: message\ndata: content\n\n`
- **OpenAI pseudo-SSE:** `data: {"choices":[{"delta":{"content":"token"}}]}\n\n`
- **Anthropic SSE:** `event: content_block_delta\ndata: {"delta":{"text":"token"}}\n\n`
- **ABI Custom SSE:** `event: ai_message\ndata: content\n\n` (multi-line data per event)

See `docs/SSE_STREAMING_STANDARDS.md` for detailed protocol comparison.

## Usage

```turtle
@prefix nexus: <http://nexus.platform/ontology/> .

owl:imports <http://nexus.platform/ontology/_shared/common_entities> ,
            <http://nexus.platform/ontology/chat_conversation/chat_completion_process> .

# Query all chat processes
SELECT ?process ?agent ?message WHERE {
    ?process a nexus:ChatCompletionProcess .
    ?process bfo:BFO_0000057 ?agent .  # has participant
    ?agent a nexus:AIAgent .
    ?message nexus:hasConversationId ?conv_id .
}
```

## Related

- **Shared Entities:** `../_shared/common_entities.ttl`
- **Auth Processes:** `../authentication/`
- **Provider Adapters:** `../../docs/PROVIDER_ADAPTER_ARCHITECTURE.md`
- **SSE Standards:** `../../docs/SSE_STREAMING_STANDARDS.md`
- **Main Index:** `../README.md`
