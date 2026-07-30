# Ollama

Local models — chat and embeddings — with **no API keys**, no cloud calls, and
nothing leaving the machine. This is the module a new ABI project enables by
default, so `abi new project` → `abi dev up` works on a fresh laptop without a
single credential.

## What it ships

| Canonical id | Ollama tag | Type | Notes |
|---|---|---|---|
| `qwen-2.5-3b` | `qwen2.5:3b` | chat | Alibaba Qwen2.5 3B, 32k context, tool-capable, ~1.9GB |
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

ollama pull qwen2.5:3b
ollama pull nomic-embed-text
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

## Why Qwen2.5 3B

The default chat model serves two jobs: plain conversation *and* the agents that
bind tools (`AbiAgent`, `OntologyEngineerAgent`). One model covers both only if
it emits **structured tool calls**, so that is the bar for this slot. Qwen2.5 3B
clears it at ~1.9GB, which keeps a keyless project to two model pulls.

On multi-tool routing (8 tools, one step, does it pick the *right* one and
abstain when none applies) `qwen2.5:3b` scored 8/8. `qwen2.5:1.5b` (~1GB)
managed 6/8 — it silently answered in prose instead of calling a tool twice — so
treat it as a constrained-hardware fallback, not an equivalent.

### Changing the default

Verify the candidate emits structured tool calls before switching — bind a real
tool and assert `response.tool_calls` is non-empty. **Do not rely on Ollama's
`capabilities` list**, which is not a reliable signal.

Models evaluated for this slot and rejected, so you don't have to re-test them:

| model | why not |
|---|---|
| `qwen2.5-coder:3b` / `:7b` | Advertise `['completion','tools','insert']`, and pick the right function and arguments — but emit them as bare JSON in the message body instead of inside the `<tool_call>` tags their own chat template declares. Ollama only fills the `tool_calls` field when it sees those tags, so LangGraph sees a plain text reply and no tool runs. Measured 0/3 at both sizes vs 3/3 for `qwen2.5:3b`; identical on langchain-ollama 0.3.10 and 1.1.0. Making these work would mean parsing tool calls out of message content ourselves — deliberately not done, since that is Ollama's job and a hand-rolled shim is permanent maintenance. |
| `phi3.5` | Reports `['completion']` only — no tool support at all. |
| `gemma3:4b` | Reports `['completion','vision']` — no tool support. |

If a server isn't reachable at load time the module logs a platform-specific
warning and lets the project boot anyway; the failure surfaces at first model
call rather than blocking startup.
