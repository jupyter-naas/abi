# MCP Server

The ABI MCP (Model Context Protocol) server exposes the engine's agents as MCP tools, so Claude Desktop, Cursor, VS Code and any MCP client can call them.

It is a small process (`naas_abi_core.apps.mcp.mcp_server`, in `naas-abi-core`) that talks to a running ABI API over HTTP. It does not load the engine.

---

## How it works

At startup, the MCP server:

1. Reads `ABI_API_KEY` (required) and `ABI_API_BASE` (default `http://localhost:9879`).
2. Fetches the API's OpenAPI document (`<ABI_API_BASE>/openapi.json`) and registers one MCP tool per `POST /agents/<name>/completion` route, with the route's summary as the tool's description.
3. Calls `POST /agents/<name>/completion` with `{"prompt": ..., "thread_id": ...}` and the API key when a tool runs.

The API publishes a completion route for each agent of the modules **the engine loads**. Agents published by [remote modules](/developer-guide/architecture/remote-modules) have no such route, so they are not MCP tools; reach them through Nexus or the chat API (`POST /api/chat/stream`, with the agent's id). Restart the MCP server after adding or removing engine agents.

---

## Running it

| Variable | Default | Meaning |
|---|---|---|
| `ABI_API_KEY` | none (required) | The API key the server sends as a bearer token. |
| `ABI_API_BASE` | `http://localhost:9879` | The ABI API. |
| `MCP_TRANSPORT` | `stdio` | `stdio`, `sse` (port 8000), or `http` (streamable HTTP, port 8000). |
| `MCP_HOST` | `127.0.0.1` | The address the HTTP transports listen on. |

**Docker Compose.** The project's stack (`abi deploy local`) runs it as the `mcp-server` service, on port 8000, with `MCP_TRANSPORT=http`, `MCP_HOST=0.0.0.0` and `ABI_API_BASE=http://abi:9879`. MCP clients connect to `http://localhost:8000/mcp`.

**Natively,** from a project or the ABI repository:

```bash
# STDIO, for a desktop client that starts the server itself
uv run python -m naas_abi_core.apps.mcp.mcp_server

# HTTP, for remote or several clients
MCP_TRANSPORT=http uv run python -m naas_abi_core.apps.mcp.mcp_server
```

In the ABI repository, `make mcp` (STDIO) and `make mcp-http` (SSE) do the same.

---

## Claude Desktop integration

Add to the Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "abi": {
      "command": "uv",
      "args": ["run", "python", "-m", "naas_abi_core.apps.mcp.mcp_server"],
      "cwd": "/path/to/your/project",
      "env": {
        "ABI_API_BASE": "http://localhost:9879",
        "ABI_API_KEY": "your-api-key"
      }
    }
  }
}
```

Start the API first (`abi dev up`, or the Docker stack), then restart Claude Desktop: the engine's agents appear as tools. The API key is `ABI_API_KEY` in the project's `.env`.

See [ADR: MCP Dynamic Agent Discovery](/user-guide/release-notes/mcp-server-dynamic-agent-discovery).
