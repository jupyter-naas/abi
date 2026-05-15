from naas_abi.apps.nexus.apps.api.app.core.config import MarketplaceConfig
from pydantic import BaseModel


class ModuleInfo(BaseModel):
    module_path: str
    name: str
    description: str
    logo_url: str | None = None
    category: str  # "core" | "ai" | "application" | "domain"
    installed: bool
    model: str | None = None
    slug: str | None = None
    agent_type: str | None = None
    system_prompt_preview: str | None = None
    functional: bool = True
    # Marketplace-specific fields extracted from agent source files
    tier: str | None = None          # "community" | "enterprise"
    maintainer: str | None = None    # e.g. "Naas"
    stripe_url: str | None = None    # Stripe payment link for this agent


class ModulesResponse(BaseModel):
    installed: list[ModuleInfo]
    available: list[ModuleInfo]


class MarketplaceConfigResponse(BaseModel):
    """Full marketplace configuration returned by GET /api/modules/config."""
    config: MarketplaceConfig
