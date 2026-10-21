# Logger

## What it is
A tiny Loguru configuration helper that resets the global `loguru.logger` sink and sets its log level (defaulting to `LOG_LEVEL` from the environment).

## Public API
- `reconfigure(level: str = "DEBUG")`
  - Removes existing Loguru handlers and adds a new sink to `sys.stderr` at the given `level`.

## Configuration/Dependencies
- **Dependency:** `loguru` (`from loguru import logger`)
- **Environment:**
  - `LOG_LEVEL`: used at import time to set the logging level (defaults to `"WARNING"` if not set).

## Usage
```python
# Importing configures Loguru immediately using LOG_LEVEL (or WARNING)
from naas_abi_core.utils.Logger import reconfigure
from loguru import logger

reconfigure("INFO")
logger.info("Hello from Loguru")
```

## Caveats
- Importing this module has side effects: it calls `reconfigure(os.environ.get("LOG_LEVEL", "WARNING"))`, which removes existing Loguru handlers and re-adds a single stderr sink.
