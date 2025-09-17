#!/usr/bin/env python3
"""
Test script to validate MCP server functionality
"""

import asyncio
import httpx
import os
import sys
from typing import Dict, Any

# Test configuration
API_BASE = os.environ.get("ABI_API_BASE", "http://localhost:9879")
API_KEY = os.environ.get("ABI_API_KEY", "")

async def test_api_health() -> bool:
    """Test if the API is healthy"""
    print(f"🔍 Testing API health at {API_BASE}...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_BASE}/openapi.json")
            if response.status_code == 200:
                print("✅ API is healthy")
                return True
            else:
                print(f"❌ API returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Failed to connect to API: {e}")
        return False

async def test_openapi_spec() -> Dict[str, Any]:
    """Test if OpenAPI spec is accessible and contains agents"""
    print(f"\n🔍 Fetching OpenAPI spec from {API_BASE}/openapi.json...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE}/openapi.json")
            response.raise_for_status()
            spec = response.json()
            print("✅ OpenAPI spec fetched successfully")
            return spec
    except Exception as e:
        print(f"❌ Failed to fetch OpenAPI spec: {e}")
        return {}

def analyze_agents(openapi_spec: Dict[str, Any]) -> list:
    """Extract and display agent information from OpenAPI spec"""
    print("\n📋 Analyzing available agents...")
    agents = []
    paths = openapi_spec.get("paths", {})
    
    for path, methods in paths.items():
        if "/agents/" in path and path.endswith("/completion"):
            agent_name = path.split("/agents/")[1].split("/completion")[0]
            post_method = methods.get("post", {})
            description = post_method.get("summary", f"{agent_name} agent")
            agents.append({
                "name": agent_name,
                "description": description,
                "endpoint": path
            })
    
    if agents:
        print(f"✅ Found {len(agents)} agents:")
        for agent in agents:
            print(f"  • {agent['name']}: {agent['description']}")
    else:
        print("❌ No agents found in OpenAPI spec")
    
    return agents

async def test_agent_call(agent_name: str) -> bool:
    """Test calling a specific agent"""
    if not API_KEY:
        print("\n⚠️  Skipping agent call test - ABI_API_KEY not set")
        return False
    
    print(f"\n🔍 Testing agent call to '{agent_name}'...")
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "prompt": "Hello, this is a test message. Please respond briefly.",
            "thread_id": 1
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE}/agents/{agent_name}/completion",
                json=data,
                headers=headers
            )
            
            if response.status_code == 200:
                print(f"✅ Successfully called {agent_name} agent")
                print(f"   Response: {response.text[:100]}...")
                return True
            else:
                print(f"❌ Agent call failed with status {response.status_code}")
                print(f"   Error: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Failed to call agent: {e}")
        return False

async def test_mcp_http_server() -> bool:
    """Test if MCP server is running in HTTP mode"""
    print("\n🔍 Testing MCP HTTP server at http://localhost:3000...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:3000/")
            if response.status_code == 200:
                print("✅ MCP HTTP server is running")
                return True
            else:
                print(f"❌ MCP server returned status {response.status_code}")
                return False
    except Exception:
        print("⚠️  MCP HTTP server not running (this is OK if testing STDIO mode)")
        return False

async def main():
    """Run all tests"""
    print("🚀 MCP Server Validation Tests")
    print("=" * 50)
    
    # Test 1: API Health
    api_healthy = await test_api_health()
    if not api_healthy:
        print("\n⚠️  API is not running. Please start it with: uv run api")
        sys.exit(1)
    
    # Test 2: OpenAPI Spec
    openapi_spec = await test_openapi_spec()
    if not openapi_spec:
        sys.exit(1)
    
    # Test 3: Analyze Agents
    agents = analyze_agents(openapi_spec)
    if not agents:
        print("\n⚠️  No agents found. Check your API configuration.")
        sys.exit(1)
    
    # Test 4: Test Agent Call (if API key is set)
    if agents:
        # Test the first available agent
        await test_agent_call(agents[0]["name"])
    
    # Test 5: MCP HTTP Server (optional)
    await test_mcp_http_server()
    
    print("\n" + "=" * 50)
    print("✅ Validation complete!")
    print("\nNext steps:")
    print("1. Start MCP server locally: python mcp_server.py")
    print("2. For HTTP mode: MCP_TRANSPORT=http python mcp_server.py")
    print("3. For Claude Desktop integration, add to MCP settings")

if __name__ == "__main__":
    asyncio.run(main())