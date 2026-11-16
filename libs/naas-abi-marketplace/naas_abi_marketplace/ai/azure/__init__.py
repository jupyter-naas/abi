"""Azure AI Foundry (Azure OpenAI): chat and embedding deployments, keyless.

The deployments are named by whoever created them, so they are declared in the
configuration and registered in the model registry from it, instead of one
file per model under ``models/``. Requests authenticate with a Microsoft Entra
ID token by default (managed identity, ``az login``, ...), which is what a
resource with key access disabled requires; an API key is optional. See
``foundry.py`` and ``README.md``.
"""

from typing import Any

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.utils.Logger import logger
from naas_abi_marketplace.ai.azure.foundry import (
    DEFAULT_API_VERSION,
    DEFAULT_TOKEN_SCOPE,
    LOGO_URL,
    PROVIDER,
    AzureAuth,
    AzureChatDeployment,
    AzureEmbeddingDeployment,
    chat_client,
    chat_model,
    embedding_client,
    embedding_model,
    entra_id_token_provider,
)
from pydantic import SecretStr, field_validator, model_validator


class ABIModule(BaseModule):
    name: str = "Azure"
    description: str = (
        "Azure AI Foundry (Azure OpenAI) chat and embedding deployments, "
        "authenticated with Microsoft Entra ID (managed identity, az login) or "
        "an API key."
    )
    logo_url: str = LOGO_URL
    tags: list[str] = ["microsoft", "azure", "azure openai", "ai foundry", "cloud"]
    slug: str = "azure"
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ModelRegistryService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.azure
        enabled: true
        config:
            # https://<resource>.openai.azure.com/ (or .cognitiveservices.azure.com/)
            endpoint: "https://my-resource.openai.azure.com/"
            api_version: "2024-10-21"
            # Optional: a user-assigned managed identity. Without it,
            # DefaultAzureCredential reads AZURE_CLIENT_ID, then uses the
            # system-assigned identity, az login, ...
            managed_identity_client_id: "00000000-0000-0000-0000-000000000000"
            # Optional, only for a resource that accepts keys. Leave it out
            # when key access is disabled: Entra ID is then used.
            # azure_api_key: "{{ secret.AZURE_API_KEY }}"
            chat_deployments:
              - deployment: "gpt-4o-prod"       # deployment name on the resource
                canonical_id: "gpt-4o"          # registry id; defaults to deployment
                model_name: "gpt-4o"            # optional, base model
                context_window: 128000          # optional
            embedding_deployments:
              - deployment: "embeddings-large"
                canonical_id: "text-embedding-3-large"
                model_name: "text-embedding-3-large"
                dimensions: 3072                # optional, text-embedding-3 only
            datastore_path: "azure"
        """

        endpoint: str | None = None
        api_version: str = DEFAULT_API_VERSION
        chat_deployments: list[AzureChatDeployment] = []
        embedding_deployments: list[AzureEmbeddingDeployment] = []

        # Entra ID, the default. The scope is the token audience: change it
        # only for a sovereign cloud.
        managed_identity_client_id: str | None = None
        token_scope: str = DEFAULT_TOKEN_SCOPE

        # Optional: when set, requests send this key instead of a token.
        azure_api_key: str | None = None

        datastore_path: str = "azure"

        @field_validator(
            "endpoint", "managed_identity_client_id", "azure_api_key", mode="before"
        )
        @classmethod
        def _blank_is_unset(cls, value: Any) -> Any:
            # A secret that is not set renders as "": not configured.
            if isinstance(value, str):
                value = value.strip()
                return value or None
            return value

        @model_validator(mode="after")
        def _check_deployments(self) -> "ABIModule.Configuration":
            deployments = [*self.chat_deployments, *self.embedding_deployments]
            missing = [
                d.deployment
                for d in deployments
                if not d.endpoint and not self.endpoint
            ]
            if missing:
                raise ValueError(
                    f"no endpoint for deployment(s) {missing}: set the module's "
                    "endpoint, or the deployment's own."
                )
            seen: set[str] = set()
            duplicates: set[str] = set()
            for d in deployments:
                if d.registry_id in seen:
                    duplicates.add(d.registry_id)
                seen.add(d.registry_id)
            if duplicates:
                raise ValueError(
                    "canonical_id (the deployment name when unset) must be unique "
                    f"across chat and embedding deployments: {sorted(duplicates)}"
                )
            return self

        def endpoint_for(
            self, deployment: AzureChatDeployment | AzureEmbeddingDeployment
        ) -> str:
            endpoint = deployment.endpoint or self.endpoint
            assert endpoint is not None  # guaranteed by _check_deployments
            return endpoint

        def auth(self) -> AzureAuth:
            """The API key when one is configured, an Entra ID token otherwise."""
            if self.azure_api_key:
                return AzureAuth(api_key=SecretStr(self.azure_api_key))
            return AzureAuth(
                token_provider=entra_id_token_provider(
                    self.managed_identity_client_id, self.token_scope
                )
            )

    def on_load(self):
        super().on_load()

        cfg = self.configuration
        if (
            cfg.endpoint is None
            and not cfg.chat_deployments
            and not cfg.embedding_deployments
        ):
            logger.warning(
                "Azure: no endpoint and no deployments configured, no model "
                "registered. Set endpoint and chat_deployments / "
                "embedding_deployments."
            )
            return

        # One credential and one token cache for every deployment.
        auth = cfg.auth()
        registry = self.engine.services.model_registry

        for chat in cfg.chat_deployments:
            registry.register(
                chat.registry_id,
                chat_model(
                    chat,
                    endpoint=cfg.endpoint_for(chat),
                    api_version=cfg.api_version,
                    auth=auth,
                ),
            )
        for emb in cfg.embedding_deployments:
            registry.register(
                emb.registry_id,
                embedding_model(
                    emb,
                    endpoint=cfg.endpoint_for(emb),
                    api_version=cfg.api_version,
                    auth=auth,
                ),
            )

        # Any other deployment of the module's resource, by its name:
        # get_chat_model("<deployment>", provider="azure").
        endpoint = cfg.endpoint
        if endpoint is not None:
            api_version = cfg.api_version

            def azure_chat_factory(deployment: str) -> AzureChatOpenAI:
                return chat_client(
                    endpoint=endpoint,
                    api_version=api_version,
                    deployment=deployment,
                    auth=auth,
                )

            def azure_embedding_factory(deployment: str) -> AzureOpenAIEmbeddings:
                return embedding_client(
                    endpoint=endpoint,
                    api_version=api_version,
                    deployment=deployment,
                    auth=auth,
                )

            registry.register_chat_provider(PROVIDER, azure_chat_factory)
            registry.register_embedding_provider(PROVIDER, azure_embedding_factory)

        logger.info(
            "Azure: registered {} chat and {} embedding deployment(s), auth={}",
            len(cfg.chat_deployments),
            len(cfg.embedding_deployments),
            auth.mode,
        )
