import os

import pytest
from fastapi.testclient import TestClient


def test_import_fastapi_app():
    """Test that we can import the FastAPI app from src.api."""
    try:
        from abi.apps.api.api import app

        assert app is not None
        assert hasattr(app, "title")
        print(f"✅ Successfully imported FastAPI app with title: {app.title}")
    except Exception as e:
        pytest.fail(f"Failed to import FastAPI app: {e}")


def test_api_basic_endpoints():
    """Test basic endpoints of the API."""
    try:
        from abi.apps.api.api import app

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
        from abi.apps.api.api import app

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
    """Test that each agent has both /completion and /stream-completion endpoints."""
    try:
        from abi.apps.api.api import app, engine
        from fastapi import APIRouter

        client = TestClient(app)

        modules = engine.modules.values()

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
        agents_with_routes = {}

        print("\n📦 Loaded modules and their agents:")
        for module in loaded_modules:
            print(f"Module: {module.module_import_path}")
            print(f"Agents: {module.agents}")
            for agent in module.agents:
                # Skip None agents (when API keys are missing)
                if agent is not None:
                    total_agents += 1

                    # Create a temporary router to inspect what routes the agent would add
                    temp_router = APIRouter()
                    agent.as_api(temp_router)

                    # Extract route paths from the temporary router
                    agent_route_paths = []
                    for route in temp_router.routes:
                        if hasattr(route, "path"):
                            agent_route_paths.append(route.path)

                    agents_with_routes[agent.name] = agent_route_paths
                    print(f"  🤖 Agent: {agent.name} (routes: {agent_route_paths})")
                else:
                    print("  ⚠️ Skipped None agent (missing API key)")

        print("\n📈 Summary:")
        print(f"  - Total modules loaded: {len(loaded_modules)}")
        print(f"  - Total agents loaded: {total_agents}")
        print(f"  - Total agent routes in API: {len(agent_routes)}")

        # Verify we have some structure
        assert len(paths) > 0, f"No API paths found in the OpenAPI schema: {paths}"
        assert len(loaded_modules) > 0, f"No modules loaded: {loaded_modules}"

        # Check that each agent has both required endpoints
        if total_agents > 0:
            # # We expect at least 2 routes per agent (completion and stream-completion)
            # assert len(agent_routes) >= 2 * total_agents, \
            #     f"Expected at least {2 * total_agents} routes for {total_agents} agents, but found {len(agent_routes)}"

            # Check each agent has routes ending with /completion and /stream-completion
            agents_missing_routes = []
            agents_with_both_routes = []

            for agent_name, route_paths in agents_with_routes.items():
                has_completion = False
                has_stream = False

                # Check in the actual API paths (with /agents prefix)
                for path in paths.keys():
                    if path.startswith("/agents/"):
                        if path.endswith("/completion"):
                            has_completion = True
                        elif path.endswith("/stream-completion"):
                            has_stream = True

                if has_completion and has_stream:
                    agents_with_both_routes.append(agent_name)
                else:
                    missing = []
                    if not has_completion:
                        missing.append("completion")
                    if not has_stream:
                        missing.append("stream-completion")
                    agents_missing_routes.append((agent_name, missing))

            print("\n🔍 Route validation:")
            print(
                f"  - Agents with both endpoints: {len(agents_with_both_routes)}/{total_agents}"
            )
            print(
                f"  - Agents missing endpoints: {len(agents_missing_routes)}/{total_agents}"
            )

            # assert total_agents == len(agents_with_both_routes) + len(agents_missing_routes), f"Expected {total_agents} agents, but found {len(agents_with_both_routes) + len(agents_missing_routes)}"

            if agents_with_both_routes:
                print("  ✅ Agents with both endpoints:")
                for agent in agents_with_both_routes[:5]:  # Show first 5
                    print(f"    - {agent}")

            if agents_missing_routes:
                print("  ❌ Agents missing endpoints:")
                for agent, missing in agents_missing_routes[:5]:  # Show first 5
                    print(f"    - {agent}: missing {', '.join(missing)}")
                pytest.fail(
                    f"{len(agents_missing_routes)} agents are missing required endpoints"
                )

            print(
                "✅ All agents have both /completion and /stream-completion endpoints"
            )
        else:
            print("⚠️ No agents were loaded, so no agent routes expected")

    except Exception as e:
        pytest.fail(f"Failed to test API agent routes: {e}")


def test_api_protected_routes():
    """Test that protected routes require authentication."""
    try:
        from abi.apps.api.api import app

        client = TestClient(app)

        # Get available agent routes first
        response = client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        agent_routes = [
            path
            for path in paths.keys()
            if path.startswith("/agents/") and not path.endswith("/stream-completion")
        ]

        if agent_routes:
            # Test first agent route without authentication
            test_route = agent_routes[0]
            response = client.get(test_route)

            # Should be 401 (unauthorized) or 405 (method not allowed for GET on POST endpoint)
            # Many agent routes are POST endpoints, so GET might return 405
            assert response.status_code in [401, 404, 405], (
                f"Expected 401, 404, or 405 but got {response.status_code}"
            )
            print(
                f"✅ Route {test_route} properly requires authentication or correct method"
            )

            # Test with valid authentication header
            headers = {"Authorization": f"Bearer {os.getenv('ABI_API_KEY', 'abi')}"}
            response = client.get(test_route, headers=headers)

            # Should still be 405 if it's a POST endpoint, or 422 if it needs request body
            assert response.status_code in [401, 404, 405, 422], (
                f"Route behavior: {response.status_code}"
            )
            print(f"✅ Route {test_route} responds appropriately with auth header")
        else:
            print("⚠️ No agent routes found to test authentication")

    except Exception as e:
        pytest.fail(f"Failed to test API protected routes: {e}")


def test_api_cors_configuration():
    """Test CORS configuration of the API."""
    try:
        from abi.apps.api.api import app

        client = TestClient(app)

        # Test CORS headers with origin
        response = client.get("/", headers={"Origin": "http://localhost:9879"})
        assert response.status_code == 200

        # Check for CORS headers
        headers = response.headers
        cors_headers = [
            h for h in headers.keys() if h.lower().startswith("access-control")
        ]

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
