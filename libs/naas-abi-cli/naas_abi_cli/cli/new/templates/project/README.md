# {{ project_name }}

An [ABI](https://github.com/jupyter-naas/abi) project. It runs on
[OpenRouter](https://openrouter.ai) by default — **one API key** serves chat,
the agents, and embeddings, so there is a single credential to manage and
nothing to install locally.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- An [OpenRouter API key](https://openrouter.ai/keys)

Put the key in `.env`:

```bash
OPENROUTER_API_KEY=sk-or-...
```

`uv run abi config validate` prompts for it and writes it there if it's missing.

## Run it

```bash
uv run abi dev up
```

The command prints the URLs it serves. To chat from the terminal instead:

```bash
uv run abi chat
```

## What's configured

`config.yaml` is the dev configuration. Out of the box:

| Setting | Value |
|---|---|
| `global_config.ai_mode` | `cloud` |
| Default chat model | `gemma-4-26b-a4b-it` (Google Gemma 4, 262k context, tool-capable) |
| Default embedding model | `text-embedding-3-small` (1536 dims, 8k input) |
| AI provider module | `naas_abi_marketplace.ai.openrouter` |
| Default agent | `{{ project_name_pascal }}Agent` (in `src/`) |

Gemma 4 26B-A4B is a sparse mixture-of-experts: 26B total parameters but only
~4B active per token, so it prices and responds like a small model while still
reading a 262k context and emitting structured tool calls. Paired with
`text-embedding-3-small` it is the cheapest default that keeps the agents
working; both bill through the same OpenRouter key.

`config.local.yaml` (docker-compose) and `config.remote.yaml` (remote
deployment) use the same two defaults.

### Swapping the chat model

Edit `services.model_registry` in `config.yaml`. Anything the enabled provider
module registers works, for example:

```yaml
model_registry:
  default_chat_model: "gemma-4-31b-it"   # dense sibling, stronger per token
  default_embedding_model: "text-embedding-3-small"
```

`AbiAgent` and `OntologyEngineerAgent` bind tools, and `config.yaml` pins them
to the same default via `abi_agent_model` / `ontology_engineer_model` — change
those too if you want the agents on a different model from plain chat. Whatever
you pick must emit **structured tool calls**; a model that only writes prose
leaves the agents silently answering without ever calling a tool.

### Using another cloud provider

1. Add the API key to `.env`, e.g. `OPENAI_API_KEY=sk-...`
2. Uncomment the provider module in `config.yaml` (e.g. `ai.chatgpt`) and
   replace `SECRET_REF` with a secret reference:

{% raw %}
   ```yaml
   - module: naas_abi_marketplace.ai.chatgpt
     enabled: true
     config:
       openai_api_key: "{{ secret.OPENAI_API_KEY }}"
   ```
{% endraw %}

3. Point `services.model_registry` at that provider's models, e.g.
   `default_chat_model: "gpt-5"`.

Also add the marketplace extra for the module you enabled:

```bash
uv add "naas-abi-marketplace[ai-chatgpt]"
```

> **Why `SECRET_REF` instead of the real snippet in `config.yaml`?** That file
> is rendered as a Jinja template *before* it is parsed as YAML, so a secret
> reference is resolved even inside a `#` comment — a commented-out example
> would make the project prompt for a key you don't have. Hence the placeholder
> there and the real snippet here.

## Running fully locally instead (Ollama)

If you'd rather keep every token on your machine — no keys, no data leaving the
box — swap the provider for [Ollama](https://ollama.com/download):

```bash
uv add "naas-abi-marketplace[ai-ollama]"

# macOS
brew install ollama && brew services start ollama
# Linux, and inside a WSL distro
curl -fsSL https://ollama.com/install.sh | sh

ollama pull qwen2.5:3b         # chat model
ollama pull nomic-embed-text   # embedding model
curl http://localhost:11434/api/tags   # check it's up
```

Then in `config.yaml`: enable the commented `naas_abi_marketplace.ai.ollama`
module, comment out the `ai.openrouter` one, set `global_config.ai_mode` to
`local`, and point the defaults (plus `abi_agent_model` /
`ontology_engineer_model`) at `qwen-2.5-3b` / `nomic-embed-text`.

Two things worth knowing about those local models:

- The chat model asks Ollama for its full 32k context explicitly. Ollama
  otherwise defaults to 4096 whatever the model supports, and truncates
  silently. The full window costs about **1GB extra RAM** (2.2GB → 3.2GB
  resident). On a constrained machine, lower `num_ctx` in the model definition
  or set `OLLAMA_CONTEXT_LENGTH`.
- The embedding model caps at **2048 tokens and drops the rest without an
  error** — and unlike the chat model, `num_ctx` will not lift it. **Chunk your
  documents before embedding them**, or long ones get indexed by their opening
  paragraph alone with nothing to indicate it.

### What a 3B local model can and can't do

Measured through the real agent loop on a fresh project:

| | result |
|---|---|
| single-step tool use (8 tools) | 8/8 correct |
| argument accuracy, incl. typed `int` | 6/6 |
| routing under a long system prompt | 4/4 |
| multi-turn with history | 2/2 |
| **two-step chains with 9 tools bound** | **fails** |

A 3B model is good at chat and one-shot tool use, but multi-step chaining breaks
as the tool set grows — at 2–4 tools it chains fine, at 9 it does not. `Abi`
binds 9 tools and delegates via `transfer_to_*`, so its supervisor behaviour is
the weak spot locally; the scaffolded project agent (5 tools) is comfortable.
If you need Abi to be reliable, point `abi_agent_model` at a bigger local model
or back at a cloud provider.

Any Ollama tag works without adding a model file:

```python
registry.get_chat_model("qwen2.5:1.5b", provider="ollama")
```

Verify a swapped model by binding a real tool and checking `response.tool_calls`
is non-empty; Ollama's `capabilities` list is not a reliable signal. Notably
`qwen2.5-coder` advertises tool support but does not deliver it, and `phi3.5`
has none.

### Linux + Docker (`abi deploy local`)

`uv run abi dev up` runs natively and needs nothing extra. The **containerised**
deployment does, on Linux only, and only when using Ollama.

Ollama's Linux install listens on `127.0.0.1:11434`. The stack reaches the host
through `host.docker.internal`, which resolves to the Docker bridge address —
so the host is found but refuses the connection, and the first chat or
embedding call fails. Bind Ollama where the bridge can reach it:

```bash
sudo systemctl edit ollama
#   [Service]
#   Environment="OLLAMA_HOST=0.0.0.0:11434"
sudo systemctl restart ollama
```

`0.0.0.0` exposes Ollama on every interface — do it only on a trusted network.
To limit the exposure, bind the bridge address instead
(`Environment="OLLAMA_HOST=172.17.0.1:11434"`) and firewall the port. Either
way, verify from a container:

```bash
docker run --rm --add-host host.docker.internal:host-gateway curlimages/curl \
  -s http://host.docker.internal:11434/api/tags
```

Docker Desktop on macOS and Windows needs none of this. To point at a remote
Ollama instead, set `ABI_OLLAMA_BASE_URL`.

### Windows WSL

Works both ways: Ollama installed inside the distro, or the **Ollama Windows
app** on the host. For the Windows app, set `OLLAMA_HOST=0.0.0.0` for it and
restart so the distro can reach it. The host address is auto-detected; if it
isn't, set it explicitly:

```bash
export ABI_OLLAMA_BASE_URL=http://$(ip route show default | awk '{print $3}'):11434
```

## Project layout

```
config.yaml          dev configuration (models, modules, services)
config.local.yaml    docker-compose deployment
config.remote.yaml   remote deployment
src/                 your module — agents, integrations, pipelines, workflows
storage/             local state (triple store, vector store, bus, KV)
```

## Useful commands

```bash
uv run abi dev up            # start the dev stack
uv run abi dev down          # stop it
uv run abi config validate   # check config.yaml resolves
uv run abi chat              # chat in the terminal
uv run abi new agent         # scaffold an agent
uv run abi new integration   # scaffold an integration
```
