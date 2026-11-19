# `mcp_server` (ABI MCP Server)

## What it is
- A lightweight MCP server that exposes the agents a person may use as MCP tools.
- It holds no credential of its own. Every call goes to Nexus's OpenAI-compatible gateway (`{ABI_API_BASE}/api/v1/models`, `{ABI_API_BASE}/api/v1/chat/completions`, where the agent is the model) with the caller's own personal API key (`abi_pk_...`, made in Nexus under Account, API keys). Nexus decides which agents that person may use, in which workspace.
- Transports:
  - `stdio` (default): a desktop client starts the process; the key is `NEXUS_ACCESS_TOKEN` in its environment. At start it registers one tool per agent the key's owner may use.
  - `sse` and `http` (streamable HTTP): every request carries `Authorization: Bearer <key>`. A request without one, or with one Nexus refuses, gets 401. Host and Origin are checked whatever the bind address.

## Public API
- `mcp: FastMCP`
  - The server, named `"abi"`, built from the environment at import: `MCP_HOST`, `MCP_PORT`, a token verifier (`NexusKeyVerifier`) and the Host/Origin checks (`transport_security()`).
- `transport_security() -> TransportSecuritySettings`
  - Host and Origin checks on, with `MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS` (comma-separated; `host:*` for any port). Defaults: loopback (`127.0.0.1:*`, `localhost:*`, `[::1]:*` and their `http://` origins).
- `NexusKeyVerifier`
  - `verify_token(token)`: valid when Nexus lists the agents of the key's owner (`GET /api/v1/models` answers 200). Accepted keys are remembered for a minute, by their SHA-256.
- `caller_token(ctx) -> str | None`
  - The bearer of the HTTP request that carried the call; with no request (stdio), `NEXUS_ACCESS_TOKEN`.
- `list_agent_ids(token) -> list[str]` (async)
  - The agent ids `GET /api/v1/models` returns for the key.
- `call_abi_agent_http(agent_name, prompt, token) -> str` (async)
  - `POST /api/v1/chat/completions` with `{"model": agent_name, "messages": [{"role": "user", "content": prompt}]}` and the caller's key; returns the answer's text. Errors come back as short strings (no exception). Without a key it refuses.
- `agent_name_to_function_name(agent_name) -> str`
  - A valid Python identifier for a tool name.
- `create_agent_function(agent_name, description)`
  - An async tool `(prompt, ctx) -> str` that asks one agent as the caller.
- Tools registered on every transport:
  - `list_agents()`: the agents the caller may use.
  - `ask_agent(agent, prompt)`: ask one of them.
- `register_agents_dynamically()` (async)
  - stdio: registers `create_agent_function(...)` for each agent `NEXUS_ACCESS_TOKEN` may use.
- `run()`
  - Starts the server with `MCP_TRANSPORT` (`stdio`, `sse`, `http`); stdio refuses to start without `NEXUS_ACCESS_TOKEN`.

## Configuration/Dependencies

### Environment variables
- `ABI_API_BASE`: the ABI API that serves Nexus. Default `http://localhost:9879`.
- `NEXUS_ACCESS_TOKEN`: stdio only, the person's own key.
- `MCP_TRANSPORT`: `stdio` (default), `sse`, `http`.
- `MCP_HOST` (default `127.0.0.1`), `MCP_PORT` (default `8000`): where the HTTP transports listen.
- `MCP_ALLOWED_HOSTS`, `MCP_ALLOWED_ORIGINS`: the Host and Origin values the HTTP transports answer.
- `MCP_AUTH_ISSUER_URL`, `MCP_PUBLIC_URL`: published in the server's protected-resource metadata. An HTTP transport listening beyond loopback (`MCP_HOST` other than `127.0.0.1`, `localhost`, `::1`) refuses to start without `MCP_PUBLIC_URL` (`http_transport_problem`).

### Compose
- The `mcp-server` service of the repository's `docker-compose.yml` and of the `abi deploy local` and `abi deploy dokploy` templates is behind the `mcp` profile: `docker compose --profile mcp up -d mcp-server`.

### Dependencies
- `httpx`, `python-dotenv`, `mcp` (`mcp.server.fastmcp.FastMCP`, its auth and transport-security settings).

## Usage

```bash
# stdio, for a desktop client: your own key
NEXUS_ACCESS_TOKEN=abi_pk_... python -m naas_abi_core.apps.mcp.mcp_server

# streamable HTTP on 127.0.0.1:8000; clients send Authorization: Bearer abi_pk_...
MCP_TRANSPORT=http python -m naas_abi_core.apps.mcp.mcp_server
```

## Caveats
- An agent answers as the caller: the gateway runs it with the caller's module scopes, in a workspace whose chat the caller holds. There is no thread memory across calls.
- Behind a reverse proxy, set `MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS` to the public address, or every request is refused.
