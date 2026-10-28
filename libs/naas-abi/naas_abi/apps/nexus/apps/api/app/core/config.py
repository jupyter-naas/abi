"""
Application configuration using pydantic-settings.
"""

from functools import lru_cache
from typing import Any, Literal

from naas_abi.apps.nexus.graph_policy_config import WorkspaceGraphPolicyConfig
from naas_abi.apps.nexus.maps_seed_config import WorkspaceMapsSeedConfig
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Namespace under which ABI serves the seed decks it ships. Reserved: a
# configured source claiming it would shadow rows the picker depends on.
ABI_SLIDES_TEMPLATE_NAMESPACE = "abi"
ABI_DOCUMENTS_TEMPLATE_NAMESPACE = "abi"
ABI_SHEETS_TEMPLATE_NAMESPACE = "abi"


class TenantConfig(BaseModel):
    """Tenant branding surfaced to the browser (tab title, favicon, etc.)."""

    model_config = ConfigDict(extra="forbid")

    tab_title: str = "ABI Nexus | naas.ai"
    favicon_url: str | None = None
    logo_url: str | None = None

    # Open Graph / social sharing preview (used when the platform URL is shared
    # in Slack, Twitter/X, iMessage, LinkedIn, etc.).
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
    show_powered_by: bool = False
    login_footer_text: str | None = None
    apps: list["ExternalAppConfig"] = Field(default_factory=list)


class ExternalAppConfig(BaseModel):
    """External app shortcut displayed in the Apps page."""

    model_config = ConfigDict(extra="forbid")

    name: str
    url: str
    description: str | None = None
    icon_emoji: str | None = None


class SlidesTemplateSourceConfig(BaseModel):
    """One directory of Nexus Slides seed decks, contributed by config.

    ABI ships its own seeds and serves them under the ``abi`` namespace. Any
    other tree a deploy wants in the picker is declared here, which is what
    keeps a consumer's name out of ABI: the deploy says who it is, ABI only
    reads what it is given.
    """

    model_config = ConfigDict(extra="forbid")

    # Prefixed onto every template id from this source (``<namespace>/<id>``)
    # and shown in the picker when more than one namespace is in play. Kebab
    # slug so it survives a round trip through a template id. ``abi`` is taken.
    namespace: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=32)

    # Directory holding ``<id>.html`` seeds and an optional ``catalog.json``.
    # Absolute, or relative to the API working directory.
    path: str = Field(min_length=1)

    @field_validator("namespace")
    @classmethod
    def _namespace_is_not_reserved(cls, value: str) -> str:
        if value == ABI_SLIDES_TEMPLATE_NAMESPACE:
            raise ValueError(
                f"'{ABI_SLIDES_TEMPLATE_NAMESPACE}' is reserved for the seeds "
                "ABI ships. Pick another namespace for this source."
            )
        return value


class DocumentsTemplateSourceConfig(BaseModel):
    """One directory of Nexus Documents seed templates, contributed by config."""

    model_config = ConfigDict(extra="forbid")

    namespace: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=32)
    path: str = Field(min_length=1)

    @field_validator("namespace")
    @classmethod
    def _namespace_is_not_reserved(cls, value: str) -> str:
        if value == ABI_DOCUMENTS_TEMPLATE_NAMESPACE:
            raise ValueError(
                f"'{ABI_DOCUMENTS_TEMPLATE_NAMESPACE}' is reserved for the seeds "
                "ABI ships. Pick another namespace for this source."
            )
        return value


class SheetsTemplateSourceConfig(BaseModel):
    """One directory of Nexus Sheets seed workbooks, contributed by config."""

    model_config = ConfigDict(extra="forbid")

    namespace: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=32)
    path: str = Field(min_length=1)

    @field_validator("namespace")
    @classmethod
    def _namespace_is_not_reserved(cls, value: str) -> str:
        if value == ABI_SHEETS_TEMPLATE_NAMESPACE:
            raise ValueError(
                f"'{ABI_SHEETS_TEMPLATE_NAMESPACE}' is reserved for the seeds "
                "ABI ships. Pick another namespace for this source."
            )
        return value


class ModelPricingEntry(BaseModel):
    """LLM token cost for one model (USD per 1M tokens, May 2026 rates)."""

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
    """
    Maintenance fee configuration for Enterprise-tier marketplace agents.

    These are expert retainer fees — not software licenses. They fund the
    AI engineers doing continuous domain knowledge curation, model migration,
    ontology updates, and integration patching for each agent.
    """

    model_config = ConfigDict(extra="forbid")

    # Standard rate (live, fully maintained agents)
    maintenance_standard_usd: int = 499
    # Early-access rate (preview agents, introductory pricing)
    maintenance_early_access_usd: int = 299
    # CTA URL for Subscribe / Early Access buttons
    cta_url: str = "https://naas.ai/enterprise"
    # Module categories considered Enterprise-maintained
    enterprise_categories: list[str] = Field(default_factory=lambda: ["domain"])
    # Token split between input (system prompt + context) and output (answer)
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

    # Prices in USD per 1M tokens (May 2026 rates).
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
            "o1": ModelPricingEntry(input_per_million=15.00, output_per_million=60.00, label="o1"),
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


FeatureKey = Literal[
    "maps",
    "chat",
    "files",
    "agents",
    "skills",
    "apps",
    "marketplace",
    "search",
    "ontology",
    "graph",
    "datasets",
    "settings",
    "code",
    "slides",
    "documents",
    "sheets",
    "tasks",
]


class FeatureFlagsConfig(BaseModel):
    """Feature access policy exposed to Nexus frontend."""

    model_config = ConfigDict(extra="forbid")

    enabled_features: list[FeatureKey] = Field(
        default_factory=lambda: [
            "maps",
            "chat",
            "files",
            "agents",
            "skills",
            "apps",
            "marketplace",
            "search",
            "ontology",
            "graph",
            "datasets",
            "settings",
            "slides",
            "documents",
            "sheets",
            "tasks",
        ]
    )
    # Deprecated: no role brings a feature, a policy does. Read once, when Nexus
    # moves what each role had in each workspace into that workspace's policy
    # "Features of <role>" (services/iam/role_features.py); a configuration
    # that still sets it gets a warning at start, and it does nothing.
    role_baseline: dict[str, list[FeatureKey]] = Field(
        default_factory=lambda: {
            "owner": [
                "maps",
                "chat",
                "files",
                "agents",
                "skills",
                "apps",
                "marketplace",
                "search",
                "ontology",
                "graph",
                "datasets",
                "settings",
                "slides",
                "documents",
                "sheets",
                "tasks",
            ],
            "admin": [
                "maps",
                "chat",
                "files",
                "agents",
                "skills",
                "apps",
                "marketplace",
                "search",
                "ontology",
                "graph",
                "datasets",
                "settings",
                "slides",
                "documents",
                "sheets",
                "tasks",
            ],
            "member": [
                "maps",
                "chat",
                "files",
                "datasets",
                "skills",
                "slides",
                "documents",
                "sheets",
            ],
            "viewer": [
                "maps",
                "chat",
                "files",
                "datasets",
                "skills",
                "slides",
                "documents",
                "sheets",
            ],
        }
    )
    # Deprecated: read once, when Nexus moves the per-workspace overrides into
    # the workspaces' feature sets (IAM's; services/iam/sets.py). A feature
    # turned off leaves the set; one turned on is kept for whoever held a role
    # there then. Edit sets on the modules × workspaces page.
    workspace_overrides: dict[str, dict[FeatureKey, bool]] = Field(default_factory=dict)
    # Deprecated, with role_baseline: per-organization role_baseline overlays,
    # keyed by organization id. Read once, by the move of the role features.
    organization_overrides: dict[str, dict[str, list[FeatureKey]]] = Field(default_factory=dict)


class UserSeedConfig(BaseModel):
    """User definition applied on startup (create by email if missing)."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    name: str
    avatar: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    is_superadmin: bool = False

    @model_validator(mode="before")
    @classmethod
    def _ignore_the_stored_password_setting(cls, data: Any) -> Any:
        """No password is made for a configured user any more (they sign in at the
        built-in identity provider): the old setting is accepted and ignored."""
        if isinstance(data, dict) and "store_credentials_in_secrets" in data:
            data = {k: v for k, v in data.items() if k != "store_credentials_in_secrets"}
        return data


class OrganizationMemberSeedConfig(BaseModel):
    """Deprecated: organization members are managed in the platform."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: Literal["owner", "admin", "member"] = "member"


class WorkspaceMemberSeedConfig(BaseModel):
    """Deprecated: workspace members are managed in the platform."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: Literal["owner", "admin", "member", "viewer"] = "member"


class WorkspaceSeedConfig(BaseModel):
    """Workspace definition applied on startup (upsert by slug)."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    # Name, owner, group and branding are managed in the app; config.workspaces.yaml
    # snapshots them (core/workspaces_import replays it). Still accepted here,
    # bootstrap only; a workspace created without a name is named after its slug.
    name: str | None = None
    # Defaults to the organization owner. Org owners and admins reach every
    # workspace of their org without a membership row.
    owner_email: EmailStr | None = None
    # Deprecated and ignored by the seed (kept so older configs still load).
    members: list[WorkspaceMemberSeedConfig] = Field(default_factory=list)

    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    background_image_url: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None
    # Group in the workspace lists ("Others" when empty). Bootstrap only: applied
    # when the workspace has no group yet, so a group changed in the UI stays.
    group: str | None = Field(default=None, max_length=100)
    # Client/module workspace default (``external.acme AcmeAgent``). When unset,
    # sync uses engine ``default_agent`` (typically naas_abi AbiAgent).
    default_agent: str | None = None
    agents: list[str] | None = None
    apps: list[str] | None = None
    # Initial assignments only; saved workspace resource policies take precedence.
    # Ontology catalog ids (``module:filename.ttl``). Exclusive when a list
    # is set: listed on, others off. Missing, null and empty lists show none.
    # owl:imports are not implied; explicitly list shared dependency files too.
    ontologies: list[str] | None = Field(default_factory=list)
    # Exact data graph grants. Missing policy exposes owned graphs only.
    graphs: WorkspaceGraphPolicyConfig = Field(default_factory=WorkspaceGraphPolicyConfig)
    # Initial Maps feeds and custom basemaps (see WorkspaceMapsSeedConfig).
    maps: WorkspaceMapsSeedConfig | None = None


class OrganizationSeedConfig(BaseModel):
    """Organization definition applied on startup (upsert by slug)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str
    owner_email: EmailStr | None = None
    # Deprecated and ignored by the seed (kept so older configs still load).
    members: list[OrganizationMemberSeedConfig] = Field(default_factory=list)
    workspaces: list[WorkspaceSeedConfig] = Field(default_factory=list)

    logo_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    font_family: str | None = None
    font_url: str | None = None

    login_card_max_width: str | None = None
    login_card_padding: str | None = None
    login_card_color: str | None = None
    login_text_color: str | None = None
    login_input_color: str | None = None
    login_border_radius: str | None = None
    login_bg_image_url: str | None = None
    show_terms_footer: bool = True
    show_powered_by: bool = False
    login_footer_text: str | None = None
    secondary_logo_url: str | None = None
    show_logo_separator: bool = False
    default_theme: str | None = None


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )

    # Tenant branding (tab title, favicon)
    tenant: TenantConfig = Field(default_factory=TenantConfig)

    # Feature access policy consumed by workspace bootstrap responses
    feature_flags: FeatureFlagsConfig = Field(default_factory=FeatureFlagsConfig)

    # Marketplace pricing, usage tiers, and model token costs
    marketplace: MarketplaceConfig = Field(default_factory=MarketplaceConfig)

    # Extra Slides seed trees for the template picker. Additive: ABI's own
    # seeds are always served, so this list holds only what a deploy adds.
    slides_template_sources: list[SlidesTemplateSourceConfig] = Field(default_factory=list)
    documents_template_sources: list[DocumentsTemplateSourceConfig] = Field(default_factory=list)
    # Empty keeps ABI's own seed as the New Document default. A deploy that
    # adds sources can point this at one of those ids so a plain create
    # matches the picker, without ABI naming that source.
    documents_default_template_id: str | None = Field(default=None, max_length=96)
    # Qualified ids or bare stems omitted from the Documents picker. Create
    # and apply still accept them, so existing documents keep working.
    documents_hidden_template_ids: list[str] = Field(default_factory=list)
    sheets_template_sources: list[SheetsTemplateSourceConfig] = Field(default_factory=list)

    # Bootstrap users (created by email on startup). Keep this to platform
    # operators: everyone else is invited from the platform. is_superadmin
    # only promotes; demote with PATCH /api/admin/users/{id}.
    users: list[UserSeedConfig] = Field(default_factory=list)

    # Organization seed configs (upserted by slug on startup)
    organizations: list[OrganizationSeedConfig] = Field(default_factory=list)

    # App
    app_name: str = "NEXUS API"
    debug: bool = False
    environment: str = "development"
    nexus_env: str = "local"  # Environment name (local, cloudflare, staging)

    # API
    api_prefix: str = "/api"
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    websocket_path: str = "/ws/socket.io"

    # Graph (Composer) query cache: TTL for cached page rows / count / column discovery.
    # Env: GRAPH_QUERY_CACHE_TTL_SECONDS. 0 disables caching (always live).
    graph_query_cache_ttl_seconds: int = 300

    # Coding workspaces (Coder editor + Forgejo monorepo auto-clone). clone
    # host/scheme are what a *workspace container* uses to reach Forgejo (not the
    # admin API URL); docker_network is the network the workspace must join to
    # reach it (empty = don't attach).
    coding_repo_id: str = "abi/monorepo"
    coding_git_clone_scheme: str = "http"
    coding_git_clone_host: str = "forgejo:3000"
    coding_workspace_docker_network: str = ""
    # Externally-reachable Forgejo base (what a developer's laptop uses to push),
    # distinct from the internal clone host workspaces use. No trailing slash.
    coding_git_public_base: str = "https://git.nexus.localhost"
    # In-IDE agent bridge: the Nexus API base a *workspace* uses to reach the
    # OpenAI shim (Continue appends /api/v1), the default agent, and how long the
    # injected access token lives.
    coding_agent_api_base: str = "http://abi:9879"
    coding_default_agent: str = "AbiAgent"
    coding_agent_token_days: int = 30

    # Database
    database_url: str = "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"  # PostgreSQL only

    # Nexus has no login of its own: people sign in at an identity provider
    # (``identity.providers``, ``oidc_*`` below). Nothing here signs a token.
    #
    # Encrypts workspace secrets and the provider tokens of sessions (Fernet). Its
    # own key, never ``secret_key``: empty, it is generated and kept in the engine's
    # secret store as ``NEXUS_SECRETS_KEY`` (``core/secret_key.py``).
    secrets_encryption_key: str = ""
    # This key used to sign Nexus's tokens and encrypt the secrets. It
    # signs nothing now, and is read at start only to move what it encrypted under
    # ``secrets_encryption_key``; unset it once Nexus logged that it had.
    secret_key: str = ""
    # Lifetime of a link for opening /app-html apps (Bearer or ?token=): an IAM
    # grant: a longer setting is accepted and clamped to eight hours.
    app_html_access_token_expire_minutes: int = Field(default=60, ge=1, le=24 * 60)
    # HMAC secret for opening Cloudflare Pages portals from Nexus (empty = off).
    pages_sso_secret: str = ""
    pages_sso_expire_seconds: int = Field(default=300, ge=30, le=15 * 60)
    # Apps builder: "Submit" sends an app project to its source repository
    # (GitHub owner/name) as a review branch. Off unless both the repo and
    # APPS_SUBMIT_TOKEN (env only, never in config files) are set.
    apps_submit_repo: str = ""
    apps_submit_base_branch: str = "main"
    apps_submit_token: str = ""
    apps_submit_open_pull_request: bool = True
    apps_submit_api_base: str = "https://api.github.com"
    apps_submit_web_base: str = "https://github.com"
    # Lifetime of an /app-preview/ token (the editor re-mints on reload).
    app_preview_token_expire_minutes: int = Field(default=60, ge=1, le=24 * 60)
    # Lifetime of an /app-remote/ grant (a remote module's app, reopened to renew).
    remote_app_grant_expire_minutes: int = Field(default=8 * 60, ge=1, le=24 * 60)
    # The name an email Nexus sends (an invitation) calls the application.
    email_app_name: str = "NEXUS"

    # Outgoing email "From" metadata. Transport details (host, credentials,
    # adapter type) live in the engine config under `services.email`.
    email_from_address: EmailStr = "no-reply@nexus.example.com"
    email_from_name: str = "NEXUS"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_attempts: int = 5  # Max attempts per account (or inviting user) per window
    rate_limit_ip_attempts: int = 20  # Max attempts per client IP per window
    rate_limit_window_seconds: int = 300  # 5-minute window

    # Sign-in through the engine's identity providers (``identity.providers``).
    # The session is an httpOnly, Secure cookie the API holds; "none" is for a
    # web app on another site than the API (it then needs HTTPS on both).
    oidc_session_cookie: str = Field(default="nexus_session", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    oidc_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    oidc_session_max_age_hours: int = Field(default=7 * 24, ge=1, le=90 * 24)
    # Where providers send the browser back; default {api_url}/api/auth/oidc/callback.
    oidc_redirect_uri: str | None = None
    # Origins of other relying parties of the built-in IdP (/idp); Nexus's own
    # (the redirect URI's and the web app's) are implied.
    idp_client_origins: list[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        """Adjust settings based on environment after initialization (pydantic v2 hook)."""
        # Make Ollama autostart opt-in and local-only
        # - Enable by setting ENABLE_OLLAMA_AUTOSTART=true
        # - Force OFF unless environment is development or nexus_env is local
        if not (self.environment == "development" or self.nexus_env == "local"):
            self.enable_ollama_autostart = False

    # Security Headers
    enable_security_headers: bool = True
    content_security_policy: str | None = None  # Set in production

    # ABI Engine
    abi_api_url: str = "http://localhost:8001"
    abi_api_key: str | None = None

    # OpenAI (for embeddings/fallback)
    openai_api_key: str | None = None

    # Anthropic (Claude)
    anthropic_api_key: str | None = None

    # Cloudflare Workers AI
    cloudflare_api_token: str | None = None
    cloudflare_account_id: str | None = None

    # Local AI (Ollama) autostart
    # Default OFF; enabled automatically in local development.
    enable_ollama_autostart: bool = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()


def current_secrets_key() -> str:
    """The key that encrypts workspace secrets, read at call time.

    ``naas_abi`` replaces ``settings`` after this module is imported, so a
    module-level ``from ... import settings`` can hold a stale object. Empty only
    before the API resolved it at start: nothing is encrypted under no key.
    """
    key = settings.secrets_encryption_key
    if not key:
        raise RuntimeError(
            "No secrets encryption key is loaded: the API resolves it at start (core/secret_key.py)"
        )
    return key
