# naas-aia

AIA — a local AI assistant that helps you build your own AI system. SOUL identity + DuckDuckGo search. Runs 100% on your machine via Ollama. No API keys. No data leaves unless you choose.

## Requirements

- [Ollama](https://ollama.ai) — install and create the AIA model (see below)
- Python 3.10+

## Setup

Create the `aia` model so the default `aia` command works:

```bash
cd libs/naas-aia
ollama pull qwen2.5-coder:7b
ollama create aia -f Modelfile.aia
```

Or use any other Ollama model directly: `aia qwen2.5-coder:7b`.

## Install

```bash
uv add naas-aia
# or from repo
cd libs/naas-aia && uv sync
```

## Run

```bash
# Standalone
aia
aia qwen2.5-coder:7b   # specify Ollama model

# Via ABI CLI (when ABI is installed)
abi call aia
```

## Web search

Say `cherche <query>` or `search <query>` to trigger a real DuckDuckGo search. Results are injected into the conversation.

```
>>> cherche NaasAI
[searching: NaasAI]
...
>>> salut
Salut! Comment puis-je vous aider ?
```

**Commands:** `/soul` — show SOUL.md | `/stop` — exit

## SOUL

AIA's identity and behavior are defined in SOUL.md. Edit it to change who AIA is and how it behaves. The file ships with the package; your edits persist across sessions when you customize a local copy.

## Python API

```python
from naas_aia import load_soul, run

soul = load_soul()   # SOUL.md content
run(model="aia")     # start chat loop
```

## AIA + ABI

- **AIA** — local, private, your machine. `aia` or `abi call aia`.
- **ABI** — platform, networked, knowledge graphs & agents. `abi chat`.

AIA helps you build ABI. One private, one connected.
