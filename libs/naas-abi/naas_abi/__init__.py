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
from pydantic import BaseModel, ConfigDict, Field


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
        # Expose ABI triple store to Nexus graph routes.
        app.state.triple_store = self.engine.services.triple_store

        from naas_abi.apps.nexus.apps.api.app.main import create_app

        create_app(app)
