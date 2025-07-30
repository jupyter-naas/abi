"""
ABI MCP Server - Lightweight Fast-Loading Implementation
Exposes ABI agents as MCP tools with lazy loading for fast startup
"""

import os
import asyncio
import sys
from typing import Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("abi")

# Global variables for lazy loading
_modules_loaded = False
_modules = None
_logger = None

def get_api_key() -> str:
    """Get the API key from environment variables"""
    api_key = os.environ.get("ABI_API_KEY")
    if not api_key:
        raise ValueError(
            "ABI_API_KEY environment variable is required. "
            "Please set it before running the MCP server."
        )
    return api_key

def get_logger():
    """Get logger with lazy loading"""
    global _logger
    if _logger is None:
        try:
            from abi import logger
            _logger = logger
        except Exception:
            import logging
            _logger = logging.getLogger(__name__)
    return _logger

async def ensure_modules_loaded():
    """Lazy load ABI modules only when first needed"""
    global _modules_loaded, _modules
    
    if _modules_loaded:
        return _modules
    
    logger = get_logger()
    logger.info("🔄 Loading ABI modules on first use...")
    
    try:
        # Import ABI modules only when needed
        from src import modules
        _modules = modules
        _modules_loaded = True
        
        available_agents = [agent.name for module in modules for agent in module.agents]
        logger.info(f"✅ Loaded {len(available_agents)} agents: {available_agents}")
        
        return _modules
    except Exception as e:
        logger.error(f"❌ Failed to load ABI modules: {e}")
        _modules = []
        _modules_loaded = True
        return _modules

async def call_abi_agent_direct(agent_name: str, prompt: str, thread_id: int = 1) -> str:
    """Call ABI agents directly with lazy loading"""
    logger = get_logger()
    
    try:
        # Ensure modules are loaded
        modules = await ensure_modules_loaded()
        
        if not modules:
            return f"ABI system is not available. Please check server logs."
        
        # Find the agent in loaded modules
        for module in modules:
            for agent in module.agents:
                if agent.name.lower() == agent_name.lower() or \
                   agent.name.replace('_', '').lower() == agent_name.replace('_', '').lower():
                    logger.debug(f"🎯 Found agent: {agent.name}, calling with prompt: {prompt[:50]}...")
                    
                    # Call the agent's completion method directly
                    if hasattr(agent, 'completion'):
                        result = await agent.completion(prompt=prompt, thread_id=thread_id)
                        return str(result)
                    elif hasattr(agent, 'run'):
                        result = await agent.run(prompt=prompt, thread_id=thread_id)
                        return str(result)
                    else:
                        logger.error(f"Agent {agent.name} has no completion or run method")
                        return f"Agent {agent_name} is not properly configured"
        
        # If we get here, agent wasn't found
        available_agents = [agent.name for module in modules for agent in module.agents]
        logger.error(f"Agent {agent_name} not found. Available agents: {available_agents}")
        return f"Agent {agent_name} not found. Available agents: {', '.join(available_agents)}"
        
    except Exception as e:
        logger.error(f"❌ Error calling agent {agent_name}: {e}")
        return f"Error calling {agent_name} agent: {str(e)}"

@mcp.tool()
async def naas_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Naas agent for data analysis and business intelligence tasks.
    
    Args:
        prompt: Your question or request for the Naas agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_direct("Naas", prompt, thread_id)

@mcp.tool()
async def multi_models_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Multi Models agent to compare responses from different AI models.
    
    Args:
        prompt: Your question or request for the Multi Models agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_direct("Multi_Models", prompt, thread_id)

@mcp.tool()
async def ontology_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Ontology agent for knowledge graph and semantic queries.
    
    Args:
        prompt: Your question or request for the Ontology agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_direct("Ontology", prompt, thread_id)

@mcp.tool()
async def support_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Support agent for technical assistance and troubleshooting.
    
    Args:
        prompt: Your question or request for the Support agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_direct("Support", prompt, thread_id)

@mcp.tool()
async def supervisor_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Supervisor agent for workflow coordination and management.
    
    Args:
        prompt: Your question or request for the Supervisor agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_direct("Supervisor", prompt, thread_id)

@mcp.tool()
async def graph_builder_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Graph Builder agent for building and managing knowledge graphs.
    
    Args:
        prompt: Your question or request for the Graph Builder agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_direct("graph_builder_agent", prompt, thread_id)

@mcp.tool()
async def ontology_engineer_agent(prompt: str, thread_id: int = 1) -> str:
    """Call the Ontology Engineer agent for advanced ontology engineering tasks.
    
    Args:
        prompt: Your question or request for the Ontology Engineer agent
        thread_id: Thread ID for conversation context (default: 1)
    """
    return await call_abi_agent_direct("ontology_engineer_agent", prompt, thread_id)

if __name__ == "__main__":
    # Quick startup logging
    api_key = get_api_key()
    print(f"🚀 Starting ABI MCP Server (lightweight mode) with API key: {api_key[:10]}...", file=sys.stderr)
    print("⚡ Fast startup - modules will load on first use", file=sys.stderr)
    
    # Run the server with STDIO transport (required for Claude Desktop)
    mcp.run(transport='stdio') 