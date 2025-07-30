"""
ABI MCP Server - Lightweight HTTP-based Implementation
Exposes ABI agents as MCP tools with fast startup (no heavy imports)
"""

import os
import asyncio
import httpx
from typing import Any
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("abi")

# Constants
ABI_API_BASE = "http://localhost:9879"

def get_api_key() -> str:
    """Get the API key from environment variables"""
    api_key = os.environ.get("ABI_API_KEY")
    if not api_key:
        print("❌ ABI_API_KEY not found in environment")
        print("📝 Please add it to your .env file:")
        print("   ABI_API_KEY=your_key_here")
        exit(1)
    return api_key

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
            return f"🔒 Authentication failed. Check your ABI_API_KEY environment variable."
        elif e.response.status_code == 404:
            return f"❓ Agent '{agent_name}' not found. Available agents: Naas, Multi_Models, Ontology, Support, Supervisor, graph_builder_agent"
        else:
            return f"❌ HTTP {e.response.status_code} error calling {agent_name} agent: {e.response.text}"
    except Exception as e:
        return f"❌ Error calling {agent_name} agent: {str(e)}"

@mcp.tool()
async def naas_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Naas agent for data analysis and business intelligence tasks.
    
    Args:
        prompt: Your question or request for the Naas agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_http("Naas", prompt, thread_id)

@mcp.tool()
async def multi_models_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Multi Models agent to compare responses from different AI models.
    
    Args:
        prompt: Your question or request for the Multi Models agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_http("Multi_Models", prompt, thread_id)

@mcp.tool()
async def ontology_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Ontology agent for knowledge graph and semantic queries.
    
    Args:
        prompt: Your question or request for the Ontology agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_http("Ontology", prompt, thread_id)

@mcp.tool()
async def support_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Support agent for technical assistance and troubleshooting.
    
    Args:
        prompt: Your question or request for the Support agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_http("Support", prompt, thread_id)

@mcp.tool()
async def supervisor_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Supervisor agent for workflow coordination and management.
    
    Args:
        prompt: Your question or request for the Supervisor agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_http("Supervisor", prompt, thread_id)

@mcp.tool()
async def graph_builder_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Graph Builder agent for building and managing knowledge graphs.
    
    Args:
        prompt: Your question or request for the Graph Builder agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_http("graph_builder_agent", prompt, thread_id)

@mcp.tool()
async def ontology_engineer_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Ontology Engineer agent for advanced ontology engineering tasks.
    
    Args:
        prompt: Your question or request for the Ontology Engineer agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_http("ontology_engineer_agent", prompt, thread_id)

if __name__ == "__main__":
    # Quick startup - no heavy imports!
    print("🚀 Starting lightweight ABI MCP Server...")
    print(f"📡 Will connect to ABI API at: {ABI_API_BASE}")
    
    # Validate API key exists
    get_api_key()
    print("🔑 API key loaded successfully")
    
    # Run the server with STDIO transport (required for Claude Desktop)
    mcp.run(transport='stdio') 