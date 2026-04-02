# ADR: OpenRouter as Unified Model Access Layer

- Status: Accepted
- Date: 2025-11-06

## Context

ABI supported multiple LLM providers (OpenAI, Claude, Gemini, Mistral, Grok, etc.) through per-provider integrations. Each integration had its own API key management, client initialization, and model enumeration. This created:

- Duplicated authentication and retry logic across providers.
- No fallback when a provider was unavailable or rate-limited.
- Inconsistent model naming across providers made it hard to compare or switch models.
- Developers needed multiple API keys and accounts to run a full ABI stack.

## Decision

Introduce **OpenRouter** as a unified model access layer via a `ChatOpenRouter` class that wraps the OpenRouter API. Key behaviors:

- A single `OPENROUTER_API_KEY` grants access to models from all supported providers.
- `ChatOpenRouter` is accepted anywhere a `ChatModel` is expected; agents that were provider-specific are migrated to accept `ChatModel` generically.
- OpenRouter is used as a fallback when provider-specific keys are absent.
- Model enumeration is fetched from the OpenRouter API at startup, making all available models (across all providers) visible without hardcoding model lists.
- Embedding requests also route through OpenRouter when the provider key is not configured directly.

## Consequences

### Positive
- Single API key for all providers simplifies deployment configuration.
- Automatic fallback to OpenRouter when provider keys are missing, enabling partial deployments.
- Model list stays current without code changes as providers release new models.

### Tradeoffs
- OpenRouter is a third-party proxy; its availability and latency add a dependency outside ABI's control.
- Routing through OpenRouter may increase per-token cost vs. direct provider access.
- Some provider-specific features (system prompt caching, tool use variants) may not be fully supported through the OpenRouter proxy.
