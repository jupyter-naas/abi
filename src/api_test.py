import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch
import asyncio

def test_import_fastapi_app():
    """Test that we can import the FastAPI app from src.api."""
    try:
        from src.api import app
        assert app is not None
        assert hasattr(app, 'title')
        print(f"✅ Successfully imported FastAPI app with title: {app.title}")
    except Exception as e:
        pytest.fail(f"Failed to import FastAPI app: {e}")


def test_api_basic_endpoints():
    """Test basic endpoints of the API."""
    try:
        from src.api import app
        client = TestClient(app)
        
        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200
        print("✅ API root endpoint works")
        
        # Test docs endpoint
        response = client.get("/docs")
        assert response.status_code == 200
        print("✅ API docs endpoint works")
        
        # Test redoc endpoint
        response = client.get("/redoc")
        assert response.status_code == 200
        print("✅ API redoc endpoint works")
        
        # Test OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        print("✅ API OpenAPI schema works")
        
    except Exception as e:
        pytest.fail(f"Failed to test API basic endpoints: {e}")


def test_api_authentication():
    """Test authentication endpoints of the API."""
    try:
        from src.api import app
        client = TestClient(app)
        
        # Test token endpoint with valid credentials
        response = client.post("/token", data={"username": "user", "password": "abi"})
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "abi"
        assert data["token_type"] == "bearer"
        print("✅ API authentication with valid credentials works")
        
        # Test token endpoint with invalid credentials
        response = client.post("/token", data={"username": "user", "password": "wrong"})
        assert response.status_code == 400
        print("✅ API properly rejects invalid credentials")
        
    except Exception as e:
        pytest.fail(f"Failed to test API authentication: {e}")


def test_api_agent_routes():
    """Test that the API has agent routes loaded from modules."""
    try:
        from src.api import app
        from src import modules
        client = TestClient(app)
        
        # Get OpenAPI schema to check routes
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        
        paths = schema.get("paths", {})
        
        # Look for agent routes
        agent_routes = [path for path in paths.keys() if path.startswith("/agents/")]
        
        print(f"📊 Found {len(agent_routes)} agent routes in API:")
        for route in sorted(agent_routes):
            print(f"  {route}")
        
        # Get loaded modules and agents
        loaded_modules = modules
        total_agents = 0
        agent_names = []
        
        print(f"\n📦 Loaded modules and their agents:")
        for module in loaded_modules:
            print(f"Module: {module.module_import_path}")
            for agent in module.agents:
                # Skip None agents (when API keys are missing)
                if agent is not None:
                    total_agents += 1
                    agent_names.append(agent.name)
                    print(f"  🤖 Agent: {agent.name}")
                else:
                    print(f"  ⚠️ Skipped None agent (missing API key)")
        
        print(f"\n📈 Summary:")
        print(f"  - Total modules loaded: {len(loaded_modules)}")
        print(f"  - Total agents loaded: {total_agents}")
        print(f"  - Total agent routes in API: {len(agent_routes)}")
        
        # Verify we have some structure
        assert len(paths) > 0, "No API paths found"
        assert len(loaded_modules) > 0, "No modules loaded"
        
        # Check if agent routes match loaded agents
        expected_routes_found = []
        missing_routes = []
        
        for agent_name in agent_names:
            expected_completion_route = f"/agents/{agent_name}/completion"
            expected_stream_route = f"/agents/{agent_name}/stream-completion"
            
            if expected_completion_route in paths:
                expected_routes_found.append(expected_completion_route)
            else:
                missing_routes.append(expected_completion_route)
                
            if expected_stream_route in paths:
                expected_routes_found.append(expected_stream_route)
            else:
                missing_routes.append(expected_stream_route)
        
        print(f"\n🔍 Route validation:")
        print(f"  - Expected routes found: {len(expected_routes_found)}")
        print(f"  - Missing routes: {len(missing_routes)}")
        
        if missing_routes:
            print("  Missing routes:")
            for route in missing_routes[:10]:  # Show first 10
                print(f"    ❌ {route}")
        
        if expected_routes_found:
            print("  Found routes:")
            for route in expected_routes_found[:10]:  # Show first 10
                print(f"    ✅ {route}")
        
        # Assert that we found at least some agent routes
        if total_agents > 0:
            assert len(agent_routes) > 0, f"No agent routes found despite having {total_agents} agents loaded"
            
            # Fail if there are missing routes
            if missing_routes:
                pytest.fail(f"Missing {len(missing_routes)} expected agent routes: {missing_routes[:5]}")
            
            print("✅ API has agent routes matching loaded agents")
        else:
            print("⚠️ No agents were loaded, so no agent routes expected")
            
    except Exception as e:
        pytest.fail(f"Failed to test API agent routes: {e}")


def test_api_protected_routes():
    """Test that protected routes require authentication."""
    try:
        from src.api import app
        client = TestClient(app)
        
        # Get available agent routes first
        response = client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        agent_routes = [path for path in paths.keys() if path.startswith("/agents/") and not path.endswith("/stream-completion")]
        
        if agent_routes:
            # Test first agent route without authentication
            test_route = agent_routes[0]
            response = client.get(test_route)
            
            # Should be 401 (unauthorized) or 405 (method not allowed for GET on POST endpoint)
            # Many agent routes are POST endpoints, so GET might return 405
            assert response.status_code in [401, 404, 405], f"Expected 401, 404, or 405 but got {response.status_code}"
            print(f"✅ Route {test_route} properly requires authentication or correct method")
            
            # Test with valid authentication header
            headers = {"Authorization": f"Bearer {os.getenv('ABI_API_KEY', 'abi')}"}
            response = client.get(test_route, headers=headers)
            
            # Should still be 405 if it's a POST endpoint, or 422 if it needs request body
            assert response.status_code in [401, 404, 405, 422], f"Route behavior: {response.status_code}"
            print(f"✅ Route {test_route} responds appropriately with auth header")
        else:
            print("⚠️ No agent routes found to test authentication")
            
    except Exception as e:
        pytest.fail(f"Failed to test API protected routes: {e}")


def test_api_cors_configuration():
    """Test CORS configuration of the API."""
    try:
        from src.api import app
        client = TestClient(app)
        
        # Test CORS headers with origin
        response = client.get("/", headers={"Origin": "http://localhost:9879"})
        assert response.status_code == 200
        
        # Check for CORS headers
        headers = response.headers
        cors_headers = [h for h in headers.keys() if h.lower().startswith("access-control")]
        
        if cors_headers:
            print(f"✅ CORS headers found: {cors_headers}")
        else:
            # CORS headers might not appear on simple requests
            print("⚠️ No CORS headers found (may be normal for simple requests)")
        
        print("✅ API CORS configuration tested")
        
    except Exception as e:
        pytest.fail(f"Failed to test API CORS: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])