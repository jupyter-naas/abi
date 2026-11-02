# ten_agent: AGENTS.md

> Scope: `applications/ten_agent/`. Real-time voice calls over ABI agents. See `README.md` for measurements and the recommendation.

## Rules for this module

- `domain/` imports nothing from FastAPI, TEN or Nexus. New engines implement `VoiceEnginePort`; new agent backends implement `AgentStreamPort`.
- Nothing the voice route returns is meant to be read: every change to `domain/speech.py` keeps markdown, tool output, URLs and the chat marker out of TTS. Pin each rule with a test.
- Credentials live in `VoiceSession.env` only. `tenapp/property.json` keeps every secret and per-call value as an `${env:...}` placeholder.
- `runtime_dir` is throwaway. Anything that must survive goes through ABI services, not there.
- Do not enable the module in any shipped config.

## Checklist

### Services

- [x] Credentials via `secret` (`{{ secret.OPENAI_API_KEY }}`, `TEN_AGENT_GATEWAY_TOKEN` through the secret service); none inline
- [x] No persistent state on local disk (`runtime_dir` is rebuildable)
- [ ] Models via `model_registry`: the ASR and TTS ids are vendor settings in `Configuration`; the ABI agent picks its own chat model

### Verification

- [x] Unit tests pin the speech rules, the thread scoping and the graph rendering
- [x] Bring-up run from an empty `runtime_dir`, and a spoken turn through TEN into the voice route (fake agent stream)
- [ ] Measured against a real ABI agent
- [ ] Barge-in measured
- [x] ruff and mypy clean on this package
