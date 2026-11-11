"""Model calls Nexus makes itself, outside the engine's model registry.

Agents (in-process and remote) resolve their chat model in the model registry,
and chat file embeddings look their model up there first. A few paths call a
provider's API directly instead:

- a chat provider that is not an agent (``provider_runtime``: OpenAI, Anthropic,
  xAI, Mistral, Google, OpenRouter, Perplexity, Cloudflare Workers AI, Ollama, a
  custom OpenAI-compatible endpoint);
- speech synthesis and transcription (``api/endpoints/speech.py``,
  ``transcribe.py``: OpenAI or OpenRouter);
- the OpenAI fallback of chat file embeddings when their model is not
  registered (``services/chat/chat_file_embeddings.py``).

``direct_model_providers_enabled`` (Nexus settings, on by default) turns all of
them off. An isolated or customer-hosted deployment, whose models are served by
its own cloud through the registry, sets it to false: each of those paths then
refuses with an error instead of calling out, so no model call bypasses the
registry.
"""

from __future__ import annotations

SETTING = "direct_model_providers_enabled"


class DirectModelProviderDisabledError(RuntimeError):
    """A call to a model provider outside the model registry, refused because
    the deployment turned direct model providers off."""


def direct_model_providers_enabled() -> bool:
    """Whether Nexus may call a model provider outside the model registry.

    Read at call time: ``naas_abi`` replaces ``config.settings`` after this
    module is imported, so a module-level ``settings`` would be stale.
    """
    from naas_abi.apps.nexus.apps.api.app.core import config

    return bool(config.settings.direct_model_providers_enabled)


def refusal_message(call: str, hint: str | None = None) -> str:
    """Why ``call`` (what would reach the provider) is refused, for the caller."""
    message = (
        f"{call} calls a model provider directly, outside the model registry, and "
        f"direct model providers are turned off on this deployment ({SETTING}: false)."
    )
    return f"{message} {hint}" if hint else message


def ensure_direct_model_providers_enabled(call: str, hint: str | None = None) -> None:
    """Raise ``DirectModelProviderDisabledError`` when direct model providers are
    off, before ``call`` builds a client or opens a connection."""
    if not direct_model_providers_enabled():
        raise DirectModelProviderDisabledError(refusal_message(call, hint))
