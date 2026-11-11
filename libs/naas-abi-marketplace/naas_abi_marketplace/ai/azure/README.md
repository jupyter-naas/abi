# Azure AI Foundry

Chat and embedding deployments of an Azure AI Foundry (Azure OpenAI) resource,
registered in the model registry, **with no API key**. Requests carry a
Microsoft Entra ID token, which is the only way in when the resource has key
access disabled (`disableLocalAuth: true`).

## What it registers

Azure serves *deployments*: names chosen by whoever deployed the model, each
bound to one base model. Since the names differ from one resource to the next,
this module ships no `models/` files. Every deployment listed in the
configuration is registered under its `canonical_id` (the deployment name when
unset), with provider `azure`:

| Config entry | Registered as | Client |
|---|---|---|
| `chat_deployments[]` | `ChatModel` | `langchain_openai.AzureChatOpenAI` |
| `embedding_deployments[]` | `EmbeddingModel` | `langchain_openai.AzureOpenAIEmbeddings` |

Point the engine defaults at them like any other model:

```yaml
services:
  model_registry:
    default_chat_model: "gpt-4o"
    default_embedding_model: "text-embedding-3-large"
```

With an `endpoint`, it also registers provider factories for `azure`, so any
other deployment of that resource is reachable by name:

```python
registry.get_chat_model("my-other-deployment", provider="azure")
registry.get_embedding_model("my-embedder", provider="azure")
```

## Configuration

```yaml
modules:
  - module: naas_abi_marketplace.ai.azure
    enabled: true
    config:
      endpoint: "https://my-resource.openai.azure.com/"
      api_version: "2024-10-21"
      # managed_identity_client_id: "<client id of a user-assigned identity>"
      chat_deployments:
        - deployment: "gpt-4o-prod"      # deployment name on the resource
          canonical_id: "gpt-4o"         # registry id, defaults to the deployment name
          model_name: "gpt-4o"           # optional: base model (tracing, display)
          context_window: 128000         # optional
          # temperature: 0               # optional, sent only when set
      embedding_deployments:
        - deployment: "embeddings-large"
          canonical_id: "text-embedding-3-large"
          model_name: "text-embedding-3-large"
          dimensions: 3072               # optional, text-embedding-3 only
```

| Key | Default | Notes |
|---|---|---|
| `endpoint` | none | `https://<resource>.openai.azure.com/` or `https://<resource>.cognitiveservices.azure.com/`. Required as soon as a deployment is listed, unless each deployment sets its own. |
| `api_version` | `2024-10-21` | Latest GA version. Reasoning models (o-series, gpt-5) need a newer preview version, e.g. `2025-04-01-preview`. |
| `chat_deployments` | `[]` | `deployment` (required), `canonical_id`, `model_name`, `endpoint`, `name`, `description`, `context_window`, `temperature`. |
| `embedding_deployments` | `[]` | `deployment` (required), `canonical_id`, `model_name`, `endpoint`, `name`, `description`, `dimensions`. |
| `managed_identity_client_id` | none | A user-assigned managed identity. Without it, `AZURE_CLIENT_ID` is read, then the system-assigned identity is used. |
| `token_scope` | `https://cognitiveservices.azure.com/.default` | Change only for a sovereign cloud (e.g. `https://cognitiveservices.azure.us/.default`). |
| `azure_api_key` | none | Optional. When set, requests send this key and no token is requested. |

Notes:

- `canonical_id` must be unique across both lists: a chat and an embedding
  model cannot share one id.
- A deployment's own `endpoint` overrides the module's, for a model that is
  only available on a resource in another region.
- `temperature` is not sent unless set: reasoning models refuse anything but
  their default.
- `dimensions` is sent to the API, which shortens the vectors. Only
  text-embedding-3 models accept it; leave it unset for
  `text-embedding-ada-002`.
- A blank value (an unset `{{ secret.X }}`) counts as not set.

## Authentication

Without `azure_api_key`, every client gets
`azure_ad_token_provider=get_bearer_token_provider(DefaultAzureCredential(), token_scope)`.
One credential is built per module load and shared by every deployment, so the
token is cached and refreshed once for all of them. Building it opens no
connection: the first token is requested on the first model call.

`DefaultAzureCredential` tries, in order, environment service principal
variables, workload identity, managed identity, then developer sign-ins
(`az login`, `azd auth login`, Azure PowerShell). So the same configuration
works on an Azure VM, App Service, Container Apps or AKS (managed or workload
identity), and on a laptop after `az login`.

The identity needs one role on the Azure OpenAI / AI Foundry resource:
**Cognitive Services OpenAI User** (data-plane inference, nothing else).

```bash
az role assignment create \
  --assignee "<principal id of the managed identity or user>" \
  --role "Cognitive Services OpenAI User" \
  --scope "<resource id of the Azure OpenAI / AI Foundry resource>"
```

With `azure_api_key` set, the key is sent (`api-key` header) and
`azure-identity` is not used at all.

## Install

```bash
uv add "naas-abi-marketplace[ai-azure]"
```

The extra adds `azure-identity`. `langchain-openai` already comes with
`naas-abi-core`. A key-only setup does not need the extra.

## Tests

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/ai/azure
```

No network and no Azure account: `azure.identity` is replaced by fakes and
HTTP requests are answered in-process, so the tests check the request that
would reach Azure (URL, deployment, `Authorization: Bearer <token>`, no key).
