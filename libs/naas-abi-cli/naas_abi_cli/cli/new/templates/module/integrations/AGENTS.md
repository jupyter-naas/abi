# `integrations/` — AGENTS.md

> Scope: third-party API wrappers for the `{{module_name_snake}}` module. See the module's [AGENTS.md](../AGENTS.md) for module-wide context.

## What goes here

Typed Python wrappers over external services (HTTP / GraphQL / SDK). Integrations are **pure code**: no LLM calls, no orchestration — they expose a stable API surface that agents and workflows consume.

## File shape

Files are `PascalCase`, one integration per file: `<Name>Integration.py`.

```python
from dataclasses import dataclass
from naas_abi_core.integration import Integration, IntegrationConfiguration
from naas_abi_core.integration.integration import IntegrationConnectionError

@dataclass
class <Name>IntegrationConfiguration(IntegrationConfiguration):
    """Configuration for the <Name> integration."""
    api_key: str
    base_url: str = "https://api.example.com"

class <Name>Integration(Integration):
    """<Name> integration."""

    __configuration: <Name>IntegrationConfiguration

    def __init__(self, configuration: <Name>IntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def list_things(self) -> list[dict]:
        ...  # call the upstream API; raise IntegrationConnectionError on transport failures
```

## Conventions

- **Two classes per file**: a `<Name>IntegrationConfiguration` dataclass and the `<Name>Integration` itself.
- **Return typed values** (Pydantic models or dataclasses) where possible — agents bind these as tool outputs.
- **Raise `IntegrationConnectionError`** for transport-level failures so callers can differentiate from logic errors.
- **No prompts, no LLM calls** — that belongs in `../agents/` or `../workflows/`.
- **Cache aggressively** when the upstream is rate-limited — use `CacheFactory` from core (see scaffolded template).
- **Use typed config**, not `os.environ.get(...)` — credentials are passed in via the dataclass.

## Scaffold a new integration

```bash
abi new integration <name> .
```

This drops `<Name>Integration.py` with the canonical structure (cache wiring + connection error handling skeleton).

## Tests

Colocated as `<Name>Integration_test.py`. **Mock the HTTP layer** — these are unit tests, not integration tests:

```python
import pytest
from unittest.mock import patch, MagicMock
from {{module_name_snake}}.integrations.<Name>Integration import (
    <Name>Integration, <Name>IntegrationConfiguration,
)

@patch("{{module_name_snake}}.integrations.<Name>Integration.requests.get")
def test_list_things(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: [{"id": 1}])
    integ = <Name>Integration(<Name>IntegrationConfiguration(api_key="x"))
    assert integ.list_things() == [{"id": 1}]
```

Run:

```bash
uv run pytest {{module_name_snake}}/integrations
uv run pytest {{module_name_snake}}/integrations/<Name>Integration_test.py -v
```

For true end-to-end checks against the real service, use a separate `<Name>Integration_integration_test.py` so it can be skipped when credentials aren't available.

## Wiring into the module

1. Add required credentials to the module's `Configuration(ModuleConfiguration)` in `../__init__.py`.
2. In `../agents/<Name>Agent.py`, instantiate the integration and pass its methods to the agent's `tools=[...]`.
3. If the integration manages persistent state, declare relevant services (e.g. `KeyValueService`, `CacheService`) in `ABIModule.dependencies.services`.

## See also

- Reference patterns: [`.abi/libs/naas-abi-marketplace/.../applications/`](../../../.abi/libs/naas-abi-marketplace/naas_abi_marketplace/applications)
- Cache service (for memoising upstream calls): [`.abi/libs/naas-abi-core/.../services/cache/AGENTS.md`](../../../.abi/libs/naas-abi-core/naas_abi_core/services/cache/AGENTS.md)
- Secret service (config-driven credentials): [`.abi/libs/naas-abi-core/.../services/secret/AGENTS.md`](../../../.abi/libs/naas-abi-core/naas_abi_core/services/secret/AGENTS.md)
