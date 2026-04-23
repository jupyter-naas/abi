# Creating an Integration

Integrations are the external API adapters in ABI. They are the smallest, most atomic units - they talk to a specific external service and nothing else. They do not depend on pipelines, workflows, or agents.

---

## Role in the stack

```bash
External API  →  Integration  →  Pipeline (transforms to RDF)
                              →  Workflow (business logic)
                              →  Agent tool (direct invocation by LLM)
```

An integration should:
- Handle authentication and HTTP communication.
- Return raw data from the external service.
- Expose itself as LangChain tools via `as_tools()`.

An integration must NOT:
- Write to the triple store directly.
- Depend on other ABI modules or services.
- Contain business logic.

---

## Integration class

```python
# integrations/MyIntegration.py
from naas_abi_core.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from typing import Any

@dataclass
class MyIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for MyIntegration.

    Attributes:
        api_key: API key for MyService.
        base_url: Base URL for the API (default: https://api.myservice.com).
    """
    api_key: str
    base_url: str = "https://api.myservice.com"

class MyIntegration(Integration):
    __configuration: MyIntegrationConfiguration

    def __init__(self, configuration: MyIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        import requests

        response = requests.request(
            method=method,
            url=f"{self.__configuration.base_url}{endpoint}",
            headers={"Authorization": f"Bearer {self.__configuration.api_key}"},
            params=params,
            json=json,
        )
        response.raise_for_status()
        return response.json()

    def list_items(self, filter: str | None = None) -> list[dict]:
        """List items from MyService.

        Args:
            filter: Optional filter expression.

        Returns:
            List of item dicts from the API.
        """
        params = {"filter": filter} if filter else None
        return self._make_request("/items", params=params)

    def get_item(self, item_id: str) -> dict:
        """Get a single item by ID."""
        return self._make_request(f"/items/{item_id}")
```

---

## Exposing as tools for agents

Every integration should implement an `as_tools()` function at module level:

```python
def as_tools(configuration: MyIntegrationConfiguration) -> list:
    """Convert MyIntegration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = MyIntegration(configuration)

    class ListItemsSchema(BaseModel):
        filter: str | None = Field(None, description="Optional filter expression")

    class GetItemSchema(BaseModel):
        item_id: str = Field(..., description="The ID of the item to retrieve")

    return [
        StructuredTool(
            name="list_myservice_items",
            description="List items from MyService. Use when the user asks to see or search items.",
            func=lambda **kwargs: integration.list_items(**kwargs),
            args_schema=ListItemsSchema,
        ),
        StructuredTool(
            name="get_myservice_item",
            description="Get a specific item from MyService by its ID.",
            func=lambda **kwargs: integration.get_item(**kwargs),
            args_schema=GetItemSchema,
        ),
    ]
```

---

## Best practices

- **One integration per external service.** A `GitHubIntegration` for GitHub, a `SalesforceIntegration` for Salesforce.
- **Document all methods.** Agents use tool descriptions to decide when to call them. Vague descriptions lead to wrong invocations.
- **Handle errors gracefully.** Raise descriptive exceptions; don't swallow HTTP errors silently.
- **Guard optional keys.** Check for API key presence before adding tools:

```python
# In your agent:
if secret.get("MY_API_KEY"):
    config = MyIntegrationConfiguration(api_key=secret.get("MY_API_KEY"))
    tools += as_tools(config)
```

- **Keep credentials in secrets.** Never hardcode API keys. Use `secret.get("KEY_NAME")` from the secret service.

---

## Testing

```python
# tests/test_my_integration.py
from unittest.mock import patch
from naas_abi.modules.custom.my_module.integrations.MyIntegration import (
    MyIntegration, MyIntegrationConfiguration,
)

def test_list_items():
    config = MyIntegrationConfiguration(api_key="test-key")
    integration = MyIntegration(config)

    with patch.object(integration, "_make_request", return_value=[{"id": "1"}]):
        result = integration.list_items()
    assert len(result) == 1
```

Next: [[building/creating-a-pipeline|Creating a Pipeline]] to ingest this data into the knowledge graph.
