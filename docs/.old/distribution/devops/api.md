# API

## Overview

The API is a RESTful API built with FastAPI that provides a way to interact with the ABI system. It automatically exposes registered agents as API endpoints and provides authentication via API keys.

## Authentication

All API endpoints are protected with Bearer token authentication. You need to include your API key in the request headers:

```bash
curl -X POST "https://your-api-url/agents/naas/completion" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your question here", "thread_id": 1}'
```

Alternatively, you can also pass the token as a query parameter:

```bash
curl -X POST "https://your-api-url/agents/naas/completion?token=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your question here", "thread_id": 1}'
```

## API Endpoints

Each agent in the system is automatically exposed through the API with two endpoints:

1. `POST /agents/{agent_name}/completion` - For synchronous completions
2. `POST /agents/{agent_name}/stream-completion` - For streaming completions

### Request Format

Both endpoints accept the same request format:

```json
{
  "prompt": "Your question or instruction for the agent",
  "thread_id": 1
}
```

- `prompt` - The input text for the agent
- `thread_id` - A numerical ID to maintain conversation context between requests

### Response Format

- The completion endpoint returns the full response as JSON
- The stream-completion endpoint returns a server-sent events (SSE) stream with partial responses

## Extending the API

### Adding New Agents

Agents are automatically registered in the API when they are added to a module. To add a new agent:

1. Create a new module directory in `src/core/` or `src/custom/modules/`
2. Add an `agents` directory within your module
3. Create a Python file inside the `agents` directory with an agent implementation
4. Implement a `create_agent()` function that returns your agent instance
5. Your agent class should extend the base `Agent` class and can override the `as_api` method to customize its API exposure:

```python
class YourAgent(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "your_agent", 
        name: str = "Your Agent", 
        description: str = "API endpoints to call Your Agent completion.", 
        description_stream: str = "API endpoints to call Your Agent stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)
```

The agent will automatically be registered with the API router with endpoints at:
- `/agents/your_agent/completion`
- `/agents/your_agent/stream-completion`

### Adding Pipelines and Workflows

Pipeline and workflow endpoints are managed via dedicated routers:

```python
# Pipelines router
pipelines_router = APIRouter(
    prefix="/pipelines", 
    tags=["Pipelines"],
    responses={401: {"description": "Unauthorized"}},
    dependencies=[Depends(is_token_valid)]
)

# Workflows router
workflows_router = APIRouter(
    prefix="/workflows", 
    tags=["Workflows"],
    responses={401: {"description": "Unauthorized"}},
    dependencies=[Depends(is_token_valid)]
)
```

Support for automatically exposing module-specific pipelines and workflows is on the roadmap.

## OpenAPI Documentation

The API provides interactive documentation through the OpenAPI standard:

- Swagger UI: `/docs`
- ReDoc UI: `/redoc`

## API Testing

To run the API locally for testing:

```bash
make api
```

This will start the API server on `http://localhost:9879`.

If you're new to the project and want to see all available make commands:

```bash
make
```

This will display the help menu with all available commands and their descriptions.