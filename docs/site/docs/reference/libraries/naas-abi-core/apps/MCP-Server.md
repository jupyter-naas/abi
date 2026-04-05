# MCP Server

The MCP server exposes ABI agents as MCP tools, discovered dynamically from API OpenAPI spec.

## How it works

1. Reads `ABI_API_BASE` (default `http://localhost:9879`).
2. Fetches `/openapi.json`.
3. Detects `/agents/*/completion` endpoints.
4. Registers one MCP tool per discovered agent.

## Required environment variables

- `ABI_API_KEY` (required)
- `ABI_API_BASE` (optional)
- `MCP_TRANSPORT` in `stdio | sse | http` (optional, default `stdio`)

## Run

```bash
uv run python -m naas_abi_core.apps.mcp.mcp_server
```bash

Transport examples:

```bash
MCP_TRANSPORT=http uv run python -m naas_abi_core.apps.mcp.mcp_server
MCP_TRANSPORT=sse uv run python -m naas_abi_core.apps.mcp.mcp_server
```
