# {{ project_name }}

An [ABI](https://github.com/jupyter-naas/abi) project. It runs **locally by
default** — models are served by Ollama on your machine, so there are **no API
keys to configure** and no data leaves the box.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- [Ollama](https://ollama.com/download) — serves the default models

Install Ollama and pull the two default models (~2.2GB total, one time):

```bash
# macOS
brew install ollama && brew services start ollama
# Linux, and inside a WSL distro
curl -fsSL https://ollama.com/install.sh | sh

ollama pull qwen2.5:3b         # default chat model
ollama pull nomic-embed-text   # default embedding model
```

Check it's up:

```bash
curl http://localhost:11434/api/tags
```

## Run it

```bash
uv run abi dev up
```

That's it — no keys, no extra setup. The command prints the URLs it serves.

To chat from the terminal instead:

```bash
uv run abi chat
```

## What's configured

`config.yaml` is the dev configuration. Out of the box:

| Setting | Value |
|---|---|
| `global_config.ai_mode` | `local` |
| Default chat model | `qwen-2.5-3b` (Alibaba Qwen2.5 3B, 32k context, tool-capable) |
| Default embedding model | `nomic-embed-text` (768 dims, 2048-token input limit) |
| AI provider module | `naas_abi_marketplace.ai.ollama` |
| Default agent | `{{ project_name_pascal }}Agent` (in `src/`) |

Two things worth knowing about those numbers:

- The chat model asks Ollama for its full 32k context explicitly. Ollama
  otherwise defaults to 4096 whatever the model supports, and truncates
  silently. The full window costs about **1GB extra RAM** (2.2GB → 3.2GB
  resident). On a constrained machine, lower `num_ctx` in the model definition
  or set `OLLAMA_CONTEXT_LENGTH`.
- The embedding model caps at **2048 tokens and drops the rest without an
  error** — and unlike the chat model, `num_ctx` will not lift it. **Chunk your
  documents before embedding them**, or long ones get indexed by their opening
  paragraph alone with nothing to indicate it.

### Linux + Docker (`abi deploy local`)

`uv run abi dev up` runs natively and needs nothing extra. The **containerised**
deployment does, on Linux only.

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

### Using a cloud model instead

Local models are the default, not a limitation. To use a cloud provider:

1. Add the API key to `.env`, e.g. `OPENAI_API_KEY=sk-...`
2. Uncomment the provider module in `config.yaml` (`ai.chatgpt` or
   `ai.openrouter`) and replace `SECRET_REF` with a secret reference:

{% raw %}
   ```yaml
   - module: naas_abi_marketplace.ai.chatgpt
     enabled: true
     config:
       openai_api_key: "{{ secret.OPENAI_API_KEY }}"
   ```
{% endraw %}

3. Set `global_config.ai_mode` to `cloud`.
4. Point `services.model_registry` at that provider's models, e.g.
   `default_chat_model: "gpt-5"` and
   `default_embedding_model: "text-embedding-3-large"`.

Also add the marketplace extra for the module you enabled:

```bash
uv add "naas-abi-marketplace[ai-chatgpt]"
```

> **Why `SECRET_REF` instead of the real snippet in `config.yaml`?** That file
> is rendered as a Jinja template *before* it is parsed as YAML, so a secret
> reference is resolved even inside a `#` comment — a commented-out example
> would make the project prompt for a key you don't have. Hence the placeholder
> there and the real snippet here.

### What the local default can and can't do

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

If you need Abi to be reliable, point `abi_agent_model` in `config.yaml` at a
bigger local model or a cloud provider.

### Swapping the local model

Qwen2.5 3B supports tool calling, so the same model backs plain chat and the
agents that bind tools (`AbiAgent`, `OntologyEngineerAgent`). Any Ollama tag
works without adding a model file — e.g. on a constrained machine:

```bash
ollama pull qwen2.5:1.5b   # ~1GB, but weaker at tool routing (6/8 vs 8/8)
```

```python
registry.get_chat_model("qwen2.5:1.5b", provider="ollama")
```

To change the defaults project-wide, edit `services.model_registry` in
`config.yaml`.

If you swap the chat model, pick one that emits **structured tool calls** —
`AbiAgent` and `OntologyEngineerAgent` bind tools and silently stop working
otherwise (they just answer in prose and never call the tool). Verify by binding
a real tool and checking `response.tool_calls` is non-empty; Ollama's
`capabilities` list is not a reliable signal. Notably `qwen2.5-coder` advertises
tool support but does not deliver it, and `phi3.5` has none.

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
