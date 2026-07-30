# Ollama

Local models — chat and embeddings — with **no API keys**, no cloud calls, and
nothing leaving the machine. This is the module a new ABI project enables by
default, so `abi new project` → `abi dev up` works on a fresh laptop without a
single credential.

## What it ships

| Canonical id | Ollama tag | Type | Notes |
|---|---|---|---|
| `phi-3.5` | `phi3.5` | chat | Microsoft Phi-3.5 Mini, 3.8B, 128k context, ~2.2GB |
| `nomic-embed-text` | `nomic-embed-text` | embedding | 768 dims, 8k context, ~274MB |

It also registers **provider factories** for `ollama`, so any tag works without
shipping a model file for it:

```python
registry.get_chat_model("llama3.2", provider="ollama")
registry.get_embedding_model("embeddinggemma", provider="ollama")
```

## Prerequisites

Install Ollama and pull the two default models:

```bash
# macOS
brew install ollama && brew services start ollama
# Linux (and inside a WSL distro)
curl -fsSL https://ollama.com/install.sh | sh

ollama pull phi3.5
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

## Known limitation: Phi-3.5 has no tool calling

Ollama reports Phi-3.5's capabilities as `completion` only. That's fine for
conversational agents — the scaffolded project agent binds no tools — but an
agent that needs tools must use a tool-capable local model:

```bash
ollama pull llama3.2
```

```python
registry.get_chat_model("llama3.2", provider="ollama")
```

If a server isn't reachable at load time the module logs a platform-specific
warning and lets the project boot anyway; the failure surfaces at first model
call rather than blocking startup.
