# Logger

## What it is
A tiny Loguru logger setup module that configures logging output to `sys.stderr` and applies a log level (defaulting to `WARNING`, overridable via `LOG_LEVEL`).

## Public API
- `reconfigure(level: str = "DEBUG")`
  - Resets Loguru handlers and adds a new handler that logs to `sys.stderr` at the specified level.

## Configuration/Dependencies
- **Dependency:** [`loguru`](https://github.com/Delgan/loguru) (`from loguru import logger`)
- **Environment variable:**
  - `LOG_LEVEL`: used at import time to set the initial log level; defaults to `"WARNING"` if not set.
- **Streams:** logs are sent to `sys.stderr`.

## Usage
```python
# Ensure your environment has LOG_LEVEL set before importing if you want to affect initial config:
# export LOG_LEVEL=INFO

from loguru import logger
from naas_abi_core.utils.Logger import reconfigure  # importing configures logger once

reconfigure("INFO")  # optional: change level at runtime
logger.info("Hello from Loguru")
```

## Caveats
- Importing this module **immediately reconfigures** the global Loguru logger based on `LOG_LEVEL`; this may override existing Loguru handlers set elsewhere.
