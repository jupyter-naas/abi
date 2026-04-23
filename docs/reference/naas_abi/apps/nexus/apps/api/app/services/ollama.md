# Ollama Service (`ollama.py`)

## What it is
Utilities to:
- Detect whether the `ollama` binary is installed.
- Check whether an Ollama server is running.
- Auto-start `ollama serve` if needed.
- List installed models and pull a required model (optionally in the background).
- Provide a status payload suitable for a health-check endpoint.

## Public API
- `find_ollama() -> str | None`
  - Locate the `ollama` executable (via `PATH` and common macOS/Linux paths).
- `is_ollama_running(endpoint: str = OLLAMA_ENDPOINT) -> bool` *(async)*
  - Check whether Ollama responds at `GET {endpoint}/api/tags`.
- `get_installed_models(endpoint: str = OLLAMA_ENDPOINT) -> list[str]` *(async)*
  - Return installed model names from `GET {endpoint}/api/tags` (empty list on error).
- `start_ollama(ollama_path: str) -> bool` *(async)*
  - Start `ollama serve` as a detached subprocess and wait up to `STARTUP_TIMEOUT` seconds for it to respond.
- `pull_model(model: str = DEFAULT_MODEL, endpoint: str = OLLAMA_ENDPOINT) -> bool` *(async)*
  - Pull a model using `POST {endpoint}/api/pull` with streaming status logs.
- `ensure_ollama_ready(required_model: str = DEFAULT_MODEL) -> dict` *(async)*
  - Ensure Ollama is installed, running (starting it if needed), and that the required model exists.
  - If the required model is missing, schedules a background pull and returns immediately with current status.
- `get_ollama_status(endpoint: str = OLLAMA_ENDPOINT) -> dict` *(async)*
  - Return `{installed, running, endpoint, models, default_model, has_default_model}` for health checks.

## Configuration/Dependencies
- Constants:
  - `OLLAMA_ENDPOINT = "http://localhost:11434"`
  - `DEFAULT_MODEL = "qwen3-vl:2b"`
  - `STARTUP_TIMEOUT = 30` (seconds)
- External dependency:
  - `httpx` (async HTTP client)
- System dependency:
  - Ollama executable (`ollama`) available on the host
- Uses `subprocess.Popen(..., start_new_session=True)` to detach the server process.

## Usage
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.ollama import (
    ensure_ollama_ready,
    get_ollama_status,
    DEFAULT_MODEL,
)

async def main():
    startup = await ensure_ollama_ready(required_model=DEFAULT_MODEL)
    print("startup:", startup)

    status = await get_ollama_status()
    print("status:", status)

asyncio.run(main())
```

## Caveats
- `ensure_ollama_ready()` may return before the model is available:
  - If the required model is missing, it triggers a background task (`asyncio.create_task(...)`) to pull it.
- Model availability checks use substring matching: `any(required_model in m for m in models)`.
- `start_ollama()` suppresses stdout/stderr (`DEVNULL`) and does not manage shutdown of the spawned process.
