# Expose

## What it is
- An abstract base class (ABC) defining a contract for components that can be exposed:
  - as LangChain tools (for agent use)
  - as FastAPI routes (for HTTP access)

## Public API
### Class: `Expose`
Abstract interface; implement both methods in concrete subclasses.

- `as_tools(self) -> list[BaseTool]`
  - Purpose: Return a list of LangChain tools representing the component’s functionality.
  - Notes: `BaseTool` is only imported for typing under `TYPE_CHECKING`.

- `as_api(self, router: APIRouter, route_name: str = "", name: str = "", description: str = "", description_stream: str = "", tags: list[str | Enum] | None = []) -> None`
  - Purpose: Register FastAPI routes on the provided `APIRouter` to expose the component over HTTP.
  - Parameters:
    - `router`: FastAPI `APIRouter` to register routes on
    - `route_name`, `name`, `description`, `description_stream`: optional metadata strings
    - `tags`: optional list of tags (`str` or `Enum`) for FastAPI route tagging (default is `[]` in signature)

## Configuration/Dependencies
- Depends on `fastapi.APIRouter`.
- Type hints refer to `langchain_core.tools.BaseTool` (imported only when type-checking).

## Usage
```python
from fastapi import APIRouter
from naas_abi_core.utils.Expose import Expose

class MyFeature(Expose):
    def as_tools(self):
        return []  # return a list of BaseTool instances

    def as_api(self, router: APIRouter, route_name: str = "", name: str = "",
               description: str = "", description_stream: str = "", tags=None):
        @router.get(f"/{route_name or 'my-feature'}", tags=tags or [])
        def endpoint():
            return {"ok": True}

router = APIRouter()
MyFeature().as_api(router, route_name="health")
```

## Caveats
- Both methods are abstract; instantiating `Expose` directly is not possible.
- `tags` in the abstract method signature defaults to `[]` (a mutable default). Implementations may want to use `None` and normalize to a list internally.
