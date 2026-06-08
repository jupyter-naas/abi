from typing import Literal

from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from pydantic import BaseModel, ConfigDict, EmailStr, Field


def _initialize_nexus_service_registry() -> None:
    try:
        from naas_abi.apps.nexus.apps.api.app.services.registry_bootstrap import (
            initialize_nexus_service_registry,
        )

        initialize_nexus_service_registry()
    except Exception:
        # Registry warm-up must never block module import.
        pass


class ModelPricingEntry(BaseModel):
    """LLM token cost for one model (USD per 1M tokens)."""

    model_config = ConfigDict(extra="forbid")

    input_per_million: float
    output_per_million: float
    label: str


class MarketplaceUsageTier(BaseModel):
    """A concrete usage scenario used to estimate monthly LLM token costs."""

    model_config = ConfigDict(extra="forbid")

    label: str
    interactions: int
    avg_tokens: int
    description: str


class MarketplacePricingConfig(BaseModel):
    """Maintenance fee configuration (expert retainer, not a license)."""

    model_config = ConfigDict(extra="forbid")

    maintenance_standard_usd: int = 499
    maintenance_early_access_usd: int = 299
    cta_url: str = "https://naas.ai/enterprise"
    enterprise_categories: list[str] = Field(default_factory=lambda: ["domain"])
    input_output_ratio: float = 0.6


class MarketplaceConfig(BaseModel):
    """Full marketplace configuration surfaced to the frontend via /api/modules/config."""

    model_config = ConfigDict(extra="forbid")

    pricing: MarketplacePricingConfig = Field(default_factory=MarketplacePricingConfig)
    usage_tiers: list[MarketplaceUsageTier] = Field(
        default_factory=lambda: [
            MarketplaceUsageTier(
                label="Starter",
                interactions=50,
                avg_tokens=2_000,
                description="~2 queries/day",
            ),
            MarketplaceUsageTier(
                label="Professional",
                interactions=300,
                avg_tokens=5_000,
                description="~10 queries/day",
            ),
            MarketplaceUsageTier(
                label="Scale",
                interactions=2_000,
                avg_tokens=10_000,
                description="~65 queries/day, team use",
            ),
        ]
    )
    model_pricing: dict[str, ModelPricingEntry] = Field(
        default_factory=lambda: {
            "gpt-4o": ModelPricingEntry(
                input_per_million=2.50, output_per_million=10.00, label="GPT-4o"
            ),
            "gpt-4o-mini": ModelPricingEntry(
                input_per_million=0.15, output_per_million=0.60, label="GPT-4o mini"
            ),
            "gpt-4": ModelPricingEntry(
                input_per_million=30.00, output_per_million=60.00, label="GPT-4"
            ),
            "gpt-3.5-turbo": ModelPricingEntry(
                input_per_million=0.50, output_per_million=1.50, label="GPT-3.5 Turbo"
            ),
            "o1": ModelPricingEntry(
                input_per_million=15.00, output_per_million=60.00, label="o1"
            ),
            "o3-mini": ModelPricingEntry(
                input_per_million=1.10, output_per_million=4.40, label="o3-mini"
            ),
            "claude-opus": ModelPricingEntry(
                input_per_million=15.00, output_per_million=75.00, label="Claude Opus"
            ),
            "claude-sonnet": ModelPricingEntry(
                input_per_million=3.00, output_per_million=15.00, label="Claude Sonnet"
            ),
            "claude-haiku": ModelPricingEntry(
                input_per_million=0.25, output_per_million=1.25, label="Claude Haiku"
            ),
            "gemini-1.5-pro": ModelPricingEntry(
                input_per_million=3.50, output_per_million=10.50, label="Gemini 1.5 Pro"
            ),
            "gemini-1.5-flash": ModelPricingEntry(
                input_per_million=0.075, output_per_million=0.30, label="Gemini Flash"
            ),
        }
    )


class TenantConfig(BaseModel):
    """Tenant branding surfaced to the browser (tab title, favicon, etc.)."""

    model_config = ConfigDict(extra="forbid")

    tab_title: str = "ABI Nexus | naas.ai"
    favicon_url: str | None = None
    logo_url: str | None = None
    og_title: str | None = None
    og_description: str | None = None
    og_image_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str = "#34D399"
    accent_color: str = "#1FA574"
    background_color: str = "#FFFFFF"
    font_family: str | None = None
    font_url: str | None = None
    login_card_max_width: str = "440px"
    login_card_padding: str = "2.5rem 3rem 3rem"
    login_card_color: str = "#FFFFFF"
    login_text_color: str | None = None
    login_input_color: str = "#F4F4F4"
    login_border_radius: str = "0"
    login_bg_image_url: str | None = None
    show_terms_footer: bool = False
    show_powered_by: bool = True
    login_footer_text: str | None = None
    apps: list["ExternalAppConfig"] = Field(default_factory=list)


class ExternalAppConfig(BaseModel):
    """External app shortcut displayed in the Apps page."""

    model_config = ConfigDict(extra="forbid")

    name: str
    url: str
    description: str | None = None
    icon_emoji: str | None = None


FeatureKey = Literal[
    "chat",
    "files",
    "agents",
    "apps",
    "marketplace",
    "search",
    "ontology",
    "graph",
    "settings",
]

_ALL_FEATURES: list[FeatureKey] = [
    "chat",
    "files",
    "agents",
    "apps",
    "marketplace",
    "search",
    "ontology",
    "graph",
    "settings",
]


def _default_enabled_features() -> list[FeatureKey]:
    return list(_ALL_FEATURES)


def _default_role_baseline() -> dict[str, list[FeatureKey]]:
    return {
        "owner": list(_ALL_FEATURES),
        "admin": list(_ALL_FEATURES),
        "member": ["chat", "files"],
        "viewer": ["chat", "files"],
    }


class FeatureFlagsConfig(BaseModel):
    """Feature access policy exposed to Nexus frontend."""

    model_config = ConfigDict(extra="forbid")

    enabled_features: list[FeatureKey] = Field(
        default_factory=_default_enabled_features
    )
    role_baseline: dict[str, list[FeatureKey]] = Field(
        default_factory=_default_role_baseline
    )
    workspace_overrides: dict[str, dict[FeatureKey, bool]] = Field(default_factory=dict)


class UserSeedConfig(BaseModel):
    """User definition applied on startup (create by email if missing)."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    name: str
    avatar: str | None = None
    company: str | None = None
    role: str | None = None
    bio: str | None = None
    is_superadmin: bool = False
    store_credentials_in_secrets: bool = True


class OrganizationMemberSeedConfig(BaseModel):
    """Organization member assignment."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: Literal["owner", "admin", "member"] = "member"


class WorkspaceMemberSeedConfig(BaseModel):
    """Workspace member assignment."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: Literal["owner", "admin", "member", "viewer"] = "member"


class WorkspaceSeedConfig(BaseModel):
    """Workspace definition applied on startup (upsert by slug)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str
    owner_email: EmailStr | None = None
    members: list[WorkspaceMemberSeedConfig] = Field(default_factory=list)

    # Workspace-level theming
    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None


class OrganizationSeedConfig(BaseModel):
    """Organization definition applied on startup (upsert by slug).

    Existing orgs get their branding fields updated.
    New orgs are created when ``owner_email`` resolves to a known user.
    """

    model_config = ConfigDict(extra="forbid")

    # Identity (slug is the upsert key)
    name: str
    slug: str
    owner_email: EmailStr | None = None
    members: list[OrganizationMemberSeedConfig] = Field(default_factory=list)
    workspaces: list[WorkspaceSeedConfig] = Field(default_factory=list)

    # Branding
    logo_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    font_family: str | None = None
    font_url: str | None = None

    # Login page styling
    login_card_max_width: str | None = None
    login_card_padding: str | None = None
    login_card_color: str | None = None
    login_text_color: str | None = None
    login_input_color: str | None = None
    login_border_radius: str | None = None
    login_bg_image_url: str | None = None
    show_terms_footer: bool = True
    show_powered_by: bool = True
    login_footer_text: str | None = None
    secondary_logo_url: str | None = None
    show_logo_separator: bool = False
    default_theme: str | None = None


class NexusConfig(BaseModel):
    """Nexus runtime settings wired into app.core.config.Settings."""

    model_config = ConfigDict(extra="forbid")

    app_name: str = "NEXUS API"
    debug: bool = False
    environment: str = "development"
    nexus_env: str = "local"

    api_prefix: str = "/api"
    api_url: str = "http://localhost:9879"
    frontend_url: str = "http://localhost:3042"
    websocket_path: str = "/ws/socket.io"

    database_url: str = "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"

    ontology_base_uri: str = "http://ontology.naas.ai/"

    secret_key: str = "change-me-in-production"
    auth_password_enabled: bool = False
    magic_link_allow_signup: bool = False
    access_token_expire_minutes: int = 1440
    refresh_token_expire_days: int = 30
    magic_link_expire_minutes: int = 15
    magic_link_path: str = "/auth/magic-link"
    magic_link_email_app_name: str = "NEXUS"
    magic_link_email_subject_template: str = "Your {app_name} magic sign-in link"
    magic_link_email_text_template: str = (
        "Use the link below to sign in to {app_name}:\n\n"
        "{magic_link_url}\n\n"
        "This link expires in {expire_minutes} minutes."
    )
    magic_link_email_html_template: str = (
        "<p>Use the link below to sign in to {app_name}:</p>"
        '<p><a href="{magic_link_url}">Sign in to {app_name}</a></p>'
        "<p>This link expires in {expire_minutes} minutes.</p>"
    )
    email_from_address: EmailStr = "no-reply@nexus.example.com"
    email_from_name: str = "NEXUS"

    rate_limit_enabled: bool = True
    rate_limit_login_attempts: int = 5
    rate_limit_window_seconds: int = 300

    enable_security_headers: bool = True
    content_security_policy: str | None = None

    abi_api_url: str = "http://localhost:9879"
    abi_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    cloudflare_api_token: str | None = None
    cloudflare_account_id: str | None = None
    enable_ollama_autostart: bool = False

    tenant: TenantConfig = Field(default_factory=TenantConfig)
    feature_flags: FeatureFlagsConfig = Field(default_factory=FeatureFlagsConfig)
    marketplace: MarketplaceConfig = Field(default_factory=MarketplaceConfig)
    users: list[UserSeedConfig] = Field(default_factory=list)
    organizations: list[OrganizationSeedConfig] = Field(default_factory=list)


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_core.modules.templatablesparqlquery",
            "naas_abi_marketplace.ai.chatgpt#soft",
            "naas_abi_marketplace.ai.claude#soft",
            "naas_abi_marketplace.ai.deepseek#soft",
            "naas_abi_marketplace.ai.gemini#soft",
            "naas_abi_marketplace.ai.gemma#soft",
            "naas_abi_marketplace.ai.grok#soft",
            "naas_abi_marketplace.ai.llama#soft",
            "naas_abi_marketplace.ai.mistral#soft",
            "naas_abi_marketplace.ai.perplexity#soft",
            "naas_abi_marketplace.ai.qwen#soft",
            "naas_abi_marketplace.applications.agicap#soft",
            "naas_abi_marketplace.applications.airtable#soft",
            "naas_abi_marketplace.applications.algolia#soft",
            "naas_abi_marketplace.applications.arxiv#soft",
            "naas_abi_marketplace.applications.aws#soft",
            "naas_abi_marketplace.applications.bodo#soft",
            "naas_abi_marketplace.applications.datagouv#soft",
            "naas_abi_marketplace.applications.exchangeratesapi#soft",
            "naas_abi_marketplace.applications.git#soft",
            "naas_abi_marketplace.applications.github#soft",
            "naas_abi_marketplace.applications.gmail#soft",
            "naas_abi_marketplace.applications.google_analytics#soft",
            "naas_abi_marketplace.applications.google_calendar#soft",
            "naas_abi_marketplace.applications.google_drive#soft",
            "naas_abi_marketplace.applications.google_maps#soft",
            "naas_abi_marketplace.applications.google_search#soft",
            "naas_abi_marketplace.applications.google_sheets#soft",
            "naas_abi_marketplace.applications.hubspot#soft",
            "naas_abi_marketplace.applications.instagram#soft",
            "naas_abi_marketplace.applications.linkedin#soft",
            "naas_abi_marketplace.applications.mercury#soft",
            "naas_abi_marketplace.applications.naas#soft",
            "naas_abi_marketplace.applications.nebari#soft",
            "naas_abi_marketplace.applications.newsapi#soft",
            "naas_abi_marketplace.applications.notion#soft",
            "naas_abi_marketplace.applications.openalex#soft",
            "naas_abi_marketplace.applications.openrouter#soft",
            "naas_abi_marketplace.applications.openweathermap#soft",
            "naas_abi_marketplace.applications.pennylane#soft",
            "naas_abi_marketplace.applications.postgres#soft",
            "naas_abi_marketplace.applications.powerpoint#soft",
            "naas_abi_marketplace.applications.pubmed#soft",
            "naas_abi_marketplace.applications.qonto#soft",
            "naas_abi_marketplace.applications.salesforce#soft",
            "naas_abi_marketplace.applications.sanax#soft",
            "naas_abi_marketplace.applications.sendgrid#soft",
            "naas_abi_marketplace.applications.sharepoint#soft",
            "naas_abi_marketplace.applications.slack#soft",
            "naas_abi_marketplace.applications.spotify#soft",
            "naas_abi_marketplace.applications.stripe#soft",
            "naas_abi_marketplace.applications.twilio#soft",
            "naas_abi_marketplace.applications.whatsapp_business#soft",
            "naas_abi_marketplace.applications.worldbank#soft",
            "naas_abi_marketplace.applications.yahoofinance#soft",
            "naas_abi_marketplace.applications.youtube#soft",
            "naas_abi_marketplace.applications.zoho#soft",
            "naas_abi_marketplace.domains.support#soft",
        ],
        services=[
            Secret,
            TripleStoreService,
            ObjectStorageService,
            VectorStoreService,
            BusService,
            CacheService,
            EmailService,
            ActivityLogService,
            EventService,
            ModelRegistryService,
        ],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi
        enabled: true
        config:
            datastore_path: "abi"
            workspace_id: "{{ secret.WORKSPACE_ID }}"
            storage_name: "{{ secret.STORAGE_NAME }}"
            nexus_config:
                # All settings accepted by app.core.config.Settings
                database_url: "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"
                api_url: "http://localhost:9879"
                frontend_url: "http://localhost:3042"
                websocket_path: "/ws/socket.io"
                tenant:
                    tab_title: "My Portal"
                    favicon_url: "https://example.com/favicon.ico"
                users:
                    - email: "owner@example.com"
                      name: "Owner User"
                      store_credentials_in_secrets: true
                organizations:
                    - name: "My Company"
                      slug: "my-company"
                      owner_email: "admin@example.com"
                      logo_url: "https://example.com/logo-square.png"
                      logo_rectangle_url: "https://example.com/logo-rectangle.png"
                      primary_color: "#FF5500"
                      accent_color: "#1E293B"
                      login_footer_text: "© 2026 My Company"
                      show_powered_by: false
                      default_theme: "dark"
                      members:
                        - email: "admin@example.com"
                          role: "admin"
                      workspaces:
                        - name: "Ops Workspace"
                          slug: "ops-workspace"
                          owner_email: "owner@example.com"
                          members:
                            - email: "admin@example.com"
                              role: "member"
        """

        datastore_path: str = "abi"
        workspace_id: str | None = None
        storage_name: str | None = None

        # Canonical model id used by AbiAgent. Must resolve against the
        # ModelRegistry once all modules have loaded; the engine's
        # validate_defaults pass will surface any mismatch.
        abi_agent_model: str = "claude-sonnet-4.6"

        # Optional provider pin. When multiple modules register the same
        # canonical id (e.g. ``claude-sonnet-4`` ships via both the anthropic
        # and bedrock modules), set this to disambiguate. Leave None to take
        # whichever provider registered first.
        abi_agent_provider: str | None = None

        # Canonical model id used by OntologyEngineerAgent. Same registry
        # semantics as ``abi_agent_model``.
        ontology_engineer_model: str = "claude-sonnet-4.6"
        ontology_engineer_provider: str | None = None

        # Canonical nexus runtime settings (passed to app.core.config.Settings).
        nexus_config: NexusConfig = Field(default_factory=NexusConfig)

    def on_initialized(self):
        super().on_initialized()
        # Initialize Nexus settings and service registry

        from naas_abi.apps.nexus.apps.api.app.core import config as nexus_config

        settings_kwargs = self.configuration.nexus_config.model_dump(exclude_none=True)

        nexus_config.settings = nexus_config.Settings(**settings_kwargs)

        _initialize_nexus_service_registry()

        import glob
        import os

        # Convert ontologies to Python classes.
        from naas_abi_core import logger
        from naas_abi_core.utils.onto2py import onto2py

        ontologies_dir = os.path.join(os.path.dirname(__file__), "ontologies")
        ttl_files = glob.glob(
            os.path.join(ontologies_dir, "modules", "*.ttl"), recursive=True
        )

        if not ttl_files:
            logger.warning(f"No TTL files found in {ontologies_dir}")
            return

        for ttl_file in ttl_files:
            try:
                logger.debug(f"Converting {ttl_file} to Python")
                onto2py(ttl_file)
            except Exception as e:
                logger.error(
                    f"Failed to convert {ttl_file} to Python: {e}", exc_info=True
                )

    def on_load(self):
        super().on_load()
        # from naas_abi_core.services.triple_store.TripleStorePorts import OntologyEvent
        # from rdflib import URIRef

        # self.engine.services.triple_store.subscribe(
        #     (URIRef("http://example.com/subject"), None, None),
        #     lambda triple: print(f"Triple received: {triple.decode('utf-8')}"),
        #     OntologyEvent.INSERT,
        # )

    def api(self, app: FastAPI) -> None:
        # Initialize Nexus platform (graphs + agent metadata in the triple
        # store). Deferred from on_initialized so non-API entry points
        # (Dagster run workers, CLI commands, tests) don't pay this cost.
        from naas_abi.pipelines.NexusPlatformPipeline import (
            NexusPlatformPipeline,
            NexusPlatformPipelineConfiguration,
            NexusPlatformPipelineParameters,
        )

        pipeline = NexusPlatformPipeline(
            NexusPlatformPipelineConfiguration(
                triple_store=self.engine.services.triple_store,
                object_storage=self.engine.services.object_storage,
            )
        )
        pipeline.run(NexusPlatformPipelineParameters())

        # Keep API and Nexus CORS aligned from a single source of truth.
        app.state.abi_cors_origins = self.engine.api_configuration.cors_origins

        # Expose ABI object storage to Nexus routes.
        app.state.object_storage = self.engine.services.object_storage
        # Expose Secret service to Nexus startup provisioning.
        app.state.secret_service = self.engine.services.secret
        # Expose ABI triple store to Nexus graph routes.
        app.state.triple_store = self.engine.services.triple_store
        # Expose the configured email adapter so Nexus magic-link sends use
        # whichever transport the engine config picked (e.g. `filesystem`
        # in dev, `smtp` in prod) instead of always constructing an SMTP
        # client inline.
        app.state.email_service = self.engine.services.email
        # Expose ABI activity-log service so the Nexus middleware can
        # record one event per HTTP request.
        if self.engine.services.activity_log_available():
            app.state.activity_log_service = self.engine.services.activity_log

        from naas_abi.apps.nexus.apps.api.app.main import create_app

        create_app(app)
