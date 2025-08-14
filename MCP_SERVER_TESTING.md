# MCP Server Testing Guide

## Prerequisites

1. **Environment Variables**: Create a `.env` file with:
```bash
ABI_API_KEY=your_api_key_here
```

2. **Install Dependencies**:
```bash
uv sync
```

## Testing Methods

### 1. Local Development Testing

#### Step 1: Start the API
```bash
# In terminal 1
uv run api
```
The API will be available at `http://localhost:9879`

#### Step 2: Test Agent Discovery
```bash
# In terminal 2
uv run python test_mcp_server.py
```

This will:
- ✅ Check API health
- ✅ Fetch OpenAPI specification
- ✅ List all discovered agents
- ✅ Test calling an agent (if API key is set)

#### Step 3: Run MCP Server (STDIO mode for Claude Desktop)
```bash
# In terminal 2
uv run python abi_mcp_server.py
```

#### Step 4: Run MCP Server (HTTP mode)
```bash
# In terminal 2
MCP_TRANSPORT=http uv run python abi_mcp_server.py
```

Then test the HTTP endpoint:
```bash
# In terminal 3
curl http://localhost:3000/
```

### 2. Production Testing

After deployment via GitHub Actions:

#### Test the deployed API
```bash
# Check API health
curl https://abi-api.default.space.naas.ai/health

# Get OpenAPI spec
curl https://abi-api.default.space.naas.ai/openapi.json | jq '.paths | keys[] | select(contains("/agents/"))'
```

#### Test the deployed MCP server
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
      "args": ["/path/to/abi_mcp_server.py"],
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

## Validation Checklist

- [ ] API is running and healthy
- [ ] OpenAPI spec contains agent endpoints
- [ ] MCP server discovers agents dynamically
- [ ] MCP server works in STDIO mode
- [ ] MCP server works in HTTP mode
- [ ] Agent calls work with valid API key
- [ ] Claude Desktop can connect to MCP server

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

When running `test_mcp_server.py` with a working API:

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