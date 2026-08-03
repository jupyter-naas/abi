# Ollama

Local models — chat and embeddings — with **no API keys**, no cloud calls, and
nothing leaving the machine. This is the module a new ABI project enables by
default, so `abi new project` → `abi dev up` works on a fresh laptop without a
single credential.

## What it ships

| Canonical id | Ollama tag | Type | Notes |
|---|---|---|---|
| `qwen-2.5-3b` | `qwen2.5:3b` | chat | Alibaba Qwen2.5 3B, 32k context, tool-capable, ~1.9GB |
| `nomic-embed-text` | `nomic-embed-text` | embedding | 768 dims, 2048-token input limit, ~274MB |

### Context sizes are set explicitly, and one of them is a trap

Ollama allocates a **4096-token context by default**, whatever the model
supports, and truncates past it without an error. So the chat model passes
`num_ctx=32768` to match its advertised window — otherwise `ollama ps` reports
`CONTEXT 4096` and long or tool-heavy conversations lose their head silently.
That costs about 1GB of extra KV cache (2.2GB → 3.2GB resident). On a
constrained machine, drop `num_ctx` in `models/qwen2_5_3b.py` or set
`OLLAMA_CONTEXT_LENGTH`.

The embedding model cannot be fixed the same way. `nomic-embed-text` reports
`nomic-bert.context_length = 2048` and **raising `num_ctx` does not lift it** —
it truncates and returns a perfectly normal-looking vector. Measured: two
~3000-word documents differing only in their last sentence embed to a cosine
similarity of exactly **1.0**, while the same two tails within the limit give
0.868. **Chunk before embedding.** A whole document passed straight in is
indexed by its opening only, and nothing anywhere will tell you. (Nomic's model
card advertises 8192 via RoPE scaling; the Ollama build does not expose it.)

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

### One source of truth

The Nexus API has its own Ollama surface — the status endpoint, the "pull
model" action, and the provider fallback used when no provider is configured.
It reads this module's `defaults.py` and `endpoint.py` rather than keeping its
own copies, which it previously did: it hardcoded `localhost:11434` (wrong
inside a container, wrong under WSL) and `qwen3-vl:2b`, so the UI told users to
install a model the project never pulls, and reported Ollama "offline" while
the engine was talking to it happily.

Both files are import-safe without the `ai-ollama` extra, so the API can read
them whether or not this module is enabled.

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

### Containers on Linux

`abi dev up` runs natively and is unaffected. The containerised deployment
(`abi deploy local`) reaches the host through `host.docker.internal`, supplied
on Linux by `extra_hosts: host-gateway`.

That gives **name resolution only**. A stock Linux Ollama listens on
`127.0.0.1:11434`, so the bridge address resolves and then refuses the
connection — the stack boots and fails on its first model call. The host has to
be bound where the bridge can reach it:

```bash
sudo systemctl edit ollama
#   [Service]
#   Environment="OLLAMA_HOST=0.0.0.0:11434"
sudo systemctl restart ollama
```

`0.0.0.0` exposes Ollama on every interface, so do this only on a trusted
network, or bind the bridge address (`172.17.0.1:11434`) and firewall the port.
Docker Desktop on macOS and Windows needs none of it. When resolution fails
inside a container, `install_hint()` prints exactly this rather than the
useless generic "install from ollama.com".

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

### Known limitation: multi-step chains break as the tool set grows

Driven through the real `Agent` loop (LangGraph, executed tools, scored on what
actually ran), `qwen2.5:3b` handles single-step work well but fails to *chain*
once many tools are bound:

| what was tested | result |
|---|---|
| argument accuracy, incl. a typed `int` parameter | 6/6 |
| routing under a 3,110-char system prompt | 4/4 |
| multi-turn routing with history | 2/2 |
| abstention when no tool applies | 2/2 |
| **two-step chain with 9 tools bound** | **0/4** |

The failure mode is argument cross-contamination: asked for "the budget of the
team Alice belongs to", it calls `find_employee_id` but passes
`{"sparql": "?x foaf:name \\"Alice\\"."}` — a parameter borrowed from a different
tool — which fails schema validation, and the agent then apologises in prose
instead of recovering. It is deterministic, not flaky.

It is tool *count*, not one confusable tool. Same chain, same prompt:

| tools bound | chained correctly |
|---|---|
| 2 (just the chain) | 2/2 |
| 3 | 2/2 |
| 4 (including the tool whose parameter leaks) | 2/2 |
| 9 | 0/2 |

**What this means for the agents actually shipped.** Measured on a freshly
generated project:

| agent | tools bound | sub-agents | prompt |
|---|---|---|---|
| `AbiAgent` | 9 (5 utility + 4 `transfer_to_*`) | 4 | 2,263 chars |
| the scaffolded project agent | 5 | 0 | 555 chars |
| `OllamaAgent` | 5 | 0 | 851 chars |

Note the framework injects 5 utility tools (`get_time_date`, `write_file`,
`read_file`, `list_dir`, `run_terminal`) even when an agent declares
`tools: list = []`.

So the 5-tool agents sit inside the range the 3B handles, but **`AbiAgent` binds
9 — the count at which chaining measurably fails — and delegating through
`transfer_to_*` is inherently multi-step.** Expect the local default to handle
chat and single-step requests through Abi, and to struggle on anything requiring
it to delegate and then use the result.

**Guidance.** A local 3B default is solid for chat, single-step tool use, and
focused agents (~≤5 tools). If you need Abi's supervisor behaviour to be
reliable, point `abi_agent_model` in `config.yaml` at a larger local model or a
cloud provider — that setting exists for exactly this trade-off.

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
