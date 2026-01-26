# OpenAI-Compatible API Implementation

This implementation adds OpenAI-compatible endpoints to ABI, allowing standard OpenAI clients to work with ABI agents.

## Architecture

### Files Added

1. **`openai_api.py`** - Main OpenAI-compatible API router
   - Request/response models matching OpenAI spec
   - `/v1/models` - List available agents as models
   - `/v1/models/{model_id}` - Get specific agent details
   - `/v1/chat/completions` - Chat completion endpoint (streaming + non-streaming)

2. **`openai_api_test.py`** - Unit tests for OpenAI API
   - Tests for all endpoints
   - Mock-based testing for isolated unit tests
   - Validation of OpenAI request/response formats

3. **Integration with `api.py`**
   - OpenAI router is included alongside existing ABI routes
   - Uses same authentication mechanism (`is_token_valid`)
   - Shares the same Engine instance for agent access

## Implementation Details

### Request/Response Models

We've implemented the following Pydantic models to match OpenAI's API:

- `OpenAIMessage` - Individual chat message
- `OpenAIChatCompletionRequest` - Request for chat completions
- `OpenAIChatCompletionResponse` - Non-streaming response
- `OpenAIChatCompletionChunk` - Streaming response chunk
- `OpenAIModel` - Model information
- `OpenAIModelList` - List of models
- `OpenAIUsage` - Token usage statistics

### Agent-to-Model Mapping

Each ABI agent is exposed as an OpenAI "model":
- Agent name becomes the model ID
- Agent description is available via the models endpoint
- All loaded agents from all modules are available

### Message Conversion

OpenAI uses a list of messages with roles (system, user, assistant). We convert this to ABI's prompt format:
- Extract the last user message as the main prompt
- System messages are preserved for context
- Thread ID can be provided via the `user` field for conversation persistence

### Streaming Implementation

Streaming responses follow OpenAI's Server-Sent Events (SSE) format:
- Initial chunk includes role: "assistant"
- Subsequent chunks include content deltas
- Final chunk includes `finish_reason: "stop"`
- Ends with `data: [DONE]`

## Testing

### Unit Tests

Run the unit tests:
```bash
make test-api
# or
pytest libs/naas-abi-core/naas_abi_core/apps/api/openai_api_test.py -v
```

Tests cover:
- Listing models
- Retrieving specific models
- Non-streaming chat completions
- Invalid model handling
- Request validation

### Manual Testing with curl

See `examples/test_openai_api.sh` for comprehensive curl tests:
```bash
./examples/test_openai_api.sh
```

### Testing with OpenAI Python Client

See `examples/openai_api_example.py` for Python examples:
```bash
export ABI_API_KEY="your-key"
python examples/openai_api_example.py
```

### Testing with OpenWebUI

1. Start ABI API:
   ```bash
   make api
   ```

2. Run OpenWebUI (Docker):
   ```bash
   docker run -d -p 3000:8080 \
     -v open-webui:/app/backend/data \
     --name open-webui \
     ghcr.io/open-webui/open-webui:main
   ```

3. Configure OpenWebUI:
   - Go to Settings → Connections
   - Add OpenAI connection with:
     - API URL: `http://host.docker.internal:9879/v1`
     - API Key: Your `ABI_API_KEY`

4. Select an ABI agent from the model dropdown and start chatting!

## Compatibility

### Supported OpenAI Features

✅ **Fully Supported:**
- `/v1/models` - List models
- `/v1/models/{model_id}` - Get model details
- `/v1/chat/completions` - Chat completions
- Streaming with SSE
- Bearer token authentication
- Basic message history

⚠️ **Partially Supported:**
- `temperature`, `top_p`, `max_tokens` - Accepted but effect depends on underlying agent model
- `user` field - Used as thread ID for conversation persistence

❌ **Not Supported (Yet):**
- `/v1/completions` - Legacy text completion endpoint
- `/v1/embeddings` - Embeddings endpoint (planned)
- Function calling via API - Agents handle tools internally
- Fine-tuning endpoints
- `logit_bias` - Not applicable to ABI

### Known Differences from OpenAI

1. **Models are Agents**: Each model is actually an ABI agent with its own tools and capabilities
2. **Token Counting**: Token usage is estimated based on word count, not exact
3. **Internal Tool Handling**: Tools are used by agents internally, not exposed through function calling API
4. **Message Flattening**: Multi-turn conversations are converted to a single prompt with context

## Integration Examples

### With LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="support_agent",
    openai_api_key=os.environ["ABI_API_KEY"],
    openai_api_base="http://localhost:9879/v1"
)

response = llm.invoke("Hello!")
```

### With Official OpenAI Client

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["ABI_API_KEY"],
    base_url="http://localhost:9879/v1"
)

response = client.chat.completions.create(
    model="support_agent",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### With JavaScript/TypeScript

```typescript
import OpenAI from 'openai';

const client = new OpenAI({
    apiKey: process.env.ABI_API_KEY,
    baseURL: 'http://localhost:9879/v1'
});

const response = await client.chat.completions.create({
    model: 'support_agent',
    messages: [{ role: 'user', content: 'Hello!' }]
});
```

## Error Handling

The API returns standard HTTP status codes:

- `200` - Success
- `401` - Unauthorized (invalid or missing API key)
- `404` - Model/Agent not found
- `422` - Validation error (invalid request format)
- `500` - Internal server error

Error responses follow OpenAI's format:
```json
{
    "error": {
        "message": "Error description",
        "type": "invalid_request_error",
        "code": "model_not_found"
    }
}
```

## Performance Considerations

### Streaming vs Non-Streaming

- **Streaming**: Better user experience for long responses, lower memory usage
- **Non-Streaming**: Simpler to implement in clients, complete response at once

### Thread Management

- Each request with a unique `user` field gets its own conversation thread
- Threads are persisted using ABI's existing memory backend (PostgreSQL or in-memory)
- Thread IDs are UUIDs generated per request if not provided

### Agent Duplication

For each request, the agent is duplicated to ensure thread safety:
- Original agent remains unchanged
- Request-specific agent gets a unique thread ID
- No state pollution between concurrent requests

## Future Enhancements

Potential improvements for future iterations:

1. **Embeddings Endpoint** (`/v1/embeddings`)
   - Expose ABI's embedding capabilities
   - Support for multiple embedding models

2. **Function Calling API**
   - Expose agent tools as OpenAI functions
   - Allow clients to handle tool calls

3. **Model Metadata**
   - More detailed model info (capabilities, context window, etc.)
   - Agent-specific parameters and defaults

4. **Advanced Streaming**
   - Stream tool usage events
   - Progress indicators for long-running operations

5. **Rate Limiting**
   - Per-model/agent rate limits
   - Per-user quota management

6. **Caching**
   - Response caching for identical requests
   - Model list caching

7. **Metrics & Monitoring**
   - Request latency tracking
   - Token usage analytics
   - Error rate monitoring

## Troubleshooting

### OpenWebUI Can't Connect

**Problem**: OpenWebUI shows "Connection failed" error

**Solutions**:
- If using Docker: Use `http://host.docker.internal:9879/v1` instead of `localhost`
- Check ABI API is running: `curl http://localhost:9879/v1/models`
- Verify API key is correct
- Check CORS settings in ABI configuration

### Streaming Doesn't Work

**Problem**: Streaming responses don't appear in client

**Solutions**:
- Ensure `stream: true` is in the request
- Check client supports SSE (Server-Sent Events)
- Verify no proxy is buffering the response
- Use curl to test directly: `curl -N http://localhost:9879/v1/chat/completions ...`

### Model Not Found

**Problem**: Error "Model 'xyz' not found"

**Solutions**:
- List available models: `curl http://localhost:9879/v1/models`
- Ensure agent module is loaded in ABI configuration
- Check agent API key requirements (some agents need external API keys)
- Verify agent name spelling matches exactly

### Authentication Errors

**Problem**: 401 Unauthorized errors

**Solutions**:
- Set `ABI_API_KEY` environment variable
- Include header: `Authorization: Bearer $ABI_API_KEY`
- Check API key matches the one in ABI configuration
- Verify no trailing spaces in API key

## References

- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [OpenWebUI Documentation](https://docs.openwebui.com/)
- [Server-Sent Events Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## Contributing

When extending the OpenAI API implementation:

1. Follow OpenAI's API specification closely
2. Add tests for new endpoints
3. Update documentation
4. Maintain backward compatibility
5. Consider performance implications
6. Test with real OpenAI clients (openai-python, LangChain, etc.)

## Support

For issues or questions:
- Check the troubleshooting section above
- Review the examples in `/examples`
- Open an issue on GitHub
- Consult the main ABI documentation
