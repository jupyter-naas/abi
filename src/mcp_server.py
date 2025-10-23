"""
ABI MCP Server - Lightweight HTTP-based Implementation
Exposes ABI agents as MCP tools with fast startup (no heavy imports)
"""

import os
import asyncio
import httpx
import re
from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("abi")

# Constants - Default to localhost for development, can be overridden by env var
ABI_API_BASE = os.environ.get("ABI_API_BASE", "http://localhost:9879")

def get_api_key() -> str:
    """Get the API key from environment variables"""
    api_key = os.environ.get("ABI_API_KEY")
    if not api_key:
        print("❌ ABI_API_KEY not found in environment")
        print("📝 Please add it to your .env file:")
        print("   ABI_API_KEY=your_key_here")
        exit(1)
    return api_key

async def fetch_openapi_spec() -> Dict[str, Any]:
    """Fetch the OpenAPI specification to discover available agents"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ABI_API_BASE}/openapi.json")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"❌ Failed to fetch OpenAPI spec: {e}")
        return {}

def extract_agents_from_openapi(openapi_spec: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract agent information from OpenAPI specification"""
    agents = []
    paths = openapi_spec.get("paths", {})
    
    for path, methods in paths.items():
        # Look for agent completion endpoints
        if "/agents/" in path and path.endswith("/completion"):
            # Extract agent name from path like /agents/{agent_name}/completion
            agent_name = path.split("/agents/")[1].split("/completion")[0]
            
            # Get description from POST method
            post_method = methods.get("post", {})
            description = post_method.get("summary", f"{agent_name} agent completion")
            
            agents.append({
                "name": agent_name,
                "description": description,
                "function_name": agent_name_to_function_name(agent_name)
            })
    
    return agents

def agent_name_to_function_name(agent_name: str) -> str:
    """Convert agent name to valid Python function name"""
    # Replace spaces and special chars with underscores, convert to lowercase
    function_name = re.sub(r'[^a-zA-Z0-9_]', '_', agent_name.lower())
    # Remove multiple consecutive underscores
    function_name = re.sub(r'_+', '_', function_name)
    # Remove leading/trailing underscores
    function_name = function_name.strip('_')
    # Ensure it doesn't start with a number
    if function_name and function_name[0].isdigit():
        function_name = f"agent_{function_name}"
    return function_name or "unknown_agent"

async def call_abi_agent_http(agent_name: str, prompt: str, thread_id: int = 1) -> str:
    """Call ABI agents via HTTP to avoid heavy module imports"""
    try:
        headers = {
            "Authorization": f"Bearer {get_api_key()}",
            "Content-Type": "application/json",
            "User-Agent": "ABI-MCP/1.0"
        }
        
        data = {
            "prompt": prompt,
            "thread_id": thread_id
        }
        
        url = f"{ABI_API_BASE}/agents/{agent_name}/completion"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.text.strip('"')  # Remove JSON quotes
            
    except httpx.ConnectError:
        return f"❌ ABI API server not running at {ABI_API_BASE}. Please start it first with: uv run api"
    except httpx.TimeoutException:
        return f"⏱️ Timeout calling {agent_name} agent. The agent might be processing a complex request."
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "🔒 Authentication failed. Check your ABI_API_KEY environment variable."
        elif e.response.status_code == 404:
            return f"❓ Agent '{agent_name}' not found. Please check available agents via OpenAPI spec."
        else:
            return f"❌ HTTP {e.response.status_code} error calling {agent_name} agent: {e.response.text}"
    except Exception as e:
        return f"❌ Error calling {agent_name} agent: {str(e)}"

def create_agent_function(agent_name: str, description: str):
    """Create a dynamic agent function"""
    async def agent_function(prompt: str, thread_id: int = 1) -> str:
        return await call_abi_agent_http(agent_name, prompt, thread_id)
    
    # Set function metadata
    agent_function.__name__ = agent_name_to_function_name(agent_name)
    agent_function.__doc__ = f"""{description}
    
    Args:
        prompt: Your question or request for the {agent_name} agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    
    return agent_function

async def wait_for_api():
    """Wait for the API to be available before starting"""
    max_retries = 30  # Wait up to 5 minutes (30 * 10 seconds)
    retry_delay = 10  # seconds
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{ABI_API_BASE}")
                if response.status_code == 200:
                    print("✅ API is ready!")
                    return True
        except Exception:
            pass
        
        if attempt < max_retries - 1:
            print(f"⏳ Waiting for API to be ready... (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(retry_delay)
    
    print("❌ API did not become ready in time")
    return False

async def register_agents_dynamically():
    """Discover and register agents from OpenAPI specification"""
    print("🔍 Discovering agents from OpenAPI specification...")
    
    # Wait for API to be ready if not running locally
    if not ABI_API_BASE.startswith("http://localhost"):
        api_ready = await wait_for_api()
        if not api_ready:
            print("⚠️ API not ready, using fallback configuration")
            return
    
    openapi_spec = await fetch_openapi_spec()
    if not openapi_spec:
        print("⚠️ Failed to fetch OpenAPI spec, falling back to basic agents")
        return
    
    agents = extract_agents_from_openapi(openapi_spec)
    
    if not agents:
        print("⚠️ No agents found in OpenAPI spec")
        return
    
    print(f"📡 Found {len(agents)} agents:")
    
    for agent_info in agents:
        agent_name = agent_info["name"]
        description = agent_info["description"]
        function_name = agent_info["function_name"]
        
        print(f"  • {agent_name} -> {function_name}()")
        
        # Create and register the agent function
        agent_function = create_agent_function(agent_name, description)
        mcp.tool()(agent_function)
    
    print("✅ All agents registered successfully!")

async def setup():
    """Setup function to initialize the server"""
    # Quick startup - no heavy imports!
    print("🚀 Starting lightweight ABI MCP Server...")
    print(f"📡 Will connect to ABI API at: {ABI_API_BASE}")
    
    # Validate API key exists
    get_api_key()
    print("🔑 API key loaded successfully")
    
    # Dynamically discover and register agents
    await register_agents_dynamically()

def run():
    """Entry point for the script"""
    # Run setup first
    asyncio.run(setup())
    
    # Determine transport type from environment
    transport = os.environ.get('MCP_TRANSPORT', 'stdio')
    
    if transport == 'sse':
        # SSE transport for web deployment
        print("🌐 Starting MCP server with SSE (Server-Sent Events) transport on port 8000")
        mcp.run(transport='sse')
    elif transport == 'http':
        # HTTP transport using streamable-http
        print("🌐 Starting MCP server with streamable HTTP transport")
        mcp.run(transport='streamable-http')
    else:
        # STDIO transport for local Claude Desktop integration
        print("📋 Starting MCP server with STDIO transport")
        mcp.run(transport='stdio')

if __name__ == "__main__":
    run() 
