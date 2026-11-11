"""Azure AI Foundry (Azure OpenAI) deployments as ABI chat and embedding models.

An Azure OpenAI resource serves *deployments*: names an operator chose, each
bound to one base model (``gpt-4o``, ``text-embedding-3-large``, ...). The
names differ from one resource to the next, so this module does not ship one
model file per model like the other providers. The deployments are listed in
the module configuration and registered from it (``ABIModule.on_load``).

Authentication: resources are often deployed with key access disabled
(``disableLocalAuth``), so the default is a Microsoft Entra ID token from
``azure.identity.DefaultAzureCredential`` (managed identity, workload
identity, environment service principal, ``az login``, ...). The caller needs
the "Cognitive Services OpenAI User" role on the resource and nothing else.
An API key is still accepted for resources that allow it.

Nothing here touches the network: building a credential, a token provider or
a client is offline. The first token is requested on the first model call.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from naas_abi_core.models.Model import ChatModel, EmbeddingModel
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

# Registry provider name for every model this module registers. A raw string:
# the registry accepts any provider name, and the marketplace must not need a
# newer naas-abi-core release for it.
PROVIDER = "azure"

# Latest GA data-plane version at the time of writing. Reasoning models (the
# o-series, gpt-5) need a newer, preview one: set ``api_version`` in the config.
DEFAULT_API_VERSION = "2024-10-21"

# The audience Azure OpenAI accepts tokens for (public cloud). Sovereign clouds
# use their own, e.g. https://cognitiveservices.azure.us/.default.
DEFAULT_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

LOGO_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/azure.png"

TokenProvider = Callable[[], str]


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class _Deployment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deployment: str
    """Deployment name on the Azure resource: what requests are routed on."""

    canonical_id: str | None = None
    """Id the model is registered under in the model registry, the one callers
    and ``default_chat_model`` / ``default_embedding_model`` use. Defaults to
    the deployment name."""

    model_name: str | None = None
    """Base model of the deployment (``gpt-4o``, ``text-embedding-3-large``).
    Optional: tracing, token counting and display."""

    endpoint: str | None = None
    """This deployment's resource, when it is not the module's ``endpoint``
    (a model only offered in another region, say)."""

    name: str | None = None
    description: str | None = None

    @field_validator("deployment")
    @classmethod
    def _deployment_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("deployment must not be empty")
        return value

    @field_validator("canonical_id", "model_name", "endpoint", mode="before")
    @classmethod
    def _optional_blank_is_none(cls, value: Any) -> Any:
        return _blank_to_none(value)

    @property
    def registry_id(self) -> str:
        return self.canonical_id or self.deployment

    def display_name(self) -> str:
        return self.name or self.model_name or self.deployment


class AzureChatDeployment(_Deployment):
    context_window: int | None = None
    """Advertised context length in tokens (registry metadata)."""

    temperature: float | None = None
    """Sent only when set. Reasoning models (o-series, gpt-5) refuse any value
    but their default, so none is sent by default."""


class AzureEmbeddingDeployment(_Deployment):
    dimensions: int | None = None
    """Output size. When set it is recorded in the registry *and* sent to the
    API, which shortens the vectors: text-embedding-3 deployments only, leave
    it unset for text-embedding-ada-002."""


@dataclass(frozen=True)
class AzureAuth:
    """How every request of the module authenticates: an API key, or a
    callable returning an Entra ID bearer token (refreshed and cached by
    ``azure.identity``)."""

    api_key: SecretStr | None = None
    token_provider: TokenProvider | None = None

    def __post_init__(self) -> None:
        if (self.api_key is None) == (self.token_provider is None):
            raise ValueError("AzureAuth takes exactly one of api_key, token_provider")

    @property
    def mode(self) -> str:
        return "api_key" if self.api_key is not None else "entra_id"

    def client_kwargs(self) -> dict[str, Any]:
        if self.token_provider is not None:
            # ``api_key=None`` explicitly: otherwise langchain falls back to the
            # AZURE_OPENAI_API_KEY / OPENAI_API_KEY environment variables, and
            # an unrelated OpenAI key would sit in the Azure client.
            return {"azure_ad_token_provider": self.token_provider, "api_key": None}
        return {"api_key": self.api_key}


def entra_id_token_provider(
    managed_identity_client_id: str | None = None,
    scope: str = DEFAULT_TOKEN_SCOPE,
) -> TokenProvider:
    """A bearer-token callable from ``DefaultAzureCredential``.

    ``managed_identity_client_id`` selects a user-assigned managed identity;
    without it the credential reads ``AZURE_CLIENT_ID`` and otherwise uses the
    system-assigned identity (or the next credential in the chain).
    """
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    except ImportError as exc:
        raise ImportError(
            "Keyless Azure AI Foundry access needs azure-identity. Install it with "
            '`uv add "naas-abi-marketplace[ai-azure]"`, or set azure_api_key '
            "for a resource that accepts keys."
        ) from exc

    kwargs: dict[str, Any] = {}
    # Passed only when set: an explicit None would hide AZURE_CLIENT_ID.
    if managed_identity_client_id:
        kwargs["managed_identity_client_id"] = managed_identity_client_id
    credential = DefaultAzureCredential(**kwargs)
    return get_bearer_token_provider(credential, scope)


def chat_client(
    *,
    endpoint: str,
    api_version: str,
    deployment: str,
    auth: AzureAuth,
    model_name: str | None = None,
    temperature: float | None = None,
) -> AzureChatOpenAI:
    kwargs: dict[str, Any] = {
        "azure_endpoint": endpoint,
        "azure_deployment": deployment,
        "api_version": api_version,
        **auth.client_kwargs(),
    }
    if model_name:
        kwargs["model"] = model_name
    if temperature is not None:
        kwargs["temperature"] = temperature
    return AzureChatOpenAI(**kwargs)


def embedding_client(
    *,
    endpoint: str,
    api_version: str,
    deployment: str,
    auth: AzureAuth,
    model_name: str | None = None,
    dimensions: int | None = None,
) -> AzureOpenAIEmbeddings:
    kwargs: dict[str, Any] = {
        "azure_endpoint": endpoint,
        "azure_deployment": deployment,
        "api_version": api_version,
        **auth.client_kwargs(),
    }
    if model_name:
        kwargs["model"] = model_name
    if dimensions is not None:
        kwargs["dimensions"] = dimensions
    return AzureOpenAIEmbeddings(**kwargs)


def chat_model(
    deployment: AzureChatDeployment,
    *,
    endpoint: str,
    api_version: str,
    auth: AzureAuth,
) -> ChatModel:
    return ChatModel(
        model_id=deployment.deployment,
        provider=PROVIDER,
        model=chat_client(
            endpoint=deployment.endpoint or endpoint,
            api_version=api_version,
            deployment=deployment.deployment,
            auth=auth,
            model_name=deployment.model_name,
            temperature=deployment.temperature,
        ),
        context_window=deployment.context_window,
        name=deployment.display_name(),
        description=deployment.description
        or f"Azure AI Foundry chat deployment {deployment.deployment!r}.",
        image=LOGO_URL,
    )


def embedding_model(
    deployment: AzureEmbeddingDeployment,
    *,
    endpoint: str,
    api_version: str,
    auth: AzureAuth,
) -> EmbeddingModel:
    return EmbeddingModel(
        model_id=deployment.deployment,
        provider=PROVIDER,
        model=embedding_client(
            endpoint=deployment.endpoint or endpoint,
            api_version=api_version,
            deployment=deployment.deployment,
            auth=auth,
            model_name=deployment.model_name,
            dimensions=deployment.dimensions,
        ),
        dimensions=deployment.dimensions,
        name=deployment.display_name(),
        description=deployment.description
        or f"Azure AI Foundry embedding deployment {deployment.deployment!r}.",
        image=LOGO_URL,
    )
