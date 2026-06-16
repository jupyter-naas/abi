# AI Provider Modules — AGENTS.md

> Scope: `libs/naas-abi-marketplace/naas_abi_marketplace/ai/`. Quick index for LLM provider modules. See the [marketplace master guide](../../AGENTS.md) for module shape, conventions, and how to extend.

## What's here

Each subdirectory is a marketplace module wrapping an LLM provider. Every module:

- Declares `services=[ObjectStorageService, ModelRegistryService]` in its `ABIModule.dependencies`.
- Exposes a `Configuration` requiring at least the provider's API key.
- Auto-registers everything under `models/*.py` into the `ModelRegistryService` via `BaseModule.on_load()`.
- Ships an `agents/<Name>Agent.py` bound to a sensible default model.

## Provider index

| Module | Models | Top agent | Notes |
|---|---:|---|---|
| [`bedrock/`](bedrock/) | 8 | `BedrockAgent` | AWS Bedrock — multi-vendor access (Anthropic, Meta, Mistral, Amazon) via AWS |
| [`chatgpt/`](chatgpt/) | 12 | `ChatGPTAgent` | OpenAI: GPT-4o, GPT-4.1 family, o3 reasoning models |
| [`claude/`](claude/) | 7 | `ClaudeAgent` | Anthropic: Claude 4 Opus/Sonnet (+ Thinking), Haiku 4.5, Sonnet 3.7 |
| [`deepseek/`](deepseek/) | 1 | `DeepSeekAgent` | Cost-efficient, strong on code |
| [`gemini/`](gemini/) | 1 | `GeminiAgent` | Google multimodal |
| [`gemma/`](gemma/) | 1 | `GemmaAgent` | Google open-weights |
| [`grok/`](grok/) | 1 | `GrokAgent` | xAI — high reasoning, real-time access |
| [`llama/`](llama/) | 1 | `LlamaAgent` | Meta open-source — local / privacy deployments |
| [`mistral/`](mistral/) | 3 | `MistralAgent` | Code + math focus |
| [`perplexity/`](perplexity/) | 6 | `PerplexityAgent` | Web-search-grounded answering |
| [`qwen/`](qwen/) | 1 | `QwenAgent` | Multilingual, efficient |

Total: **11 providers, 42 models**.

## Module shape (recap)

```
ai/<provider>/
├── __init__.py        # ABIModule + Configuration (API key field)
├── agents/
│   ├── <Provider>Agent.py
│   └── <Provider>Agent_test.py
├── models/            # one file per concrete model
│   └── <model_id>.py  # exports CANONICAL_ID, MODEL_ID, PROVIDER, model
├── ontologies/
└── on_load_test.py    # smoke test for ABIModule.on_load()
```

## Model file convention

Each file under `models/` exports a `ModelDefinition` subclass:

```python
class ClaudeHaiku45Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_HAIKU_4_5
    MODEL_ID = "claude-haiku-4-5-20251001"
    PROVIDER = ModelProvider.ANTHROPIC

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatAnthropic(model_name=MODEL_ID, ...),
    )
```

`BaseModule.on_load()` scans this directory and calls `ModelRegistryService.register(canonical_id, model)` for each — no manual wiring.

## Configuration example

```yaml
modules:
  - module: naas_abi_marketplace.ai.anthropic
    enabled: true
    config:
      anthropic_api_key: "{{ secret.ANTHROPIC_API_KEY }}"
      datastore_path: "claude"
```

## Adding a new model to an existing provider

1. Drop `models/<model_id>.py` exposing `CANONICAL_ID`, `MODEL_ID`, `PROVIDER`, and a `model: ChatModel` instance.
2. Add the canonical id to `naas_abi_core.models.Model.CanonicalModelId` if it's not already there.
3. Done — `on_load()` picks it up automatically.

## Adding a new provider

1. Create `ai/<provider>/` with the module shape above.
2. `Configuration` must include the provider's API key field.
3. Set `dependencies.services = [ObjectStorageService, ModelRegistryService]`.
4. Add at least one model file and a `<Provider>Agent.py`.
5. Add `<Provider>Agent_test.py` and `on_load_test.py`.
6. Add a `[ai-<provider>]` optional-extra group in the package `pyproject.toml`.

## Tests

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/ai
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/ai/anthropic
```
