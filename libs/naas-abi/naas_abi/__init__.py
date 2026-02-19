from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TenantConfig(BaseModel):
    """Tenant branding surfaced to the browser (tab title, favicon, etc.)."""

    model_config = ConfigDict(extra="forbid")

    tab_title: str = "ABI Nexus | naas.ai"
    favicon_url: str | None = None
    logo_url: str | None = None
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


class UserSeedConfig(BaseModel):
    """User definition applied on startup (create by email if missing)."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    name: str
    avatar: str | None = None
    company: str | None = None
    role: str | None = None
    bio: str | None = None
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
    cors_origins_str: str = "http://localhost:3042,http://127.0.0.1:3042"
    cors_origins: str | None = None
    websocket_path: str = "/ws/socket.io"

    database_url: str = "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

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
    auto_seed_demo_data: bool = True

    tenant: TenantConfig = Field(default_factory=TenantConfig)
    users: list[UserSeedConfig] = Field(default_factory=list)
    organizations: list[OrganizationSeedConfig] = Field(default_factory=list)


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_core.modules.templatablesparqlquery",
            "naas_abi_marketplace.ai.chatgpt",
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
        services=[Secret, TripleStoreService, ObjectStorageService],
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
                redis_url: "redis://localhost:6379/0"
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

        # Canonical nexus runtime settings (passed to app.core.config.Settings).
        nexus_config: NexusConfig = Field(default_factory=NexusConfig)

    # def on_initialized(self):
    #     if (
    #         self.configuration.anthropic_api_key is not None
    #         and "naas_abi_marketplace.ai.claude" not in self.engine.modules
    #     ):
    #         raise ValueError(
    #             "anthropic_api_key is provided but naas_abi_marketplace.ai.claude is not available"
    #         )

    def on_load(self):
        super().on_load()
        from naas_abi_core.services.triple_store.TripleStorePorts import OntologyEvent
        from rdflib import URIRef

        self.engine.services.triple_store.subscribe(
            (URIRef("http://example.com/subject"), None, None),
            lambda triple: print(f"Triple received: {triple.decode('utf-8')}"),
            OntologyEvent.INSERT,
        )

    def api(self, app: FastAPI) -> None:
        # Initialize Nexus settings

        from naas_abi.apps.nexus.apps.api.app.core import config as nexus_config

        # We override settings with module config from `nexus_config`.
        settings_kwargs = self.configuration.nexus_config.model_dump(exclude_none=True)

        nexus_config.settings = nexus_config.Settings(**settings_kwargs)

        # Expose ABI object storage to Nexus routes.
        app.state.object_storage = self.engine.services.object_storage
        # Expose Secret service to Nexus startup provisioning.
        app.state.secret_service = self.engine.services.secret
        # Expose ABI triple store to Nexus graph routes.
        app.state.triple_store = self.engine.services.triple_store

        from naas_abi.apps.nexus.apps.api.app.main import create_app

        create_app(app)
