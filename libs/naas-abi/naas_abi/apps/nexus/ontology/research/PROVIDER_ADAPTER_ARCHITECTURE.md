# Provider Adapter Architecture - Multi-Standard Streaming Hub

## Vision

**NEXUS must be protocol-agnostic.** It should seamlessly integrate AI providers with different streaming standards, formats, and behaviors without forcing them into a single mold.

**Problem:** Current implementation assumes OpenAI-like streaming everywhere. This breaks with W3C-compliant SSE (ABI), custom protocols, and future providers.

**Solution:** Provider Adapter pattern with format detection and normalization.

---

## Current State (Problems)

### Tightly Coupled to OpenAI Format

**apps/api/app/api/endpoints/chat.py:**
```python
# Current: Every provider forced into OpenAI JSON format
elif provider.type == "abi":
    async for chunk in stream_with_abi(...):
        full_response += chunk
        escaped = chunk.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        yield f'data: {{"content": "{escaped}"}}\n\n'  # ❌ Forced JSON wrapping
```

**Issues:**
1. Every provider handler must output raw text
2. Backend re-wraps everything as `{"content": "..."}`
3. Frontend expects this specific format
4. No way to send rich metadata (tool calls, thinking, file attachments)
5. Adding new providers = copy-paste + adapt

---

## Proposed Architecture

### 1. Provider Adapter Interface

```python
# apps/api/app/services/providers/base.py

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any
from enum import Enum

class StreamEventType(Enum):
    """Normalized event types across all providers"""
    CONTENT = "content"              # Regular text content
    THINKING = "thinking"            # Reasoning/chain-of-thought
    TOOL_CALL = "tool_call"          # Function/tool invocation
    TOOL_RESULT = "tool_result"      # Tool execution result
    FILE = "file"                    # File/attachment reference
    LINK = "link"                    # URL/link
    ERROR = "error"                  # Error condition
    METADATA = "metadata"            # Additional metadata
    DONE = "done"                    # Stream complete

class StreamEvent:
    """Normalized streaming event"""
    type: StreamEventType
    content: str | None = None
    metadata: Dict[str, Any] = {}
    
    def to_json(self) -> dict:
        return {
            "type": self.type.value,
            "content": self.content,
            "metadata": self.metadata,
        }

class ProviderAdapter(ABC):
    """Base class for all provider adapters"""
    
    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        config: ProviderConfig,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream responses from provider.
        
        Returns normalized StreamEvent objects that frontend can consume.
        Each adapter handles its provider's specific format internally.
        """
        pass
    
    @abstractmethod
    def detect_format(self, response_headers: dict) -> str:
        """
        Detect the streaming format from response headers.
        Returns: 'sse', 'json-lines', 'websocket', 'custom', etc.
        """
        pass
```

### 2. Provider-Specific Adapters

#### OpenAI Adapter

```python
# apps/api/app/services/providers/openai_adapter.py

class OpenAIAdapter(ProviderAdapter):
    """Adapter for OpenAI Chat Completions API"""
    
    async def stream(self, messages, config, system_prompt=None):
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", config.endpoint, ...) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        content = line[6:]
                        if content == "[DONE]":
                            yield StreamEvent(type=StreamEventType.DONE)
                            break
                        
                        data = json.loads(content)
                        delta = data["choices"][0]["delta"]
                        
                        if "content" in delta:
                            yield StreamEvent(
                                type=StreamEventType.CONTENT,
                                content=delta["content"]
                            )
    
    def detect_format(self, headers):
        return "openai-sse"
```

#### ABI Adapter (W3C SSE)

```python
# apps/api/app/services/providers/abi_adapter.py

class ABIAdapter(ProviderAdapter):
    """Adapter for ABI/Naas servers using W3C-compliant SSE"""
    
    async def stream(self, messages, config, system_prompt=None):
        # Extract latest message for ABI's prompt format
        prompt = self._extract_latest_message(messages)
        thread_id = self._generate_thread_id(messages)
        
        url = f"{config.endpoint}/agents/{config.model}/stream-completion?token={config.api_key}"
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST", url,
                json={"prompt": prompt, "thread_id": thread_id}
            ) as response:
                current_event = None
                data_buffer = []
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        # Blank line = dispatch accumulated event (W3C SSE)
                        if current_event and data_buffer:
                            content = "\n".join(data_buffer)
                            
                            # Classify content type
                            if current_event == "ai_message":
                                # Check if it's a link, file, or plain text
                                event_type = self._classify_content(content)
                                yield StreamEvent(
                                    type=event_type,
                                    content=content
                                )
                            
                            data_buffer = []
                        continue
                    
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                    elif line.startswith("data: "):
                        content = line[6:]
                        if content == "[DONE]":
                            yield StreamEvent(type=StreamEventType.DONE)
                            break
                        # W3C: Accumulate multiple data: lines
                        data_buffer.append(content)
    
    def _classify_content(self, content: str) -> StreamEventType:
        """Detect if content is link, file, or plain text"""
        if content.strip().startswith("http"):
            return StreamEventType.LINK
        elif "powerpoint" in content.lower() or ".pptx" in content.lower():
            return StreamEventType.FILE
        else:
            return StreamEventType.CONTENT
    
    def detect_format(self, headers):
        return "w3c-sse"
```

#### Anthropic Adapter

```python
# apps/api/app/services/providers/anthropic_adapter.py

class AnthropicAdapter(ProviderAdapter):
    """Adapter for Anthropic Claude API"""
    
    async def stream(self, messages, config, system_prompt=None):
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", config.endpoint, ...) as response:
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        data = json.loads(line[6:])
                        
                        # Map Anthropic events to normalized events
                        if event_type == "content_block_delta":
                            yield StreamEvent(
                                type=StreamEventType.CONTENT,
                                content=data["delta"]["text"]
                            )
                        elif event_type == "message_stop":
                            yield StreamEvent(type=StreamEventType.DONE)
    
    def detect_format(self, headers):
        return "anthropic-sse"
```

### 3. Adapter Registry

```python
# apps/api/app/services/providers/registry.py

class AdapterRegistry:
    """Central registry for provider adapters"""
    
    _adapters: Dict[str, Type[ProviderAdapter]] = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "abi": ABIAdapter,
        "openrouter": OpenAIAdapter,  # OpenRouter is OpenAI-compatible
        "ollama": OllamaAdapter,
        # ... more providers
    }
    
    @classmethod
    def get_adapter(cls, provider_type: str) -> ProviderAdapter:
        """Get adapter instance for provider type"""
        adapter_class = cls._adapters.get(provider_type)
        if not adapter_class:
            raise ValueError(f"Unknown provider: {provider_type}")
        return adapter_class()
    
    @classmethod
    def register(cls, provider_type: str, adapter_class: Type[ProviderAdapter]):
        """Register a new adapter (for plugins/extensions)"""
        cls._adapters[provider_type] = adapter_class
```

### 4. Updated Chat Endpoint

```python
# apps/api/app/api/endpoints/chat.py

@router.post("/stream")
async def stream_chat(...):
    # ... existing auth/validation ...
    
    # Get provider config
    provider = await _resolve_provider(...)
    
    # Get appropriate adapter
    adapter = AdapterRegistry.get_adapter(provider.type)
    
    # Stream using adapter
    async def generate():
        async for event in adapter.stream(provider_messages, provider_config, system_prompt):
            # Send normalized events to frontend
            yield f'data: {json.dumps(event.to_json())}\n\n'
            
            if event.type == StreamEventType.DONE:
                break
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 5. Frontend Event Handling

```typescript
// apps/web/src/lib/streaming.ts

export enum StreamEventType {
  CONTENT = "content",
  THINKING = "thinking",
  TOOL_CALL = "tool_call",
  TOOL_RESULT = "tool_result",
  FILE = "file",
  LINK = "link",
  ERROR = "error",
  METADATA = "metadata",
  DONE = "done",
}

export interface StreamEvent {
  type: StreamEventType;
  content?: string;
  metadata?: Record<string, any>;
}

export async function* parseNexusStream(response: Response): AsyncGenerator<StreamEvent> {
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  
  if (!reader) return;
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') break;
        
        try {
          const event = JSON.parse(data) as StreamEvent;
          yield event;
        } catch (e) {
          console.error('Failed to parse stream event:', e);
        }
      }
    }
  }
}
```

```typescript
// apps/web/src/components/chat/chat-interface.tsx

// Updated message handling
for await (const event of parseNexusStream(response)) {
  switch (event.type) {
    case StreamEventType.CONTENT:
      responseContent += event.content;
      updateLastMessage(conversationId!, responseContent);
      break;
      
    case StreamEventType.THINKING:
      thinkingContent += event.content;
      updateLastMessage(conversationId!, `<think>${thinkingContent}</think>`);
      break;
      
    case StreamEventType.LINK:
      // Render as clickable link with metadata
      const linkHtml = `<a href="${event.content}" target="_blank">${event.metadata?.title || event.content}</a>`;
      responseContent += linkHtml;
      updateLastMessage(conversationId!, responseContent);
      break;
      
    case StreamEventType.FILE:
      // Render file download button
      const fileHtml = renderFileAttachment(event.content, event.metadata);
      responseContent += fileHtml;
      updateLastMessage(conversationId!, responseContent);
      break;
      
    case StreamEventType.TOOL_CALL:
      // Show tool invocation
      showToolCall(event.metadata?.tool, event.metadata?.args);
      break;
      
    case StreamEventType.ERROR:
      showError(event.content);
      break;
      
    case StreamEventType.DONE:
      finishMessage(conversationId!);
      break;
  }
}
```

---

## Benefits

### 1. **Protocol Agnostic**
- Support OpenAI, Anthropic, ABI, custom providers
- Each adapter handles its provider's quirks internally
- Frontend gets clean, normalized events

### 2. **Easy to Extend**
- New provider? Implement one adapter class
- No changes to chat endpoint or frontend
- Plugin system for custom providers

### 3. **Rich Content Support**
- Links, files, tool calls, thinking, metadata
- Not limited to `{"content": "text"}`
- Future-proof for multimodal (images, audio)

### 4. **Transparent Debugging**
- Each adapter logs its specific format
- Clear separation of concerns
- Easy to test adapters in isolation

### 5. **Format Detection**
- Auto-detect provider format from headers/response
- Fall back to safe defaults
- Warn on unexpected formats

---

## Migration Path

### Phase 1: Extract Adapters (Week 1)
- [ ] Create `providers/base.py` with interfaces
- [ ] Extract `stream_with_openai` → `OpenAIAdapter`
- [ ] Extract `stream_with_abi` → `ABIAdapter`
- [ ] Keep existing endpoint logic (backward compatible)

### Phase 2: Normalize Events (Week 2)
- [ ] Define `StreamEvent` structure
- [ ] Update adapters to emit `StreamEvent`
- [ ] Update frontend to handle event types
- [ ] Add link/file rendering

### Phase 3: Adapter Registry (Week 3)
- [ ] Create `AdapterRegistry`
- [ ] Refactor chat endpoint to use registry
- [ ] Remove provider-specific if/else chains
- [ ] Add adapter tests

### Phase 4: Advanced Features (Week 4)
- [ ] Add thinking/tool call events
- [ ] Implement format auto-detection
- [ ] Add adapter metrics/monitoring
- [ ] Create adapter plugin system

---

## Example: Adding New Provider

```python
# 1. Create adapter
class MyCustomAdapter(ProviderAdapter):
    async def stream(self, messages, config, system_prompt=None):
        # Custom logic here
        yield StreamEvent(type=StreamEventType.CONTENT, content="...")
    
    def detect_format(self, headers):
        return "my-custom-format"

# 2. Register it
AdapterRegistry.register("mycustom", MyCustomAdapter)

# 3. Add agent config in DB
INSERT INTO agent_configs (provider, model_id, ...) 
VALUES ('mycustom', 'my-model', ...);

# 4. Done! Frontend automatically works
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend (Next.js)                     │
│                                                               │
│  parseNexusStream() → Normalized StreamEvents                │
│  ├─ CONTENT      → Display text                             │
│  ├─ LINK         → Render link                              │
│  ├─ FILE         → Download button                          │
│  ├─ THINKING     → Collapsible section                      │
│  └─ TOOL_CALL    → Show tool use                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ SSE: data: {"type":"content",...}
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Backend (FastAPI)                         │
│                                                               │
│  /api/chat/stream                                            │
│  └─ AdapterRegistry.get_adapter(provider.type)              │
│     └─ adapter.stream() → StreamEvent objects               │
└───────────────────────────┬─────────────────────────────────┘
                            │
          ┌─────────────────┴─────────────────┐
          │                                   │
┌─────────▼──────────┐            ┌──────────▼─────────┐
│   OpenAIAdapter    │            │    ABIAdapter      │
│                    │            │                    │
│ ┌────────────────┐ │            │ ┌────────────────┐│
│ │ OpenAI Format  │ │            │ │ W3C SSE Format ││
│ │ data: {...}    │ │            │ │ event: type    ││
│ │ [DONE]         │ │            │ │ data: line1    ││
│ └────────────────┘ │            │ │ data: line2    ││
│         │          │            │ └────────────────┘│
│         ▼          │            │         │         │
│  StreamEvent       │            │         ▼         │
│  {type:"content"}  │            │  StreamEvent      │
└────────────────────┘            │  {type:"link"}    │
                                  └───────────────────┘
          ┌─────────────────┐
          │ AnthropicAdapter│
          │                 │
          │ event: delta    │
          │ data: {...}     │
          │        │        │
          │        ▼        │
          │  StreamEvent    │
          └─────────────────┘
```

---

## Testing Strategy

### Unit Tests (Per Adapter)

```python
# tests/test_abi_adapter.py

@pytest.mark.asyncio
async def test_abi_multi_line_data():
    """Test that ABI adapter handles W3C multi-line data: correctly"""
    adapter = ABIAdapter()
    
    # Mock response with multi-line data
    mock_response = """
event: ai_message
data: First part
data: https://link.com
data: Last part

data: [DONE]
"""
    
    events = []
    async for event in adapter.stream(...):
        events.append(event)
    
    assert len(events) == 2
    assert events[0].type == StreamEventType.LINK
    assert "https://link.com" in events[0].content
    assert events[1].type == StreamEventType.DONE
```

### Integration Tests

```python
# tests/test_provider_integration.py

@pytest.mark.asyncio
async def test_all_providers_produce_normalized_events():
    """Ensure all adapters produce valid StreamEvent objects"""
    for provider_type in ["openai", "anthropic", "abi"]:
        adapter = AdapterRegistry.get_adapter(provider_type)
        
        events = []
        async for event in adapter.stream(...):
            events.append(event)
            assert isinstance(event, StreamEvent)
            assert event.type in StreamEventType
```

---

## Performance Considerations

### Adapter Overhead
- Minimal: Just object creation and type mapping
- No extra HTTP requests
- Streaming remains efficient

### Memory
- Don't buffer entire response
- Process events incrementally
- Let adapters manage their own buffers

### Caching
- Cache adapter instances per provider type
- Don't recreate on every request

---

## Security

### Input Validation
- Adapters validate provider responses
- Sanitize content before emitting StreamEvents
- Prevent injection attacks via malformed streams

### Content Type Detection
- Verify `Content-Type` headers
- Reject unexpected formats
- Log suspicious behavior

---

## Monitoring & Observability

```python
# Add to each adapter
class ProviderAdapter(ABC):
    async def stream(self, ...):
        start_time = time.time()
        event_count = 0
        error_count = 0
        
        try:
            async for event in self._stream_internal(...):
                event_count += 1
                yield event
        except Exception as e:
            error_count += 1
            logger.error(f"{self.__class__.__name__} error: {e}")
            raise
        finally:
            duration = time.time() - start_time
            metrics.record_stream(
                provider=self.provider_type,
                duration=duration,
                events=event_count,
                errors=error_count,
            )
```

---

## Documentation

- [ ] Document each adapter's specific behavior
- [ ] Provide examples for adding new adapters
- [ ] Create provider compatibility matrix
- [ ] Add troubleshooting guide per provider

---

*Last Updated: 2026-02-09*  
*Status: Proposed Architecture*
