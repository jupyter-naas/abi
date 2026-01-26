# OpenAI-Compatible API

ABI now provides OpenAI-compatible API endpoints that allow you to use standard OpenAI clients and tools with ABI agents.

## Features

- **OpenAI-Compatible Endpoints**: `/v1/chat/completions`, `/v1/models`
- **Streaming Support**: Real-time streaming responses using Server-Sent Events (SSE)
- **Bearer Token Authentication**: Uses existing ABI authentication
- **Agent as Models**: Each ABI agent is exposed as a model
- **Standard Request/Response Format**: Fully compatible with OpenAI's API specification

## Endpoints

### List Models

List all available ABI agents as OpenAI models.

```bash
curl http://localhost:9879/v1/models \
  -H "Authorization: Bearer $ABI_API_KEY"
```

Response:
```json
{
  "object": "list",
  "data": [
    {
      "id": "support_agent",
      "object": "model",
      "created": 1706745600,
      "owned_by": "abi"
    }
  ]
}
```

### Get Model Details

Retrieve information about a specific model/agent.

```bash
curl http://localhost:9879/v1/models/support_agent \
  -H "Authorization: Bearer $ABI_API_KEY"
```

### Chat Completions (Non-Streaming)

Send a chat completion request to an ABI agent.

```bash
curl http://localhost:9879/v1/chat/completions \
  -H "Authorization: Bearer $ABI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "support_agent",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant"},
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "temperature": 0.7
  }'
```

Response:
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1706745600,
  "model": "support_agent",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm doing well, thank you for asking..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 50,
    "total_tokens": 70
  }
}
```

### Chat Completions (Streaming)

Stream responses in real-time using Server-Sent Events.

```bash
curl http://localhost:9879/v1/chat/completions \
  -H "Authorization: Bearer $ABI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "support_agent",
    "messages": [
      {"role": "user", "content": "Tell me a story"}
    ],
    "stream": true
  }'
```

## Using with Python OpenAI Client

```python
from openai import OpenAI

# Initialize client with ABI endpoint
client = OpenAI(
    api_key="your-abi-api-key",
    base_url="http://localhost:9879/v1"
)

# List available models (agents)
models = client.models.list()
print("Available models:", [m.id for m in models.data])

# Non-streaming completion
response = client.chat.completions.create(
    model="support_agent",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello!"}
    ]
)
print(response.choices[0].message.content)

# Streaming completion
stream = client.chat.completions.create(
    model="support_agent",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## Using with LangChain

```python
from langchain_openai import ChatOpenAI

# Initialize LangChain with ABI
llm = ChatOpenAI(
    model="support_agent",
    openai_api_key="your-abi-api-key",
    openai_api_base="http://localhost:9879/v1"
)

# Use like any other LangChain model
response = llm.invoke("Hello, how are you?")
print(response.content)
```

## Using with OpenWebUI

[OpenWebUI](https://github.com/open-webui/open-webui) is a user-friendly web interface for chatting with LLMs. You can now use it with ABI!

### Setup Steps

1. **Start ABI API** (if not already running):
   ```bash
   make api
   ```

2. **Install OpenWebUI** (using Docker):
   ```bash
   docker run -d -p 3000:8080 \
     -v open-webui:/app/backend/data \
     --name open-webui \
     ghcr.io/open-webui/open-webui:main
   ```

3. **Configure OpenWebUI to use ABI**:
   - Open http://localhost:3000 in your browser
   - Go to Settings → Connections
   - Add a new OpenAI connection:
     - **API Base URL**: `http://host.docker.internal:9879/v1`
       - (Use `http://localhost:9879/v1` if not using Docker)
     - **API Key**: Your `ABI_API_KEY` value
   - Click "Save"

4. **Select an ABI Agent**:
   - In the chat interface, click the model dropdown
   - You should see all your ABI agents listed
   - Select the agent you want to chat with

5. **Start Chatting**:
   - Type your message and press Enter
   - The ABI agent will respond through OpenWebUI's interface

### Troubleshooting OpenWebUI Connection

If OpenWebUI can't connect to ABI:

- **Docker networking**: Use `host.docker.internal` instead of `localhost` when ABI is running on your host machine
- **CORS**: ABI already has CORS enabled for common origins
- **Authentication**: Ensure your `ABI_API_KEY` is set correctly in OpenWebUI
- **Check logs**: Look at both ABI logs and OpenWebUI logs for error messages

## Supported Parameters

The following OpenAI parameters are supported:

- ✅ `model` - Agent name to use
- ✅ `messages` - Chat message history
- ✅ `stream` - Enable/disable streaming
- ⚠️ `temperature` - Accepted but depends on underlying agent model
- ⚠️ `top_p` - Accepted but depends on underlying agent model
- ⚠️ `max_tokens` - Accepted but depends on underlying agent model
- ⚠️ `presence_penalty` - Accepted but depends on underlying agent model
- ⚠️ `frequency_penalty` - Accepted but depends on underlying agent model
- ❌ `logit_bias` - Not supported
- ✅ `user` - Used as thread ID for conversation persistence

Note: Parameters marked with ⚠️ are passed to the request but their effect depends on the underlying chat model used by the agent.

## Authentication

The OpenAI-compatible API uses the same Bearer token authentication as the standard ABI API:

```bash
export ABI_API_KEY="your-api-key"
```

Include this in the `Authorization` header:
```
Authorization: Bearer your-api-key
```

## Differences from OpenAI API

While we strive for compatibility, there are some differences:

1. **Models are Agents**: Each "model" is actually an ABI agent with tools and capabilities
2. **Token Counting**: Token usage is estimated, not exact
3. **Function Calling**: Currently not exposed through the OpenAI API (agents handle tools internally)
4. **Embeddings**: Not yet supported (coming soon)
5. **Fine-tuning**: Not applicable to ABI agents

## Benefits

Using the OpenAI-compatible API gives you:

- **Tool Integration**: Use any tool that works with OpenAI's API
- **Easy Migration**: Swap OpenAI for ABI with minimal code changes
- **Standard Interface**: Well-documented API format
- **Community Ecosystem**: Access to OpenAI-compatible tools and libraries
- **UI Clients**: Use visual clients like OpenWebUI, Chatbot UI, etc.

## Next Steps

- Explore available agents: `curl http://localhost:9879/v1/models`
- Try the Python examples above
- Set up OpenWebUI for a better UI experience
- Integrate with your existing OpenAI-based applications

## API Reference

For detailed API specifications, see the [OpenAI API documentation](https://platform.openai.com/docs/api-reference/chat).

Our implementation follows the same request/response formats for maximum compatibility.
