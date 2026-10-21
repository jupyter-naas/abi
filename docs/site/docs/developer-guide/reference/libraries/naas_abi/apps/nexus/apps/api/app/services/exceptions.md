# Service Exception Handlers

## What it is
A small FastAPI integration layer that maps internal service exceptions to HTTP responses (`JSONResponse`) with an appropriate status code and `"detail"` message.

## Public API
- `service_exception_handler(request: Request, exc: Exception) -> JSONResponse`
  - FastAPI exception handler that:
    - Converts known service exceptions to `JSONResponse({"detail": ...}, status_code=...)`.
    - Re-raises unknown exceptions (so FastAPI’s default handlers/middleware can process them).
- `register_service_exception_handlers(app: FastAPI) -> None`
  - Registers `service_exception_handler` for every exception type listed in `EXCEPTION_TO_HTTP`.

## Configuration/Dependencies
- **FastAPI**:
  - `fastapi.FastAPI`, `fastapi.Request`
  - `fastapi.responses.JSONResponse`
- **Exception mapping table**:
  - `EXCEPTION_TO_HTTP: dict[type[Exception], tuple[int, DetailResolver]]`
    - Maps exception classes to `(http_status_code, detail_resolver)`.
    - `detail_resolver` is a `Callable[[Exception], str]`.

## Usage
```python
from fastapi import FastAPI

from naas_abi.apps.nexus.apps.api.app.services.exceptions import (
    register_service_exception_handlers,
)

app = FastAPI()
register_service_exception_handlers(app)
```

## Caveats
- Only exceptions included in `EXCEPTION_TO_HTTP` are handled. Any other exception is re-raised by `service_exception_handler`.
- `_resolve_exception_mapping()` uses `isinstance()` and iterates in insertion order; if multiple mapped types match (via inheritance), the **first** match wins.
- Some mapped exceptions return a fixed `"detail"` string via `lambda`, ignoring the original exception message.
