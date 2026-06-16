from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderModelInfo:
    """A model surfaced from a marketplace AI provider module."""

    canonical_id: str
    model_id: str
    provider: str  # ModelProvider value (e.g. "openai", "anthropic")
    provider_id: str  # marketplace directory name (e.g. "chatgpt", "claude")
    module_path: str  # e.g. "naas_abi_marketplace.ai.chatgpt"
    configured: bool  # true when the owning module is loaded in the engine
    name: str | None = None
    description: str | None = None
    image: str | None = None
    context_window: int | None = None


@dataclass(frozen=True)
class ProviderInfo:
    """A marketplace AI provider module discovered on disk."""

    id: str  # directory name under naas_abi_marketplace/ai/
    name: str
    module_path: str
    configured: bool
    logo_url: str | None = None
    config_keys: tuple[str, ...] = field(default_factory=tuple)
    models: list[ProviderModelInfo] = field(default_factory=list)
    # Display/branding metadata mirrored from the provider ABIModule class.
    description: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    slug: str | None = None
    privacy_policy_url: str | None = None
    terms_of_service_url: str | None = None
    status_page_url: str | None = None
    headquarters: str | None = None
    datacenters: tuple[str, ...] | None = None
