# logging (structured logging configuration)

## What it is
- A small helper module to configure **structured logging** using `structlog`.
- Provides a centralized way to initialize processors and obtain named loggers.

## Public API
- `configure_logging() -> None`
  - Configures `structlog` with a processor chain and logger settings.
  - Uses a console renderer when `sys.stderr` is a TTY; otherwise emits JSON.
- `get_logger(name: str) -> structlog.BoundLogger`
  - Returns a named `structlog` bound logger via `structlog.get_logger(name)`.

## Configuration/Dependencies
- Dependencies:
  - `structlog`
  - Standard library: `logging`, `sys`
- Configuration details set by `configure_logging()`:
  - Processors:
    - `structlog.contextvars.merge_contextvars`
    - `structlog.processors.add_log_level`
    - `structlog.processors.StackInfoRenderer()`
    - `structlog.dev.set_exc_info`
    - `structlog.processors.TimeStamper(fmt="iso")`
    - Renderer:
      - `structlog.dev.ConsoleRenderer()` if `sys.stderr.isatty()`
      - else `structlog.processors.JSONRenderer()`
  - `wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)`
  - `context_class=dict`
  - `logger_factory=structlog.PrintLoggerFactory()`
  - `cache_logger_on_first_use=True`

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.core.logging import configure_logging, get_logger

configure_logging()

log = get_logger(__name__)
log.info("service_started", port=8000)
```

## Caveats
- The output format depends on whether `sys.stderr` is attached to a TTY (human-readable console vs JSON).
