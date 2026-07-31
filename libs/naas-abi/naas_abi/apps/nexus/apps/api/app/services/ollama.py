"""
Ollama Service - Auto-start Ollama and manage models.

Handles:
- Detecting if Ollama is installed
- Starting Ollama if installed but not running
- Pulling required models on startup
- Health check endpoint for frontend

Endpoint resolution and the default model tag are **not** defined here. They
come from ``naas_abi_marketplace.ai.ollama``, which is the module a new
project enables, so the API and the engine cannot disagree about where Ollama
lives or which model a keyless project is expected to have pulled. They did
disagree: this file used to hardcode ``localhost:11434`` (unreachable from a
container, and the wrong host under WSL) and ``qwen3-vl:2b`` (a model the
project never installs).
"""

import asyncio
import functools
import logging
import subprocess

import httpx

logger = logging.getLogger(__name__)

try:
    from naas_abi_marketplace.ai.ollama.defaults import (
        DEFAULT_CHAT_MODEL_TAG,
        DEFAULT_EMBEDDING_MODEL_TAG,
        FALLBACK_CHAT_MODEL_TAGS,
    )
    from naas_abi_marketplace.ai.ollama.endpoint import (
        DEFAULT_BASE_URL,
        find_ollama_binary,
        resolve_base_url,
    )
except ImportError:  # pragma: no cover - marketplace is a hard dependency
    # Defensive only. Keeping the API importable matters more than local
    # models working, so fall back to the historical behaviour.
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_CHAT_MODEL_TAG = "qwen2.5:3b"
    DEFAULT_EMBEDDING_MODEL_TAG = "nomic-embed-text"
    FALLBACK_CHAT_MODEL_TAGS = (DEFAULT_CHAT_MODEL_TAG,)
    find_ollama_binary = lambda: None  # noqa: E731
    resolve_base_url = None  # type: ignore[assignment]

DEFAULT_MODEL = DEFAULT_CHAT_MODEL_TAG
STARTUP_TIMEOUT = 30  # seconds to wait for Ollama to start


@functools.lru_cache(maxsize=1)
def resolve_endpoint() -> str:
    """The Ollama base URL reachable from *this* process.

    Honours ``ABI_OLLAMA_BASE_URL`` and ``OLLAMA_HOST``, and falls back to the
    WSL host when running in a distro against the Ollama Windows app. Cached:
    resolution probes the network, and this is called per request.
    """
    if resolve_base_url is None:
        return DEFAULT_BASE_URL
    try:
        base_url, _reachable = resolve_base_url(None, probe=True)
        return base_url
    except Exception:  # pragma: no cover - resolution is best-effort
        logger.warning("Ollama endpoint resolution failed", exc_info=True)
        return DEFAULT_BASE_URL


# Kept as a module attribute for callers that read it directly. Resolution is
# deferred to first use so importing this module never touches the network.
def __getattr__(name: str) -> str:
    if name == "OLLAMA_ENDPOINT":
        return resolve_endpoint()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def find_ollama() -> str | None:
    """Find the Ollama binary on the system.

    Delegates to the marketplace module, which additionally knows about WSL —
    where the binary legitimately does not exist in the VM because Ollama runs
    on the Windows host.
    """
    return find_ollama_binary()


async def is_ollama_running(endpoint: str | None = None) -> bool:
    """Check if Ollama is responding."""
    endpoint = endpoint or resolve_endpoint()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{endpoint}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


async def get_installed_models(endpoint: str | None = None) -> list[str]:
    """Get list of models installed in Ollama."""
    endpoint = endpoint or resolve_endpoint()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{endpoint}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


async def start_ollama(ollama_path: str) -> bool:
    """Start the Ollama server as a background process."""
    try:
        logger.info(f"Starting Ollama from {ollama_path}...")

        # Start ollama serve as a detached subprocess
        process = subprocess.Popen(
            [ollama_path, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent process
        )

        # Wait for it to become responsive
        for _i in range(STARTUP_TIMEOUT):
            await asyncio.sleep(1)
            if await is_ollama_running():
                logger.info(f"Ollama started successfully (pid={process.pid})")
                return True
            # Check if process died
            if process.poll() is not None:
                logger.error(f"Ollama process exited with code {process.returncode}")
                return False

        logger.error(f"Ollama did not become responsive within {STARTUP_TIMEOUT}s")
        return False

    except Exception as e:
        logger.error(f"Failed to start Ollama: {e}")
        return False


async def pull_model(model: str = DEFAULT_MODEL, endpoint: str | None = None) -> bool:
    """Pull a model from the Ollama registry. Runs in background."""
    endpoint = endpoint or resolve_endpoint()
    try:
        logger.info(f"Pulling model {model}...")
        async with httpx.AsyncClient(timeout=600.0) as client:
            # Ollama pull API - streaming response
            async with client.stream(
                "POST",
                f"{endpoint}/api/pull",
                json={"name": model, "stream": True},
            ) as response:
                response.raise_for_status()
                last_status = ""
                async for line in response.aiter_lines():
                    if line:
                        import json

                        try:
                            data = json.loads(line)
                            status = data.get("status", "")
                            if status != last_status:
                                logger.info(f"  [{model}] {status}")
                                last_status = status
                        except json.JSONDecodeError:
                            continue

        logger.info(f"Model {model} pulled successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to pull model {model}: {e}")
        return False


async def ensure_ollama_ready(
    required_model: str = DEFAULT_MODEL,
) -> dict:
    """
    Ensure Ollama is running and has the required model.
    Called during API startup.

    Returns a status dict with results.
    """
    result = {
        "ollama_installed": False,
        "ollama_running": False,
        "ollama_started_by_nexus": False,
        "model_available": False,
        "model_pulled": False,
        "models": [],
        "error": None,
    }

    # 1. Check if Ollama is installed
    ollama_path = find_ollama()
    if not ollama_path:
        result["error"] = "Ollama not installed"
        logger.warning(
            "Ollama not found. Install from https://ollama.ai to enable local AI."
        )
        return result

    result["ollama_installed"] = True
    logger.info(f"Ollama found at: {ollama_path}")

    # 2. Check if already running
    if await is_ollama_running():
        result["ollama_running"] = True
        logger.info("Ollama is already running")
    else:
        # 3. Try to start it
        logger.info("Ollama is not running, attempting to start...")
        started = await start_ollama(ollama_path)
        if started:
            result["ollama_running"] = True
            result["ollama_started_by_nexus"] = True
        else:
            result["error"] = "Failed to start Ollama"
            logger.error(
                "Could not start Ollama. Try running 'ollama serve' manually."
            )
            return result

    # 4. Check installed models
    models = await get_installed_models()
    result["models"] = models
    logger.info(f"Ollama models available: {models}")

    # 5. Check if required model is available
    model_found = any(required_model in m for m in models)
    if model_found:
        result["model_available"] = True
        logger.info(f"Required model '{required_model}' is available")
    else:
        # 6. Pull the model (in background to not block startup)
        logger.info(
            f"Required model '{required_model}' not found, pulling in background..."
        )
        # Fire and forget - don't block startup
        asyncio.create_task(_pull_model_background(required_model, result))

    return result


async def _pull_model_background(model: str, result: dict) -> None:
    """Pull model in background and update result dict."""
    success = await pull_model(model)
    result["model_pulled"] = success
    result["model_available"] = success
    if success:
        result["models"] = await get_installed_models()


async def get_ollama_status(endpoint: str | None = None) -> dict:
    """Get current Ollama status for health check endpoint."""
    endpoint = endpoint or resolve_endpoint()
    installed = find_ollama() is not None
    running = await is_ollama_running(endpoint)
    models = await get_installed_models(endpoint) if running else []

    return {
        "installed": installed,
        "running": running,
        "endpoint": endpoint,
        "models": models,
        "default_model": DEFAULT_MODEL,
        "has_default_model": any(DEFAULT_MODEL in m for m in models),
    }
