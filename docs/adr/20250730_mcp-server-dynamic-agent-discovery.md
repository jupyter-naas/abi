# ADR: ABI MCP Server with Dynamic Agent Discovery

- Status: Accepted
- Date: 2025-07-30

## Context

ABI agents were accessible only through the CLI chat interface or the Nexus web frontend. External tools, IDEs, and automation pipelines had no standard protocol to invoke ABI agents programmatically. The Model Context Protocol (MCP) was emerging as a standard for exposing AI capabilities to external clients (editors, orchestration systems, other agents).

## Decision

Introduce an ABI MCP Server that exposes registered ABI agents as MCP tools via a dedicated FastAPI/SSE endpoint (`Dockerfile.mcp`). Key design choices:

- **Dynamic agent discovery**: the MCP server introspects the running ABI engine and registers one MCP tool per discovered agent, without hardcoding the tool list.
- **Fast startup**: the MCP server starts independently from the full ABI stack, loading only the minimal set of services needed to respond to tool calls.
- **Direct agent integration**: MCP tool calls are routed directly to the corresponding ABI agent's `run()` method, reusing all existing agent logic.
- API keys are managed via environment variables; no hardcoded credentials.

## Consequences

### Positive
- ABI agents are accessible from any MCP-compatible client (Cursor, Claude Desktop, etc.) without custom integration code.
- Dynamic discovery means new agents are automatically exposed as MCP tools without MCP server changes.
- Enables ABI to participate in multi-agent pipelines driven by external orchestrators.

### Tradeoffs
- The MCP server is a second process/image to manage alongside the main ABI stack.
- Dynamic tool discovery at startup means tool schemas are generated from agent metadata, which must be kept accurate and descriptive.
- MCP is a relatively new protocol; breaking changes in the spec may require adapter updates.
