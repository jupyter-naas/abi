"""
AI Providers API endpoints - Discover and manage available AI providers from environment.
"""

import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User, get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.model_registry import (
    fetch_openrouter_models,
    get_logo_for_openrouter_model,
    get_logo_for_provider,
    get_models_for_provider,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(get_current_user_required)])


class Model(BaseModel):
    """Model metadata from registry."""
    id: str
    name: str
    provider: Literal["openai", "anthropic", "cloudflare", "ollama", "openrouter", "xai", "mistral", "perplexity", "google"]
    context_window: int
    supports_streaming: bool
    supports_vision: bool
    supports_function_calling: bool
    max_output_tokens: int | None
    released: str
    logo_url: str | None = None  # Per-model logo (OpenRouter: upstream provider)


class Provider(BaseModel):
    """Available AI provider from environment."""
    id: str
    name: str
    type: Literal["openai", "anthropic", "cloudflare", "ollama", "openrouter", "xai", "mistral", "perplexity", "google"]
    has_api_key: bool
    logo_url: str | None = None
    models: list[Model]  # Models from registry


# Helper function to get API key from database or env
async def has_api_key_configured(
    key_name: str,
    workspace_ids: list[str],
    db: AsyncSession,
) -> bool:
    """Check if API key exists in database secrets or environment."""
    from naas_abi.apps.nexus.apps.api.app.models import SecretModel
    from sqlalchemy import select

    # Check database first
    result = await db.execute(
        select(SecretModel.id).where(
            SecretModel.workspace_id.in_(workspace_ids),
            SecretModel.key == key_name,
        ).limit(1)
    )
    if result.first():
        return True

    # Fallback to environment
    return bool(os.getenv(key_name))


@router.get("/available")
async def list_available_providers(
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[Provider]:
    """
    List all available AI providers based on workspace secrets.
    Returns providers with models from the registry.
    """
    from naas_abi.apps.nexus.apps.api.app.models import SecretModel, WorkspaceMemberModel
    from sqlalchemy import select

    providers = []

    # Get user's workspaces to check for secrets
    result = await db.execute(
        select(WorkspaceMemberModel.workspace_id).where(
            WorkspaceMemberModel.user_id == current_user.id
        )
    )
    workspace_ids = [row[0] for row in result.fetchall()]

    if not workspace_ids:
        logger.warning(f"User {current_user.id} has no workspaces")
        return providers

    # Check which API keys exist in any of the user's workspaces
    result = await db.execute(
        select(SecretModel.key).where(
            SecretModel.workspace_id.in_(workspace_ids)
        )
    )
    raw_secret_keys = {row[0] for row in result.fetchall()}

    # Canonical provider keys we check for
    CANONICAL_KEYS = frozenset({
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY", "MISTRAL_API_KEY",
        "PERPLEXITY_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY",
        "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID",
    })
    # Map alternate forms (e.g. openrouter_api_key) -> canonical
    KEY_ALIASES = {
        "openrouter_api_key": "OPENROUTER_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "xai_api_key": "XAI_API_KEY",
        "mistral_api_key": "MISTRAL_API_KEY",
        "perplexity_api_key": "PERPLEXITY_API_KEY",
        "google_api_key": "GOOGLE_API_KEY",
        "cloudflare_api_token": "CLOUDFLARE_API_TOKEN",
        "cloudflare_account_id": "CLOUDFLARE_ACCOUNT_ID",
    }

    secret_keys = set()
    for k in raw_secret_keys:
        secret_keys.add(k)
        if k.lower() in KEY_ALIASES:
            secret_keys.add(KEY_ALIASES[k.lower()])
        elif k.upper() in CANONICAL_KEYS:
            secret_keys.add(k.upper())

    logger.info(f"Found secrets (raw): {raw_secret_keys} -> resolved: {secret_keys}")

    # Check environment variables as fallback
    env_keys = set()
    for key in CANONICAL_KEYS:
        if os.getenv(key):
            env_keys.add(key)

    # Combine both sources
    all_keys = secret_keys | env_keys
    logger.info(f"All available keys: {all_keys}")

    # OpenAI
    if "OPENAI_API_KEY" in all_keys:
        models = [Model(**m) for m in get_models_for_provider("openai")]
        providers.append(Provider(
            id="openai",
            name="OpenAI",
            type="openai",
            has_api_key=True,
            logo_url=get_logo_for_provider("openai"),
            models=models,
        ))

    # Anthropic
    if "ANTHROPIC_API_KEY" in all_keys:
        models = [Model(**m) for m in get_models_for_provider("anthropic")]
        providers.append(Provider(
            id="anthropic",
            name="Anthropic",
            type="anthropic",
            has_api_key=True,
            logo_url=get_logo_for_provider("anthropic"),
            models=models,
        ))

    # xAI
    if "XAI_API_KEY" in all_keys:
        models = [Model(**m) for m in get_models_for_provider("xai")]
        providers.append(Provider(
            id="xai",
            name="xAI (Grok)",
            type="xai",
            has_api_key=True,
            logo_url=get_logo_for_provider("xai"),
            models=models,
        ))

    # Mistral
    if "MISTRAL_API_KEY" in all_keys:
        models = [Model(**m) for m in get_models_for_provider("mistral")]
        providers.append(Provider(
            id="mistral",
            name="Mistral AI",
            type="mistral",
            has_api_key=True,
            logo_url=get_logo_for_provider("mistral"),
            models=models,
        ))

    # Perplexity
    if "PERPLEXITY_API_KEY" in all_keys:
        models = [Model(**m) for m in get_models_for_provider("perplexity")]
        providers.append(Provider(
            id="perplexity",
            name="Perplexity",
            type="perplexity",
            has_api_key=True,
            logo_url=get_logo_for_provider("perplexity"),
            models=models,
        ))

    # Google
    if "GOOGLE_API_KEY" in all_keys:
        models = [Model(**m) for m in get_models_for_provider("google")]
        providers.append(Provider(
            id="google",
            name="Google AI",
            type="google",
            has_api_key=True,
            logo_url=get_logo_for_provider("google"),
            models=models,
        ))

    # OpenRouter - fetch 400+ models dynamically from API, per-model logos from upstream
    if "OPENROUTER_API_KEY" in all_keys:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            from naas_abi.apps.nexus.apps.api.app.api.endpoints.secrets import _decrypt

            for wid in workspace_ids:
                for key_variant in ("OPENROUTER_API_KEY", "openrouter_api_key"):
                    result = await db.execute(
                        select(SecretModel).where(
                            SecretModel.workspace_id == wid,
                            SecretModel.key == key_variant,
                        )
                    )
                    secret = result.scalar_one_or_none()
                    if secret:
                        try:
                            api_key = _decrypt(secret.encrypted_value)
                            break
                        except Exception:
                            pass
                if api_key:
                    break
        if api_key:
            raw_models = await fetch_openrouter_models(api_key)
            models = [
                Model(**{**m, "logo_url": get_logo_for_openrouter_model(m["id"])})
                for m in raw_models
            ]
        else:
            raw = get_models_for_provider("openrouter")
            models = [
                Model(**{**m, "logo_url": get_logo_for_openrouter_model(m["id"])})
                for m in raw
            ]
        providers.append(Provider(
            id="openrouter",
            name="OpenRouter",
            type="openrouter",
            has_api_key=True,
            logo_url=get_logo_for_provider("openrouter"),
            models=models,
        ))

    # Cloudflare (require both API token and Account ID)
    if ("CLOUDFLARE_API_TOKEN" in all_keys) and ("CLOUDFLARE_ACCOUNT_ID" in all_keys):
        models = [Model(**m) for m in get_models_for_provider("cloudflare")]
        providers.append(Provider(
            id="cloudflare",
            name="Cloudflare Workers AI",
            type="cloudflare",
            has_api_key=True,
            logo_url=get_logo_for_provider("cloudflare"),
            models=models,
        ))

    # Ollama (always available - local, no API key needed)
    models = [Model(**m) for m in get_models_for_provider("ollama")]
    providers.append(Provider(
        id="ollama",
        name="Ollama (Local)",
        type="ollama",
        has_api_key=False,  # No API key required/configured
        logo_url=get_logo_for_provider("ollama"),
        models=models,
    ))

    return providers
