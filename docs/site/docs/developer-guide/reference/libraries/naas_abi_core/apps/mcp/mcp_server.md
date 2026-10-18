# `mcp_server` (ABI MCP Server)

## What it is
- A lightweight MCP server that:
  - Discovers available ABI “agents” by fetching an ABI API OpenAPI spec (`/openapi.json`).
  - Registers each discovered agent as an MCP tool.
  - Proxies tool calls to the ABI API over HTTP.

## Public API
- `mcp: FastMCP`
  - Global MCP server instance named `"abi"`.
  - Uses `MCP_HOST` (default `127.0.0.1`) for HTTP-based transports.

- `ABI_API_BASE: str`
  - ABI API base URL (env `ABI_API_BASE`, default `http://localhost:9879`).

- `get_api_key() -> str`
  - Reads `ABI_API_KEY` from environment.
  - If missing, prints instructions and exits the process via `sys.exit(1)`.

- `fetch_openapi_spec() -> dict[str, Any]` (async)
  - GETs `{ABI_API_BASE}/openapi.json` and returns parsed JSON.
  - On failure, prints an error and returns `{}`.

- `extract_agents_from_openapi(openapi_spec: dict[str, Any]) -> list[dict[str, str]]`
  - Scans OpenAPI `paths` for endpoints matching:
    - path contains `"/agents/"` and ends with `"/completion"`.
  - Extracts:
    - `name`: from the path segment between `/agents/` and `/completion`
    - `description`: POST method `summary` (fallback: `"{agent_name} agent completion"`)
    - `function_name`: sanitized via `agent_name_to_function_name()`

- `agent_name_to_function_name(agent_name: str) -> str`
  - Converts an agent name to a valid Python identifier:
    - lowercases
    - replaces non-alphanumeric/underscore with `_`
    - collapses repeated `_`
    - strips leading/trailing `_`
    - prefixes with `agent_` if it starts with a digit
    - returns `"unknown_agent"` if empty after normalization

- `call_abi_agent_http(agent_name: str, prompt: str, thread_id: int = 1) -> str` (async)
  - POSTs to `{ABI_API_BASE}/agents/{agent_name}/completion` with JSON:
    - `{"prompt": prompt, "thread_id": thread_id}`
  - Adds headers including `Authorization: Bearer {ABI_API_KEY}`.
  - Returns `response.text.strip('"')`.
  - On errors, returns human-readable error strings (does not raise).

- `create_agent_function(agent_name: str, description: str)`
  - Builds an async function `(prompt: str, thread_id: int = 1) -> str` that calls `call_abi_agent_http`.
  - Sets:
    - `__name__` to a sanitized function name
    - `__doc__` containing the description and argument notes

- `wait_for_api() -> bool` (async)
  - Polls `{ABI_API_BASE}` until HTTP 200 or timeout:
    - 30 retries, 10 seconds between retries
  - Returns `True` when ready, otherwise `False`.

- `register_agents_dynamically()` (async)
  - If `ABI_API_BASE` is not `http://localhost...`, waits for API readiness via `wait_for_api()`.
  - Fetches OpenAPI spec and registers each discovered agent as an MCP tool using `mcp.tool()(agent_function)`.

- `setup()` (async)
  - Prints startup info, validates API key, then registers agents dynamically.

- `run()`
  - Runs `setup()` and starts the MCP server using `MCP_TRANSPORT`:
    - `stdio` (default)
    - `sse`
    - `http` (mapped to `streamable-http`)

## Configuration/Dependencies

### Environment variables
- `ABI_API_KEY` (required)
  - Used for `Authorization: Bearer ...` when calling the ABI API.
- `ABI_API_BASE` (optional)
  - Default: `http://localhost:9879`
- `MCP_TRANSPORT` (optional)
  - `stdio` (default), `sse`, `http`
- `MCP_HOST` (optional)
  - Host binding passed to `FastMCP(..., host=...)` (default: `127.0.0.1`)

### Python dependencies
- `httpx` (async HTTP client)
- `python-dotenv` (`load_dotenv()` loads `.env` if present)
- `mcp.server.fastmcp` (`FastMCP`)

## Usage

### Run as a module (typical)
```bash
export ABI_API_KEY="your_key_here"
export ABI_API_BASE="http://localhost:9879"   # optional
export MCP_TRANSPORT="stdio"                  # or: sse, http
python -m naas_abi_core.apps.mcp.mcp_server
```

### Run from Python
```python
from naas_abi_core.apps.mcp import mcp_server

mcp_server.run()
```

## Caveats
- Missing `ABI_API_KEY` terminates the process (`sys.exit(1)`).
- Agent discovery depends on `{ABI_API_BASE}/openapi.json` and on paths matching `.../agents/<name>/completion`.
- `call_abi_agent_http()` returns error *strings* on failures (not exceptions), so failures surface as tool output.
- HTTP response handling uses `response.text.strip('"')`, assuming the body may be a quoted JSON string.
