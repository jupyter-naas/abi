import pytest

from src.core.modules.supervisor.agents.SupervisorAgent import (
    create_agent as create_supervisor_agent,
)
from src import secret, config
import requests
import inspect
import json

@pytest.fixture
def supervisor_agent() -> str:
    agent = create_supervisor_agent()
    as_api = getattr(agent, "as_api", None)
    route_name = None
    if as_api is not None:
        # Get the index of 'route_name' in co_varnames tuple
        try:
            # Get route_name from function signature
            signature = inspect.signature(as_api)
            route_name = signature.parameters.get('route_name').default
        except ValueError:
            raise ValueError(f"Route name not found for agent {agent}")
    url = f"https://{config.space_name}-api.default.space.naas.ai/agents/{route_name}/stream-completion?token={secret.get('ABI_API_KEY')}"
    return url

def test_supervisor_agent(supervisor_agent: str):
    url = supervisor_agent
    payload = {
        "prompt": "Hello, how are you?",
        "thread_id": 0
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    assert response.status_code == 200, response.text