# SSE Streaming Standards - Reference Guide

## Overview
This document compares SSE (Server-Sent Events) implementations across major AI providers and the W3C standard.

**Date:** 2026-02-09  
**Purpose:** Understand best practices for streaming responses in agentic AI systems

---

## 1. W3C SSE Standard (Official Specification)

**Source:** [WHATWG HTML Living Standard](https://html.spec.whatwg.org/multipage/server-sent-events.html)

### Format

```
event: <event-type>
data: <content>
data: <more-content>
id: <event-id>

<blank line to dispatch event>
```

### Key Rules

1. **Multiple `data:` lines ARE VALID** ✅
   - Multiple `data:` lines for the same event are **concatenated with newlines**
   - Example from spec:
     ```
     data: This is the second message, it
     data: has two lines.
     ```
   - Result: `"This is the second message, it\nhas two lines."`

2. **Event boundaries**
   - Events are separated by **blank lines** (double newline)
   - A blank line triggers the dispatch of the accumulated event

3. **Field types**
   - `event:` - Sets event type (default: "message")
   - `data:` - Adds to data buffer (can appear multiple times)
   - `id:` - Sets event ID for reconnection
   - `retry:` - Sets reconnection time in milliseconds
   - `:` (comment) - Ignored (used for keepalive)

4. **Encoding**
   - Always UTF-8
   - No other encodings supported

### Example from Spec

```
: test stream (comment)

data: first event
id: 1

data: second event
id

data:  third event

```

---

## 2. OpenAI Streaming (De Facto Standard)

**Source:** [OpenAI API Reference - Chat Streaming](https://platform.openai.com/docs/api-reference/chat-streaming)

### Format

**OpenAI does NOT use standard SSE!** They use a custom JSON-per-line format:

```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":" there"},"finish_reason":null}]}

data: [DONE]
```

### Key Characteristics

1. **One `data:` line per chunk** (NOT multiple data: per event)
2. **No `event:` type** - All events are streamed as data
3. **JSON payload** - Each line is a complete JSON object
4. **`[DONE]` terminator** - Signals end of stream
5. **Incremental delta** - Each chunk contains only the new content

### Streaming Events (Newer Responses API)

OpenAI's **newer** Responses API has expanded event types:
- `.created`, `.in_progress`, `.completed`, `.failed`
- `.output_item`, `.content_part`, `.output_text.delta`
- `.refusal`, `.function_call_arguments`, `.web_search_call`

---

## 3. Anthropic Claude Streaming

**Source:** [Anthropic Streaming Messages](https://docs.anthropic.com/claude/reference/streaming)

### Format

Similar to OpenAI, Anthropic uses **JSON-per-line SSE**:

```
event: message_start
data: {"type":"message_start","message":{"id":"msg_123","type":"message","role":"assistant",...}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" there"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_stop
data: {"type":"message_stop"}
```

### Key Characteristics

1. **Uses `event:` types** ✅ (follows SSE spec)
2. **One `data:` per event** (single-line pattern)
3. **Rich event types** - Clear lifecycle events
4. **JSON payloads** - Structured data per event
5. **Explicit lifecycle** - start/delta/stop pattern

---

## 4. ABI Server (Forvis Mazars) - Current Issue

### Format (What we discovered)

```
event: ai_message
data: First part of text
data: Second part (e.g., link)
data: Third part

event: message
data: First part (DUPLICATE!)
data: Second part (DUPLICATE!)

event: done
data: [DONE]
```

### Issues Identified

1. ✅ **Multiple `data:` per event** - VALID per W3C spec, but rare in AI APIs
2. ❌ **Duplicate events** - `ai_message` and `message` contain same data
3. ⚠️ **No JSON** - Raw text instead of structured JSON
4. ⚠️ **Custom terminator** - Uses `[DONE]` like OpenAI but in different context

### Why This Is Problematic

**Standards compliance:**
- ✅ W3C SSE compliant (multiple data: lines are valid)
- ❌ Not OpenAI-compatible (they don't use multiple data: per event)
- ❌ Not Anthropic-compatible (they use one data: per event)

**Integration challenges:**
- Most SSE client libraries expect one `data:` per event
- The duplicate event pattern is non-standard
- No documentation about the multi-line behavior
- Breaking change risk if format evolves

---

## 5. Best Practices (Industry Consensus)

### For AI Agentic APIs

Based on OpenAI, Anthropic, Hugging Face, AWS Bedrock:

1. **Use clear event types**
   ```
   event: thinking
   event: response
   event: tool_call
   event: error
   ```

2. **One `data:` line per event** (easier to parse)
   ```
   event: response
   data: {"content": "chunk", "index": 0}
   
   event: response
   data: {"content": " of text", "index": 1}
   ```

3. **JSON payloads for structure**
   - Allows versioning
   - Enables rich metadata
   - Type-safe parsing

4. **Clear lifecycle events**
   - `start` - Begin processing
   - `delta` - Incremental content
   - `stop` - Complete
   - `error` - Failure

5. **Function calling / Tool use**
   - Separate event types for tool calls
   - Include tool name, arguments, results
   - Example: `event: tool_call`, `event: tool_result`

### For General SSE APIs

1. **Follow W3C spec** for maximum compatibility
2. **Use multiple `data:` only when necessary** (W3C allows, but most clients expect single)
3. **Always include blank line** to dispatch event
4. **Use `:` comments** for keepalive (every 15-30s)
5. **Include `id:` field** for resumable connections

---

## 6. Comparison Matrix

| Feature | W3C Standard | OpenAI | Anthropic | ABI Server |
|---------|--------------|--------|-----------|------------|
| **Multiple data: per event** | ✅ Allowed | ❌ Never | ❌ Never | ✅ Used |
| **event: types** | ✅ Yes | ❌ No* | ✅ Yes | ✅ Yes |
| **JSON payloads** | ⚠️ Optional | ✅ Always | ✅ Always | ❌ Raw text |
| **Terminator** | Blank line | `[DONE]` | Event-based | `[DONE]` |
| **Lifecycle events** | Generic | Delta-based | Explicit | Unclear |
| **Documentation** | Complete | Complete | Complete | ❌ Missing |

*OpenAI's newer Responses API uses event types

---

## 7. Recommendations for ABI Integration

### What ABI Should Do

1. **Choose a pattern and document it**
   - Either follow W3C multi-line pattern (document it!)
   - Or adopt OpenAI single-line pattern (easier for clients)

2. **Remove duplicate events**
   - Send EITHER `ai_message` OR `message`, not both
   - Wastes bandwidth and confuses clients

3. **Consider JSON payloads**
   - Current: `data: raw text`
   - Better: `data: {"type": "content", "text": "..."}`
   - Enables metadata, versioning, structured errors

4. **Add event types for different content**
   ```
   event: content
   data: Regular response text
   
   event: link
   data: {"url": "https://...", "title": "..."}
   
   event: file
   data: {"path": "...", "type": "pptx"}
   ```

5. **Document the spec!**
   - Publish a streaming format reference
   - Include examples for all scenarios
   - Version the API format

### What NEXUS Must Do

1. ✅ **Handle multiple `data:` per event** (DONE)
   - Don't reset `current_event` until next `event:` line
   - Concatenate all data: lines for same event

2. ✅ **Filter duplicate events** (DONE)
   - Only yield from `ai_message`, ignore `message`

3. ⚠️ **Add format detection**
   - Auto-detect if ABI changes to JSON format
   - Support both raw text and JSON responses

4. ⚠️ **Monitor for format changes**
   - Log unexpected event types
   - Alert if duplicate pattern changes
   - Version the integration

5. 📝 **Document the gaps**
   - Keep `ABI_INTEGRATION_GAPS.md` updated
   - Share findings with ABI team
   - Create test suite for edge cases

---

## 8. Code Examples

### Correct W3C SSE Parsing (Multi-line Support)

```python
async def parse_sse_stream(response):
    current_event = None
    current_data = []
    
    async for line in response.aiter_lines():
        if not line or not line.strip():
            # Blank line = dispatch event
            if current_data:
                yield {
                    "event": current_event or "message",
                    "data": "\n".join(current_data)
                }
                current_data = []
            continue
        
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            # Accumulate data lines (W3C allows multiple!)
            current_data.append(line[6:])
        elif line.startswith("id: "):
            # Handle event ID for reconnection
            event_id = line[4:].strip()
        elif line.startswith(":"):
            # Comment (keepalive), ignore
            pass
```

### OpenAI-Compatible Streaming (NEXUS Standard)

```python
async def stream_openai_compatible(response):
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            content = line[6:]
            if content == "[DONE]":
                break
            
            # OpenAI sends JSON per line
            data = json.loads(content)
            if "choices" in data:
                delta = data["choices"][0].get("delta", {})
                if "content" in delta:
                    yield delta["content"]
```

### ABI-Specific Parser (Current Implementation)

```python
async def stream_with_abi(response):
    current_event = None
    
    async for line in response.aiter_lines():
        if not line or not line.strip():
            continue
        
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            content = line[6:]
            
            if content == "[DONE]":
                break
            
            # CRITICAL: Don't reset current_event here!
            # ABI sends multiple data: lines per event
            if current_event == "ai_message" and content.strip():
                yield content
                # Keep current_event active for next data: line
```

---

## 9. Testing Checklist

For ABI integration, we must test:

- [ ] Single-line responses (short text)
- [ ] Multi-line responses (paragraphs)
- [ ] Responses with links (split across data: lines)
- [ ] Responses with code blocks
- [ ] Responses with lists/tables
- [ ] Error conditions
- [ ] Timeout/reconnection
- [ ] Concurrent requests
- [ ] All 18 agents (different response patterns?)

---

## 10. References

1. [WHATWG HTML Standard - SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html)
2. [OpenAI Streaming API](https://platform.openai.com/docs/api-reference/chat-streaming)
3. [Anthropic Streaming Messages](https://docs.anthropic.com/claude/reference/streaming)
4. [MDN Web Docs - SSE](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
5. [OpenAI Agents SDK - Streaming Guide](https://openai.github.io/openai-agents-js/guides/streaming)

---

*Last Updated: 2026-02-09*  
*Author: NEXUS Platform Team*
