# mcp_server

## What it is
A lightweight HTTP-based MCP server that exposes ABI agents as MCP tools by:
- Fetching the ABI API OpenAPI spec (`/openapi.json`)
- Discovering agent completion endpoints (`/agents/{agent}/completion`)
- Dynamically registering each agent as an MCP tool on a `FastMCP("abi")` server

## Public API
- `get_api_key() -> str`
  - Reads `ABI_API_KEY` from environment; exits the process if missing.
- `fetch_openapi_spec() -> dict`
  - Async; GETs `"{ABI_API_BASE}/openapi.json"` and returns the parsed JSON (or `{}` on failure).
- `extract_agents_from_openapi(openapi_spec: dict) -> list[dict[str, str]]`
  - Parses OpenAPI `paths` to find agent completion endpoints and returns agent metadata:
    - `name`, `description` (from POST `summary`), `function_name`.
- `agent_name_to_function_name(agent_name: str) -> str`
  - Normalizes an agent name into a valid Python function name (lowercase, underscores, non-numeric prefix).
- `call_abi_agent_http(agent_name: str, prompt: str, thread_id: int = 1) -> str`
  - Async; POSTs to `"{ABI_API_BASE}/agents/{agent_name}/completion"` with bearer auth.
  - Returns response text (with surrounding quotes stripped) or a user-facing error string.
- `create_agent_function(agent_name: str, description: str)`
  - Creates an async function `(prompt: str, thread_id: int = 1) -> str` that calls the agent via HTTP.
  - Sets `__name__` based on `agent_name_to_function_name()` and populates `__doc__`.
- `wait_for_api() -> bool`
  - Async; polls `GET "{ABI_API_BASE}"` until it returns HTTP 200 (or times out after 30 attempts).
- `register_agents_dynamically()`
  - Async; fetches OpenAPI spec, extracts agents, creates/registers each tool via `mcp.tool()(agent_function)`.
  - If `ABI_API_BASE` is not localhost, waits for API readiness first.
- `setup()`
  - Async; prints startup info, validates API key, and registers tools dynamically.
- `run()`
  - Script entry point: runs `setup()` then starts MCP server with transport chosen by `MCP_TRANSPORT`.

## Configuration/Dependencies
Environment variables:
- `ABI_API_BASE` (default: `http://localhost:9879`)
  - Base URL for the ABI API server.
- `ABI_API_KEY` (required)
  - Bearer token used for ABI API calls.
- `MCP_TRANSPORT` (default: `stdio`)
  - One of:
    - `stdio` (default)
    - `sse`
    - `http` (mapped to FastMCP transport `"streamable-http"`)

Dependencies:
- `mcp.server.fastmcp.FastMCP`
- `httpx` (async HTTP client)
- `python-dotenv` (`load_dotenv()` is called at import time)

## Usage
Minimal runnable example (run as a script):

```python
# libs/naas-abi-core/naas_abi_core/apps/mcp/mcp_server.py
from naas_abi_core.apps.mcp.mcp_server import run

if __name__ == "__main__":
    run()
```

Typical environment setup:

```bash
export ABI_API_KEY="your_key_here"
export ABI_API_BASE="http://localhost:9879"   # optional
export MCP_TRANSPORT="stdio"                  # or: sse, http
python -m naas_abi_core.apps.mcp.mcp_server
```

## Caveats
- If `ABI_API_KEY` is missing, `get_api_key()` prints instructions and terminates the process via `exit(1)`.
- Agent discovery depends on the ABI API OpenAPI spec and endpoints matching `/agents/{name}/completion`.
- When `ABI_API_BASE` is not localhost, the server waits for API readiness (up to ~5 minutes) before attempting discovery; if not ready, it falls back without registering any tools.
