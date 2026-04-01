from __future__ import annotations

import logging

from naas_abi.apps.nexus.apps.api.app.services.model_registry import (
    get_logo_for_provider,
    get_models_for_provider,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.port import ProviderAvailabilityPort
from naas_abi.apps.nexus.apps.api.app.services.providers.providers__schema import (
    ProviderInfo,
    ProviderModelInfo,
)

logger = logging.getLogger(__name__)

_ENV_SECRET_KEYS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "XAI_API_KEY",
    "MISTRAL_API_KEY",
    "PERPLEXITY_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
]


class ProviderService:
    def __init__(self, adapter: ProviderAvailabilityPort):
        self.adapter = adapter

    @staticmethod
    def _models_for_provider(provider: str) -> list[ProviderModelInfo]:
        return [ProviderModelInfo(**model) for model in get_models_for_provider(provider)]

    async def list_available_providers(self, user_id: str) -> list[ProviderInfo]:
        providers: list[ProviderInfo] = []

        workspace_ids = await self.adapter.list_workspace_ids_for_user(user_id=user_id)
        if not workspace_ids:
            logger.warning("User %s has no workspaces", user_id)
            return providers

        secret_keys = await self.adapter.list_secret_keys_for_workspaces(
            workspace_ids=workspace_ids
        )
        env_keys = await self.adapter.list_environment_keys(key_names=_ENV_SECRET_KEYS)
        all_keys = secret_keys | env_keys

        if "OPENAI_API_KEY" in all_keys:
            providers.append(
                ProviderInfo(
                    id="openai",
                    name="OpenAI",
                    type="openai",
                    has_api_key=True,
                    logo_url=get_logo_for_provider("openai"),
                    models=self._models_for_provider("openai"),
                )
            )

        if "ANTHROPIC_API_KEY" in all_keys:
            providers.append(
                ProviderInfo(
                    id="anthropic",
                    name="Anthropic",
                    type="anthropic",
                    has_api_key=True,
                    logo_url=get_logo_for_provider("anthropic"),
                    models=self._models_for_provider("anthropic"),
                )
            )

        if "XAI_API_KEY" in all_keys:
            providers.append(
                ProviderInfo(
                    id="xai",
                    name="xAI (Grok)",
                    type="xai",
                    has_api_key=True,
                    logo_url=get_logo_for_provider("xai"),
                    models=self._models_for_provider("xai"),
                )
            )

        if "MISTRAL_API_KEY" in all_keys:
            providers.append(
                ProviderInfo(
                    id="mistral",
                    name="Mistral AI",
                    type="mistral",
                    has_api_key=True,
                    logo_url=get_logo_for_provider("mistral"),
                    models=self._models_for_provider("mistral"),
                )
            )

        if "PERPLEXITY_API_KEY" in all_keys:
            providers.append(
                ProviderInfo(
                    id="perplexity",
                    name="Perplexity",
                    type="perplexity",
                    has_api_key=True,
                    logo_url=get_logo_for_provider("perplexity"),
                    models=self._models_for_provider("perplexity"),
                )
            )

        if "GOOGLE_API_KEY" in all_keys:
            providers.append(
                ProviderInfo(
                    id="google",
                    name="Google AI",
                    type="google",
                    has_api_key=True,
                    logo_url=get_logo_for_provider("google"),
                    models=self._models_for_provider("google"),
                )
            )

        if "OPENROUTER_API_KEY" in all_keys:
            providers.append(
                ProviderInfo(
                    id="openrouter",
                    name="OpenRouter",
                    type="openrouter",
                    has_api_key=True,
                    logo_url=get_logo_for_provider("openrouter"),
                    models=self._models_for_provider("openrouter"),
                )
            )

        if "CLOUDFLARE_API_TOKEN" in all_keys and "CLOUDFLARE_ACCOUNT_ID" in all_keys:
            providers.append(
                ProviderInfo(
                    id="cloudflare",
                    name="Cloudflare Workers AI",
                    type="cloudflare",
                    has_api_key=True,
                    logo_url=get_logo_for_provider("cloudflare"),
                    models=self._models_for_provider("cloudflare"),
                )
            )

        providers.append(
            ProviderInfo(
                id="ollama",
                name="Ollama (Local)",
                type="ollama",
                has_api_key=False,
                logo_url=get_logo_for_provider("ollama"),
                models=self._models_for_provider("ollama"),
            )
        )

        return providers
