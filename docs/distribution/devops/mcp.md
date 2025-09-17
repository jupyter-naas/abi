# MCP Integration

## Overview

The Model Context Protocol (MCP) integration enables ABI agents to be exposed as tools in external applications like Claude Desktop, VS Code, and other MCP-compatible clients. This creates a seamless bridge between ABI's agent ecosystem and popular development and productivity tools.

## Architecture

The MCP integration consists of:

- **MCP Server** (`mcp_server.py`): Lightweight server that exposes ABI agents as MCP tools
- **Dynamic Agent Discovery**: Automatically discovers available agents from the ABI API
- **Multiple Transport Support**: STDIO for local integrations, HTTP for remote deployments
- **Authentication**: Secure API key-based authentication with ABI backend

## Setup Guide

## Prerequisites

1. **Environment Variables**: Create a `.env` file with:
```bash
ABI_API_KEY=your_api_key_here
```

2. **Install Dependencies**:
```bash
uv sync
```

## Deployment Methods

### 1. Local Development Deployment

#### Step 1: Start the API
```bash
# In terminal 1
uv run api
```
The API will be available at `http://localhost:9879`

#### Step 2: Run MCP Server (STDIO mode for Claude Desktop)
```bash
# In terminal 2
uv run python mcp_server.py
```

#### Step 3: Run MCP Server (HTTP mode)
```bash
# In terminal 2
MCP_TRANSPORT=http uv run python mcp_server.py
```

Then test the HTTP endpoint:
```bash
# In terminal 3
curl http://localhost:3000/
```

### 2. Production Deployment

For production environments, the MCP server can be deployed alongside your ABI API:

#### Verify the deployed API
```bash
# Check API health
curl https://abi-api.default.space.naas.ai/health

# Get OpenAPI spec
curl https://abi-api.default.space.naas.ai/openapi.json | jq '.paths | keys[] | select(contains("/agents/"))'
```

#### Verify the deployed MCP server
```bash
# Check if MCP server is running
curl https://abi-mcp-server.default.space.naas.ai/
```

### 3. Claude Desktop Integration

Add to your Claude Desktop MCP settings (`~/Library/Application Support/Claude/claude_desktop_config.json`):

#### For local development:
```json
{
  "mcpServers": {
    "abi-local": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "ABI_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

#### For production:
```json
{
  "mcpServers": {
    "abi-production": {
      "command": "curl",
      "args": ["https://abi-mcp-server.default.space.naas.ai/"],
      "env": {
        "ABI_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

## Testing & Validation

### Automated Testing

Run the comprehensive test suite to validate your MCP integration:

```bash
uv run python mcp_server_test.py
```

This will validate:
- ✅ API connectivity and health
- ✅ OpenAPI specification access
- ✅ Agent discovery and registration
- ✅ MCP server functionality
- ✅ Agent execution (if API key provided)

### Manual Validation Checklist

- [ ] API is running and healthy
- [ ] OpenAPI spec contains agent endpoints
- [ ] MCP server discovers agents dynamically
- [ ] MCP server works in STDIO mode
- [ ] MCP server works in HTTP mode
- [ ] Agent calls work with valid API key
- [ ] Claude Desktop can connect to MCP server

## Best Practices

### Security
- **API Key Management**: Store API keys securely using environment variables or secret management systems
- **Network Security**: Use HTTPS for production deployments
- **Access Control**: Limit MCP server access to authorized clients only

### Performance
- **Connection Pooling**: The MCP server maintains efficient connections to the ABI API
- **Caching**: Agent discovery is cached to reduce API calls
- **Timeout Management**: Proper timeout handling for long-running agent operations

### Monitoring
- **Health Checks**: Monitor both API and MCP server health
- **Logging**: Enable structured logging for troubleshooting
- **Metrics**: Track agent usage and performance metrics

## Supported MCP Clients

The ABI MCP integration works with any MCP-compatible client:

- **Claude Desktop**: Native integration for AI assistance
- **VS Code**: Via MCP extensions for development workflows  
- **Custom Applications**: Any application implementing the MCP protocol

## Architecture Benefits

- **Dynamic Discovery**: Automatically exposes new agents without configuration changes
- **Lightweight**: Minimal overhead with HTTP-based agent communication
- **Scalable**: Supports multiple concurrent MCP client connections
- **Transport Flexible**: STDIO for local use, HTTP for distributed deployments

## Troubleshooting

### API not running
```bash
# Make sure to start the API first
uv run api
```

### No agents discovered
- Check that API is running
- Verify OpenAPI spec has agent endpoints
- Check network connectivity

### MCP server fails to start
- Check dependencies: `uv sync`
- Verify environment variables are set
- Check port 3000 is not in use (for HTTP mode)

### Agent calls fail
- Verify `ABI_API_KEY` is set correctly
- Check API authentication is working
- Ensure agent name exists in OpenAPI spec

## Expected Output

When running `mcp_server_test.py` with a working API:

```
🚀 MCP Server Validation Tests
==================================================
🔍 Testing API health at http://localhost:9879/health...
✅ API is healthy

🔍 Fetching OpenAPI spec from http://localhost:9879/openapi.json...
✅ OpenAPI spec fetched successfully

📋 Analyzing available agents...
✅ Found 10 agents:
  • Multi_Models: Multi Model Agent completion
  • Naas: Call the Naas agent completion
  • graph_builder_agent: Assembles entities and relationships
  • ontology_agent: Helps users to work with ontologies
  ...

🔍 Testing agent call to 'Multi_Models'...
✅ Successfully called Multi_Models agent
   Response: "Hello! I'm here to help..."

🔍 Testing MCP HTTP server at http://localhost:3000...
⚠️  MCP HTTP server not running (this is OK if testing STDIO mode)

==================================================
✅ Validation complete!
```