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
| Default embedding model | `nomic-embed-text` (768 dims) |
| AI provider module | `naas_abi_marketplace.ai.ollama` |
| Default agent | `{{ project_name_pascal }}Agent` (in `src/`) |

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

### Swapping the local model

Qwen2.5 3B supports tool calling, so the same model backs plain chat and the
agents that bind tools (`AbiAgent`, `OntologyEngineerAgent`). Any Ollama tag
works without adding a model file — e.g. on a constrained machine:

```bash
ollama pull qwen2.5:1.5b   # ~1GB, also tool-capable
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
