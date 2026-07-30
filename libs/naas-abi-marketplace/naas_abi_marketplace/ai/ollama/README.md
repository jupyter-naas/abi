# Ollama

Local models — chat and embeddings — with **no API keys**, no cloud calls, and
nothing leaving the machine. This is the module a new ABI project enables by
default, so `abi new project` → `abi dev up` works on a fresh laptop without a
single credential.

## What it ships

| Canonical id | Ollama tag | Type | Notes |
|---|---|---|---|
| `qwen-2.5-coder-3b` | `qwen2.5-coder:3b` | chat | **default chat model** — code-tuned, 32k context, ~1.9GB |
| `qwen-2.5-3b` | `qwen2.5:3b` | chat | for tool-using agents — general Qwen2.5, 32k context, ~1.9GB |
| `nomic-embed-text` | `nomic-embed-text` | embedding | 768 dims, 8k context, ~274MB |

It also registers **provider factories** for `ollama`, so any tag works without
shipping a model file for it:

```python
registry.get_chat_model("qwen2.5:1.5b", provider="ollama")
registry.get_embedding_model("embeddinggemma", provider="ollama")
```

## Prerequisites

Install Ollama and pull the two default models:

```bash
# macOS
brew install ollama && brew services start ollama
# Linux (and inside a WSL distro)
curl -fsSL https://ollama.com/install.sh | sh

ollama pull qwen2.5-coder:3b   # default chat model
ollama pull qwen2.5:3b         # tool-using agents
ollama pull nomic-embed-text   # embeddings
```

## Configuration

```yaml
- module: naas_abi_marketplace.ai.ollama
  enabled: true
```

That's the whole thing — the endpoint is auto-detected. To override:

```yaml
- module: naas_abi_marketplace.ai.ollama
  enabled: true
  config:
    base_url: "http://localhost:11434"
    probe_on_load: true   # set false to skip detection and trust base_url
```

Environment variables, checked in this order and overridden by an explicit
`base_url`:

| Variable | Purpose |
|---|---|
| `ABI_OLLAMA_BASE_URL` | ABI-specific override; doesn't disturb your `ollama` CLI |
| `OLLAMA_HOST` | Ollama's own variable; accepts `11434`, `host`, `host:port` or a full URL |

## Platform support

Endpoint resolution is a platform question, not a config question, so the
module builds an ordered candidate list and uses the first that answers
`GET /api/tags`.

| Platform | Behaviour |
|---|---|
| **macOS** (arm64 + Intel) | `localhost`. Binary also looked up in the `.app` bundle and Homebrew paths. |
| **Linux** (x86_64 + arm64) | `localhost`. Never spawns a second server — a systemd-managed `ollama.service` already owns the port. |
| **Windows WSL** | Both topologies. Ollama *inside* the distro wins on `localhost`; otherwise the **Ollama Windows app** on the host is found via the `/etc/resolv.conf` nameserver (NAT networking) or `localhost` (`networkingMode=mirrored`). |

Native Windows is not supported — use WSL, consistent with the rest of the ABI
dev stack.

For the WSL + Windows-app case, the Windows-side server must accept
connections from the VM: set `OLLAMA_HOST=0.0.0.0` for the Windows app and
restart it. If auto-detection still misses, point ABI at the host directly:

```bash
export ABI_OLLAMA_BASE_URL=http://$(ip route show default | awk '{print $3}'):11434
```

## Why two chat models

Qwen2.5-Coder is the default because most of what people ask an ABI project to
do is write code — pipelines, workflows, SPARQL, ontologies. But it **cannot
drive a tool-using agent**, so `AbiAgent` and `OntologyEngineerAgent` use the
general Qwen2.5 instead.

That is not for lack of a capability flag. `ollama show` reports
`['completion', 'tools', 'insert']` for the coder model, and the model does pick
the right function and arguments — it just emits them as bare JSON in the
message body instead of wrapping them in the `<tool_call>` tags its own chat
template declares. Ollama only fills the structured `tool_calls` field when it
sees those tags, so LangChain and LangGraph see a plain text reply and no tool
is ever invoked:

```
qwen2.5-coder:3b   tool_calls=False  content='{"name": "get_weather", "arguments": {"city": "Paris"}}'
qwen2.5:3b         tool_calls=True   [{"id": "call_…", "function": {"name": "get_weather", …}}]
```

Measured over identical prompts and tool bindings, via `bind_tools` — the path
agents actually use:

| model | size | structured tool calls |
|---|---|---|
| `qwen2.5-coder:7b` | 4.7GB | 0/3 |
| `qwen2.5-coder:3b` | 1.9GB | 0/3 |
| `qwen2.5:3b` | 1.9GB | 3/3 |

The 7B doing no better than the 3B is why the coder ships at 3B: the extra
2.8GB buys nothing here. Both chat models being the same size class keeps the
total download reasonable.

**If you change `default_chat_model`, check the model advertises `tools` *and*
actually emits them** — the flag alone is not enough. `qwen2.5:1.5b` (~1GB) is a
verified-lighter tool-capable option.

If a server isn't reachable at load time the module logs a platform-specific
warning and lets the project boot anyway; the failure surfaces at first model
call rather than blocking startup.
