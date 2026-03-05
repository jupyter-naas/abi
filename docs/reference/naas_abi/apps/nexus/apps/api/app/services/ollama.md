# `ollama` Service

## What it is
Utilities to manage a local [Ollama](https://ollama.ai) server for the Nexus API:
- Detects whether the `ollama` binary is installed.
- Checks whether the Ollama server is running.
- Starts `ollama serve` if needed.
- Lists installed models and pulls a required model (optionally in the background).
- Provides a status dict suitable for a health-check endpoint.

## Public API
- `find_ollama() -> str | None`
  - Locates the `ollama` binary (PATH plus common macOS/Linux locations).
- `is_ollama_running(endpoint: str = OLLAMA_ENDPOINT) -> bool`
  - Checks server responsiveness by calling `GET {endpoint}/api/tags`.
- `get_installed_models(endpoint: str = OLLAMA_ENDPOINT) -> list[str]`
  - Returns installed model names from `GET {endpoint}/api/tags` (returns `[]` on errors).
- `start_ollama(ollama_path: str) -> bool`
  - Starts `ollama serve` as a detached subprocess and waits up to `STARTUP_TIMEOUT` seconds for it to respond.
- `pull_model(model: str = DEFAULT_MODEL, endpoint: str = OLLAMA_ENDPOINT) -> bool`
  - Pulls a model via `POST {endpoint}/api/pull` (streaming logs); timeout up to 600 seconds.
- `ensure_ollama_ready(required_model: str = DEFAULT_MODEL) -> dict`
  - Startup orchestration:
    - verifies install
    - ensures server running (starts if needed)
    - checks models
    - if required model missing, triggers background pull
  - Returns a status dict with keys:
    - `ollama_installed`, `ollama_running`, `ollama_started_by_nexus`
    - `model_available`, `model_pulled`, `models`, `error`
- `get_ollama_status(endpoint: str = OLLAMA_ENDPOINT) -> dict`
  - Returns health/status info:
    - `installed`, `running`, `endpoint`, `models`
    - `default_model`, `has_default_model`

> Internal helper:
- `_pull_model_background(model: str, result: dict) -> None` (not intended for external use)

## Configuration/Dependencies
- Constants:
  - `OLLAMA_ENDPOINT = "http://localhost:11434"`
  - `DEFAULT_MODEL = "qwen3-vl:2b"`
  - `STARTUP_TIMEOUT = 30`
- Dependencies:
  - `httpx` for async HTTP calls
  - `subprocess` to run `ollama serve`
  - `asyncio` for polling and background tasks
  - `platform`, `shutil`, `pathlib.Path` for binary discovery

## Usage
Minimal async example:

```python
import asyncio

from naas_abi.apps.nexus.apps.api.app.services.ollama import (
    ensure_ollama_ready,
    get_ollama_status,
)

async def main():
    startup = await ensure_ollama_ready()  # may start server; may pull model in background
    print("startup:", startup)

    status = await get_ollama_status()
    print("status:", status)

asyncio.run(main())
```

## Caveats
- `ensure_ollama_ready()` may initiate model pulling asynchronously; the returned dict can show `model_available=False` initially even though a background pull is in progress.
- `start_ollama()` suppresses stdout/stderr (`DEVNULL`), so diagnostics require logs or manual invocation.
- Model presence checks use substring matching (`any(required_model in m for m in models)`), not exact equality.
