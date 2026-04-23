# `mcp_server` (ABI MCP Server)

## What it is
A lightweight MCP server that discovers ABI “agents” from an ABI API OpenAPI spec and exposes them as MCP tools. It proxies tool calls to the ABI API over HTTP and supports multiple MCP transports.

## Public API
- `mcp: FastMCP`
  - Global MCP server instance named `"abi"`.
- `ABI_API_BASE: str`
  - Base URL for the ABI API (defaults to `http://localhost:9879`).
- `get_api_key() -> str`
  - Reads `ABI_API_KEY` from environment; exits the process if missing.
- `fetch_openapi_spec() -> dict[str, Any]`
  - Fetches `{ABI_API_BASE}/openapi.json` and returns the parsed JSON (or `{}` on failure).
- `extract_agents_from_openapi(openapi_spec: dict[str, Any]) -> list[dict[str, str]]`
  - Scans OpenAPI `paths` for `"/agents/{name}/completion"` endpoints and returns agent metadata:
    - `name`, `description` (from POST `summary`), `function_name` (sanitized).
- `agent_name_to_function_name(agent_name: str) -> str`
  - Converts an agent name into a valid Python function name (lowercase, underscores, no leading digit).
- `call_abi_agent_http(agent_name: str, prompt: str, thread_id: int = 1) -> str` (async)
  - POSTs to `{ABI_API_BASE}/agents/{agent_name}/completion` with JSON `{prompt, thread_id}` and Bearer auth.
  - Returns response text (with surrounding quotes stripped) or an error message string on failure.
- `create_agent_function(agent_name: str, description: str)`
  - Creates an async tool function `agent_function(prompt, thread_id=1)` that calls `call_abi_agent_http`.
  - Sets `__name__` using `agent_name_to_function_name` and a docstring based on `description`.
- `wait_for_api() -> bool` (async)
  - Polls `{ABI_API_BASE}` until it returns HTTP 200 (up to 30 retries, 10s delay).
- `register_agents_dynamically()` (async)
  - Optionally waits for API readiness (when `ABI_API_BASE` is not localhost).
  - Fetches OpenAPI spec, extracts agents, registers each as an MCP tool via `mcp.tool()(agent_function)`.
- `setup()` (async)
  - Prints startup info, validates API key, and registers agents dynamically.
- `run()`
  - Runs `setup()` and starts the MCP server with transport controlled by `MCP_TRANSPORT`:
    - `"stdio"` (default), `"sse"`, or `"http"` (streamable HTTP).

## Configuration/Dependencies
### Environment variables
- `ABI_API_KEY` (required)
  - Used as `Authorization: Bearer ...` when calling the ABI API.
- `ABI_API_BASE` (optional)
  - Default: `http://localhost:9879`
- `MCP_TRANSPORT` (optional)
  - `stdio` (default), `sse`, or `http`

### Python dependencies
- `httpx` (async HTTP client)
- `python-dotenv` (`load_dotenv()` loads `.env` if present)
- `mcp.server.fastmcp` (`FastMCP`)

## Usage
### Run as a script
```python
# mcp_server.py is intended to be executed directly
from naas_abi_core.apps.mcp import mcp_server

if __name__ == "__main__":
    mcp_server.run()
```

### Minimal environment
```bash
export ABI_API_KEY="your_key_here"
export ABI_API_BASE="http://localhost:9879"   # optional
export MCP_TRANSPORT="stdio"                  # or: sse, http
python -m naas_abi_core.apps.mcp.mcp_server
```

## Caveats
- If `ABI_API_KEY` is missing, `get_api_key()` prints instructions and terminates the process via `exit(1)`.
- Agent discovery depends on `{ABI_API_BASE}/openapi.json` and on paths matching `.../agents/<agent>/completion`.
- `call_abi_agent_http()` returns human-readable error *strings* on failures (it does not raise), which will surface as tool outputs.
- Response handling strips surrounding quotes from `response.text`; this assumes the API may return a JSON-quoted string in the body.
