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
    provider: Literal[
        "openai",
        "anthropic",
        "cloudflare",
        "ollama",
        "openrouter",
        "xai",
        "mistral",
        "perplexity",
        "google",
    ]
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
    "openrouter": [
        {
            "id": "anthropic/claude-opus-4.6",
            "name": "Claude Opus 4.6 (via OpenRouter)",
            "provider": "openrouter",
            "context_window": 1000000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 16384,
            "released": "2026-02-04",
        },
        {
            "id": "anthropic/claude-3.5-sonnet",
            "name": "Claude 3.5 Sonnet (via OpenRouter)",
            "provider": "openrouter",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2024-10-22",
        },
        {
            "id": "openai/gpt-4-turbo",
            "name": "GPT-4 Turbo (via OpenRouter)",
            "provider": "openrouter",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 4096,
            "released": "2024-04-09",
        },
        {
            "id": "meta-llama/llama-3.3-70b-instruct",
            "name": "Llama 3.3 70B (via OpenRouter)",
            "provider": "openrouter",
            "context_window": 131072,
            "supports_streaming": True,
            "supports_vision": False,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2024-12-06",
        },
        {
            "id": "google/gemini-2.0-flash-exp:free",
            "name": "Gemini 2.0 Flash Free (via OpenRouter)",
            "provider": "openrouter",
            "context_window": 1048576,
            "supports_streaming": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "max_output_tokens": 8192,
            "released": "2024-12-11",
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
