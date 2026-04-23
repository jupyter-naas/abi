# logging (structured logging)

## What it is
- A small module that configures **structured logging** using `structlog`.
- Provides a helper to retrieve a named `structlog` bound logger.

## Public API
- `configure_logging() -> None`
  - Configures `structlog` with a standard processor chain and logger settings.
  - Uses console rendering when stderr is a TTY; otherwise outputs JSON.
- `get_logger(name: str) -> structlog.BoundLogger`
  - Returns a named `structlog` bound logger via `structlog.get_logger(name)`.

## Configuration/Dependencies
- Dependencies:
  - `structlog`
  - Python stdlib: `logging`, `sys`
- Configuration details applied by `configure_logging()`:
  - Processors:
    - `structlog.contextvars.merge_contextvars`
    - `structlog.processors.add_log_level`
    - `structlog.processors.StackInfoRenderer()`
    - `structlog.dev.set_exc_info`
    - `structlog.processors.TimeStamper(fmt="iso")`
    - Renderer:
      - `structlog.dev.ConsoleRenderer()` if `sys.stderr.isatty()`
      - else `structlog.processors.JSONRenderer()`
  - `wrapper_class`: `structlog.make_filtering_bound_logger(logging.DEBUG)`
  - `context_class`: `dict`
  - `logger_factory`: `structlog.PrintLoggerFactory()`
  - `cache_logger_on_first_use`: `True`

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.core.logging import configure_logging, get_logger

configure_logging()

log = get_logger(__name__)
log.info("service_started", port=8000)
```

## Caveats
- Call `configure_logging()` early (before emitting logs) to ensure processors/renderers are active.
- Output format changes based on whether `stderr` is a TTY (console vs JSON).
