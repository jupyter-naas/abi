"""
Model Registry - Centralized catalog of AI models from all providers.

This registry defines all available models, their capabilities, and how to call them.
It's simpler and more reliable than dynamic discovery.
"""

from typing import Literal, TypedDict


class ModelInfo(TypedDict):
    """Model metadata."""
    id: str
    name: str
    provider: Literal["openai", "anthropic", "cloudflare", "ollama", "openrouter", "xai", "mistral", "perplexity", "google"]
    context_window: int
    supports_streaming: bool
    supports_vision: bool
    supports_function_calling: bool
    max_output_tokens: int | None
    released: str  # Date string YYYY-MM-DD


# ============================================================================
# MODEL REGISTRY - Update this when providers release new models
# ============================================================================

MODEL_REGISTRY: dict[str, list[ModelInfo]] = {
    "openai": [
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "provider": "openai",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 16384,
            "released": "2024-05-13",
        },
        {
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "provider": "openai",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 16384,
            "released": "2024-07-18",
        },
        {
            "id": "gpt-4-turbo",
            "name": "GPT-4 Turbo",
            "provider": "openai",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2024-04-09",
        },
        {
            "id": "gpt-3.5-turbo",
            "name": "GPT-3.5 Turbo",
            "provider": "openai",
            "context_window": 16385,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2022-11-30",
        },
        {
            "id": "o1-preview",
            "name": "O1 Preview",
            "provider": "openai",
            "context_window": 128000,
            "supports_streaming": False,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 32768,
            "released": "2024-09-12",
        },
        {
            "id": "o1-mini",
            "name": "O1 Mini",
            "provider": "openai",
            "context_window": 128000,
            "supports_streaming": False,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 65536,
            "released": "2024-09-12",
        },
    ],

    "anthropic": [
        {
            "id": "claude-opus-4.6",
            "name": "Claude Opus 4.6",
            "provider": "anthropic",
            "context_window": 1000000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 16384,
            "released": "2026-02-04",
        },
        {
            "id": "claude-3-5-sonnet-20241022",
            "name": "Claude 3.5 Sonnet",
            "provider": "anthropic",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2024-10-22",
        },
        {
            "id": "claude-3-5-haiku-20241022",
            "name": "Claude 3.5 Haiku",
            "provider": "anthropic",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2024-10-22",
        },
        {
            "id": "claude-3-opus-20240229",
            "name": "Claude 3 Opus",
            "provider": "anthropic",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2024-02-29",
        },
        {
            "id": "claude-3-sonnet-20240229",
            "name": "Claude 3 Sonnet",
            "provider": "anthropic",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2024-02-29",
        },
        {
            "id": "claude-3-haiku-20240307",
            "name": "Claude 3 Haiku",
            "provider": "anthropic",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2024-03-07",
        },
    ],

    "xai": [
        {
            "id": "grok-3",
            "name": "Grok 3",
            "provider": "xai",
            "context_window": 131072,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2025-11-01",
        },
        {
            "id": "grok-2-latest",
            "name": "Grok 2",
            "provider": "xai",
            "context_window": 131072,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2024-08-13",
        },
        {
            "id": "grok-2-vision-1212",
            "name": "Grok 2 Vision",
            "provider": "xai",
            "context_window": 32768,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2024-12-12",
        },
    ],

    "mistral": [
        {
            "id": "mistral-large-latest",
            "name": "Mistral Large",
            "provider": "mistral",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2024-07-24",
        },
        {
            "id": "mistral-medium-latest",
            "name": "Mistral Medium",
            "provider": "mistral",
            "context_window": 32000,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2023-12-11",
        },
        {
            "id": "mistral-small-latest",
            "name": "Mistral Small",
            "provider": "mistral",
            "context_window": 32000,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2024-02-26",
        },
        {
            "id": "codestral-latest",
            "name": "Codestral",
            "provider": "mistral",
            "context_window": 32000,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2024-05-29",
        },
    ],

    "perplexity": [
        {
            "id": "llama-3.1-sonar-large-128k-online",
            "name": "Sonar Large 128k Online",
            "provider": "perplexity",
            "context_window": 127072,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 4096,
            "released": "2024-07-23",
        },
        {
            "id": "llama-3.1-sonar-small-128k-online",
            "name": "Sonar Small 128k Online",
            "provider": "perplexity",
            "context_window": 127072,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 4096,
            "released": "2024-07-23",
        },
        {
            "id": "llama-3.1-sonar-large-128k-chat",
            "name": "Sonar Large 128k Chat",
            "provider": "perplexity",
            "context_window": 127072,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 4096,
            "released": "2024-07-23",
        },
        {
            "id": "llama-3.1-sonar-small-128k-chat",
            "name": "Sonar Small 128k Chat",
            "provider": "perplexity",
            "context_window": 127072,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 4096,
            "released": "2024-07-23",
        },
    ],

    "google": [
        {
            "id": "gemini-2.0-flash-exp",
            "name": "Gemini 2.0 Flash (Experimental)",
            "provider": "google",
            "context_window": 1048576,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2024-12-11",
        },
        {
            "id": "gemini-exp-1206",
            "name": "Gemini Experimental 1206",
            "provider": "google",
            "context_window": 2097152,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2024-12-06",
        },
        {
            "id": "gemini-1.5-pro",
            "name": "Gemini 1.5 Pro",
            "provider": "google",
            "context_window": 2097152,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2024-02-15",
        },
        {
            "id": "gemini-1.5-flash",
            "name": "Gemini 1.5 Flash",
            "provider": "google",
            "context_window": 1048576,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2024-05-14",
        },
    ],

    # OpenRouter - Cursor-style model selection; single API for 400+ models
    # See https://openrouter.ai/models for full list
    "openrouter": [
        # Anthropic (Claude)
        {
            "id": "anthropic/claude-opus-4.6",
            "name": "Opus 4.6",
            "provider": "openrouter",
            "context_window": 1000000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 16384,
            "released": "2026-02-05",
        },
        {
            "id": "anthropic/claude-sonnet-4.6",
            "name": "Sonnet 4.6",
            "provider": "openrouter",
            "context_window": 1000000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 128000,
            "released": "2026-02-17",
        },
        {
            "id": "anthropic/claude-sonnet-4.5",
            "name": "Sonnet 4.5",
            "provider": "openrouter",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2025-09-29",
        },
        {
            "id": "anthropic/claude-haiku-4.5",
            "name": "Haiku 4.5",
            "provider": "openrouter",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2025-10-01",
        },
        # OpenAI (GPT) - Codex optimized for coding workflows
        {
            "id": "openai/gpt-5.2-codex",
            "name": "GPT-5.2 Codex",
            "provider": "openrouter",
            "context_window": 400000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 65536,
            "released": "2026-01-14",
        },
        {
            "id": "openai/gpt-5-mini",
            "name": "GPT-5 Mini",
            "provider": "openrouter",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 16384,
            "released": "2025-01-01",
        },
        {
            "id": "openai/gpt-5",
            "name": "GPT-5",
            "provider": "openrouter",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 16384,
            "released": "2025-01-01",
        },
        {
            "id": "openai/gpt-4.1-mini",
            "name": "GPT-4.1 Mini",
            "provider": "openrouter",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 16384,
            "released": "2025-01-01",
        },
        # Google (Gemini)
        {
            "id": "google/gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "provider": "openrouter",
            "context_window": 1048576,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2025-06-01",
        },
        {
            "id": "google/gemini-2.0-flash-exp",
            "name": "Gemini 2.0 Flash",
            "provider": "openrouter",
            "context_window": 1048576,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2024-12-11",
        },
        # Moonshot (Kimi)
        {
            "id": "moonshotai/kimi-k2.5",
            "name": "Kimi K2",
            "provider": "openrouter",
            "context_window": 262144,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 262144,
            "released": "2026-01-27",
        },
        # Qwen (Coder)
        {
            "id": "qwen/qwen3-coder-next",
            "name": "Qwen 2.5 Coder",
            "provider": "openrouter",
            "context_window": 262144,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 65536,
            "released": "2026-02-03",
        },
        {
            "id": "qwen/qwen3.5-plus-02-15",
            "name": "Qwen 3.5 Plus",
            "provider": "openrouter",
            "context_window": 1000000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 65536,
            "released": "2026-02-15",
        },
        # xAI (Grok)
        {
            "id": "x-ai/grok-4",
            "name": "Grok Code",
            "provider": "openrouter",
            "context_window": 131072,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2025-01-01",
        },
        # Perplexity
        {
            "id": "perplexity/sonar-pro",
            "name": "Sonar Pro",
            "provider": "openrouter",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 4096,
            "released": "2024-01-01",
        },
    ],

    "ollama": [
        {
            "id": "qwen3-vl:2b",
            "name": "Qwen3 Vision 2B",
            "provider": "ollama",
            "context_window": 32768,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": False,
            "max_output_tokens": 2048,
            "released": "2024-12-30",
        },
        {
            "id": "llama3.1:8b",
            "name": "Llama 3.1 8B",
            "provider": "ollama",
            "context_window": 131072,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 2048,
            "released": "2024-07-23",
        },
        {
            "id": "mistral:7b",
            "name": "Mistral 7B",
            "provider": "ollama",
            "context_window": 32768,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 2048,
            "released": "2023-09-27",
        },
        {
            "id": "codellama:13b",
            "name": "Code Llama 13B",
            "provider": "ollama",
            "context_window": 16384,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 2048,
            "released": "2023-08-24",
        },
    ],

    "cloudflare": [
        {
            "id": "@cf/meta/llama-3.1-8b-instruct",
            "name": "Llama 3.1 8B Instruct",
            "provider": "cloudflare",
            "context_window": 131072,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 2048,
            "released": "2024-07-23",
        },
        {
            "id": "@cf/mistral/mistral-7b-instruct-v0.1",
            "name": "Mistral 7B Instruct",
            "provider": "cloudflare",
            "context_window": 8192,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 2048,
            "released": "2023-09-27",
        },
        {
            "id": "@cf/google/gemma-7b-it",
            "name": "Gemma 7B IT",
            "provider": "cloudflare",
            "context_window": 8192,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": False,
            "max_output_tokens": 2048,
            "released": "2024-02-21",
        },
    ],
}


def get_models_for_provider(provider: str) -> list[ModelInfo]:
    """Get all registered models for a provider."""
    return MODEL_REGISTRY.get(provider, [])


def get_all_models() -> list[ModelInfo]:
    """Get all registered models across all providers."""
    all_models = []
    for models in MODEL_REGISTRY.values():
        all_models.extend(models)
    return all_models


def get_model_by_id(model_id: str) -> ModelInfo | None:
    """Find a model by its ID across all providers."""
    for models in MODEL_REGISTRY.values():
        for model in models:
            if model["id"] == model_id:
                return model
    return None


def get_all_provider_names() -> list[str]:
    """Get list of all registered provider names."""
    return list(MODEL_REGISTRY.keys())


# Default logo URLs for each provider
# Served locally from /logos endpoint (user-provided square logos)
PROVIDER_LOGOS = {
    "openai": "/logos/openai.jpg",
    "anthropic": "/logos/anthropic.jpg",
    "xai": "/logos/xai.jpg",
    "google": "/logos/google.png",
    "mistral": "/logos/mistral.png",
    "cloudflare": "/logos/cloudflare.jpg",
    "openrouter": "/logos/openrouter.jpeg",
    "perplexity": "/logos/perplexity.png",
    "ollama": "/logos/ollama.png",
}


def get_logo_for_provider(provider: str) -> str | None:
    """Get default logo URL for a provider."""
    return PROVIDER_LOGOS.get(provider)


# OpenRouter model id prefix -> upstream provider logo (e.g. anthropic/claude-... -> anthropic)
OPENROUTER_UPSTREAM_LOGOS: dict[str, str] = {
    "anthropic": "/logos/anthropic.jpg",
    "openai": "/logos/openai.jpg",
    "google": "/logos/google.png",
    "xai": "/logos/xai.jpg",
    "x-ai": "/logos/xai.jpg",
    "mistral": "/logos/mistral.png",
    "moonshotai": "/logos/openrouter.jpeg",  # no moonshot logo, use openrouter
    "qwen": "/logos/openrouter.jpeg",
    "perplexity": "/logos/perplexity.png",
    "writer": "/logos/openrouter.jpeg",
    "minimax": "/logos/openrouter.jpeg",
    "stepfun": "/logos/openrouter.jpeg",
    "upstage": "/logos/openrouter.jpeg",
    "cohere": "/logos/openrouter.jpeg",
    "meta-llama": "/logos/openrouter.jpeg",
    "deepseek": "/logos/openrouter.jpeg",
}


def get_logo_for_openrouter_model(model_id: str) -> str:
    """Resolve logo for OpenRouter model from upstream provider (anthropic/claude -> anthropic logo)."""
    if "/" in model_id:
        prefix = model_id.split("/")[0].lower()
        return OPENROUTER_UPSTREAM_LOGOS.get(prefix, "/logos/openrouter.jpeg")
    return "/logos/openrouter.jpeg"


async def fetch_openrouter_models(api_key: str) -> list[ModelInfo]:
    """Fetch models from OpenRouter API (400+ models). Falls back to static registry on error."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        import logging

        logging.warning("OpenRouter models fetch failed, using static registry: %s", e)
        return MODEL_REGISTRY.get("openrouter", [])

    models_data = data.get("data", [])
    result: list[ModelInfo] = []
    for m in models_data:
        model_id = m.get("id", "")
        name = m.get("name", model_id)
        # Clean name: "Anthropic: Claude Sonnet 4.6" -> "Claude Sonnet 4.6"
        if ": " in name:
            name = name.split(": ", 1)[1]
        top = m.get("top_provider") or {}
        context = top.get("context_length") or m.get("context_length") or 128000
        max_out = top.get("max_completion_tokens")
        arch = m.get("architecture") or {}
        mods = arch.get("input_modalities") or []
        has_vision = "image" in mods or "video" in mods
        result.append(
            {
                "id": model_id,
                "name": name,
                "provider": "openrouter",
                "context_window": context,
                "supports_streaming": True,
                "supports_vision": has_vision,
                "supports_function_calling": "tools" in str(m.get("supported_parameters", [])),
                "max_output_tokens": max_out,
                "released": "2024-01-01",
            }
        )
    return result
