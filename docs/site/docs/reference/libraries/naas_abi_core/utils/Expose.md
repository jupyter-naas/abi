# Expose

## What it is
- An abstract base class (ABC) defining a standard interface for exposing a component:
  - as LangChain tools (for agent use), and/or
  - as FastAPI routes (for HTTP access).

## Public API
- `class Expose(ABC)`
  - `as_tools(self) -> list[BaseTool]`
    - Must be implemented by subclasses.
    - Should return a list of LangChain `BaseTool` instances usable by an Agent.
  - `as_api(self, router: APIRouter, route_name: str = "", name: str = "", description: str = "", description_stream: str = "", tags: list[str | Enum] | None = []) -> None`
    - Must be implemented by subclasses.
    - Should register FastAPI routes on the provided `APIRouter`.

## Configuration/Dependencies
- Depends on:
  - `fastapi.APIRouter`
- Type-checking only dependency:
  - `langchain_core.tools.BaseTool` (imported only under `TYPE_CHECKING`)

## Usage
```python
from fastapi import APIRouter
from naas_abi_core.utils.Expose import Expose

class MyExpose(Expose):
    def as_tools(self):
        return []  # return a list of langchain tools

    def as_api(self, router: APIRouter, route_name: str = "", **kwargs) -> None:
        @router.get(f"/{route_name or 'my-endpoint'}")
        def ping():
            return {"ok": True}

router = APIRouter()
MyExpose().as_api(router, route_name="ping")
tools = MyExpose().as_tools()
```

## Caveats
- `tags` default is an empty list literal (`[]`), which is a mutable default argument.
- `as_api` contains two consecutive `raise NotImplementedError()` statements; both are unreachable in practice but indicate the method must be overridden.
