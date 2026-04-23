# MCP Server

The ABI MCP (Model Context Protocol) server exposes every loaded ABI agent as an MCP tool. This lets Claude Desktop, Cursor, VS Code, and any MCP-compatible client invoke ABI agents directly.

---

## Starting the MCP server

```bash
# STDIO mode (for Claude Desktop)
make mcp
# or
uv run python -m naas_abi.apps.mcp.mcp

# HTTP mode (for remote / multi-client)
make mcp-http
# or
uv run python -m naas_abi.apps.mcp.mcp --transport http --port 8000
```

---

## Claude Desktop integration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "abi": {
      "command": "uv",
      "args": ["run", "python", "-m", "naas_abi.apps.mcp.mcp"],
      "cwd": "/path/to/your/abi",
      "env": {
        "OPENROUTER_API_KEY": "sk-or-...",
        "ABI_API_KEY": "your-api-key"
      }
    }
  }
}
```

Restart Claude Desktop. ABI agents will appear as available tools.

---

## How it works

At startup, the MCP server:
1. Starts the ABI Engine and loads all configured modules.
2. Discovers every registered agent.
3. Registers one MCP tool per agent, using the agent's `description` as the tool description.

Tool calls are routed directly to the corresponding agent's `run()` method. No additional configuration is needed when agents are added to or removed from the engine.

See [[adr/20250730_mcp-server-dynamic-agent-discovery|ADR: MCP Dynamic Agent Discovery]].

---

## Testing the MCP server

```bash
make mcp-test
```

This runs MCP protocol validation tests to confirm all tools are registered and respond correctly.
