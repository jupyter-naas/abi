# Creating an Integration

Integrations are the external API adapters in ABI. They are the smallest, most atomic units - they talk to a specific external service and nothing else. They do not depend on pipelines, workflows, or agents.

`abi new integration` writes the right one for the module you run it in: `naas_abi_core` code in an [in-engine module](/user-guide/build/modules/creating-a-module#remote-or-in-engine), and `naas_abi_sdk` code in a [remote module](/user-guide/build/sdk/build-a-remote-module) (see [in a remote module](#in-a-remote-module)).

---

## Scaffold one

From the project root:

```bash
abi new integration My src/my_module/integrations
```

It writes `MyIntegration.py` with a configuration dataclass and an `Integration` subclass to fill in (the name is converted to PascalCase and `Integration` is appended).

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
- Depend on other ABI modules, or on services beyond what it needs for itself (the scaffold wires the cache service to memoize upstream calls).
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

By convention, an integration file also defines an `as_tools(configuration)` function at module level (the marketplace integrations all do), which an agent calls to get the tools:

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
- **Handle errors gracefully.** Raise descriptive exceptions; don't swallow HTTP errors silently. Raise `IntegrationConnectionError` (from `naas_abi_core.integration`) for transport-level failures, so callers can tell them from logic errors.
- **Guard optional keys.** Check for the API key before adding tools:

```python
# In your agent's New():
from my_module import ABIModule

api_key = ABIModule.get_instance().configuration.my_api_key
if api_key:
    tools += as_tools(MyIntegrationConfiguration(api_key=api_key))
```

- **Keep credentials in secrets.** Never hardcode API keys. Declare a field on the module's `Configuration` (`my_api_key: str`) and set it in `config.yaml` as `my_api_key: "{{ secret.MY_API_KEY }}"`; the value comes from the secret service (`.env` by default). A module can also read a secret at run time with `self.engine.services.secret.get("MY_API_KEY")`.

---

## Testing

```python
# integrations/MyIntegration_test.py
from unittest.mock import patch
from my_module.integrations.MyIntegration import (
    MyIntegration, MyIntegrationConfiguration,
)

def test_list_items():
    config = MyIntegrationConfiguration(api_key="test-key")
    integration = MyIntegration(config)

    with patch.object(integration, "_make_request", return_value=[{"id": "1"}]):
        result = integration.list_items()
    assert len(result) == 1
```

---

## In a remote module

`abi new integration crm integrations`, run in a remote module's folder, writes `CrmIntegration.py` and a test beside it, on `naas_abi_sdk` (no `naas_abi_core` import). The class has the same shape, with async methods (use `httpx`) and `IntegrationConnectionError` for a tool that cannot be reached:

```python
# src/research/integrations/CrmIntegration.py
from dataclasses import dataclass

from naas_abi_sdk.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)


@dataclass
class CrmIntegrationConfiguration(IntegrationConfiguration):
    api_key: str = ""
    base_url: str = "https://api.example.com"


class CrmIntegration(Integration):
    def __init__(self, configuration: CrmIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    async def ping(self) -> str:
        if not self.__configuration.api_key:
            raise IntegrationConnectionError("CRM: no API key in its configuration")
        return self.__configuration.base_url
```

- **Nothing consumes it.** As in an in-engine module, an integration is a code pattern: the module's workflows, pipelines and agents build it and call it. It is not published in discovery.
- **Credentials** come from the engine's secret service, not from `config.yaml`: declare it in the module (`ModuleDependencies(services=("secret",))`) and read `await self.engine.services.secret.get("CRM_API_KEY")`, in a workflow's or pipeline's `New(module)` or in `on_initialized`, then pass the value in the configuration.
- **Test it** offline: `CrmIntegration_test.py` checks the configuration and the refusal without credentials, and a patched HTTP client covers your own calls.

---

Next: [Creating a Pipeline](/user-guide/build/knowledge-graph/creating-a-pipeline) to ingest this data into the knowledge graph.
