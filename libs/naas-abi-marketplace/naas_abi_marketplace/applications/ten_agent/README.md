# TEN Agent: real-time voice calls over ABI agents

Refs [jupyter-naas/abi#1405](https://github.com/jupyter-naas/abi/issues/1405). Exploration module: off unless enabled, not wired into the Nexus call bar.

```
caller audio -> voice engine (TEN Agent) -> POST /api/v1/voice/chat/completions -> ABI agent
             <- speech                   <- speakable sentences only
```

## Recommendation

Build option C first: browser WebRTC to OpenAI Realtime, with ABI as an `ask_abi` function tool served by this module's `/api/v1/voice/chat/completions`. That means a second `VoiceEnginePort` adapter, not more TEN. Keep the TEN adapter for when Nexus needs phone calls (TEN ships Twilio, Telnyx and Plivo SIP examples) or non-OpenAI voices.

The 8 to 40 s delay in today's calls is ABI's time to first token, not the voice transport. Any cascade, TEN included, waits for the LLM before it can speak, so it inherits ABI's latency on every turn. Only a speech-to-speech model in front of ABI separates chit-chat latency from ABI.

## Layout

```
ten_agent/
├── __init__.py                    # ABIModule: Configuration, api() mounts /api/v1/voice
├── domain/
│   ├── ports.py                   # VoiceEnginePort, AgentStreamPort, VoiceSession(Request)
│   └── speech.py                  # agent chunks -> speakable sentences, filler, thread ids
├── adapters/
│   ├── primary/ten_agent__primary_adapter__FastAPI.py       # OpenAI-compatible voice route
│   └── secondary/ten_agent__secondary_adapter__AbiInProcess.py  # AgentStreamPort over the in-process ABI agent
├── integrations/TENAgentIntegration.py   # VoiceEnginePort for TEN, plus TENAgentRuntime (install, launch)
├── tenapp/                        # TEN graph: manifest.json (pinned packages), property.json
├── scripts/
│   ├── run_ten_agent.py           # bring-up for one call
│   ├── ws_latency_probe.py        # time a spoken turn through TEN's websocket transport
│   └── realtime_latency_probe.py  # time OpenAI Realtime, including a tool turn
└── on_load_test.py, *_test.py
```

The domain has no FastAPI, TEN or Nexus imports. An OpenAI Realtime adapter implements `VoiceEnginePort.open_session` by minting an ephemeral client secret and returning a `webrtc` session; the voice route and the speech rules stay as they are.

## Configuration

```yaml
modules:
  - module: naas_abi_marketplace.applications.ten_agent
    enabled: false
    config:
      openai_api_key: "{{ secret.OPENAI_API_KEY }}"
      gateway_base_url: "http://127.0.0.1:9879/api/v1/voice"
      agent: "AbiAgent"
```

Enabling the module is the feature flag: until then nothing is mounted. Other fields (`websocket_port`, `asr_model`, `tts_model`, `tts_voice`, `vad_silence_ms`, `runtime_dir`, `ten_version`) have defaults in `__init__.py`.

Secrets:

- `OPENAI_API_KEY`: TEN's streaming ASR and TTS.
- `TEN_AGENT_GATEWAY_TOKEN`: a Nexus bearer token TEN uses to call the voice route. Read by the bring-up script only.

## The voice route

`POST /api/v1/voice/chat/completions`, OpenAI chat-completions shape, streaming or not. Auth is the Nexus user (or `ABI_API_KEY` without Nexus).

- Streams speakable sentences only. Markdown, fenced tool output, URLs and the hidden chat marker never reach TTS.
- The first tool call becomes one spoken filler ("One moment, let me check.") unless the agent already said something.
- Every turn carries a short voice style instruction, because ABI agents read only the latest user message. The caller's profile goes on the first turn.
- One call keeps one ABI thread through the `X-Voice-Session` header, scoped to the authenticated user.

## Bring-up

```bash
uv run python -m naas_abi_marketplace.applications.ten_agent.scripts.run_ten_agent \
  --dotenv .env --call-id call-1 --gateway-base-url http://127.0.0.1:9879/api/v1/voice
```

The first run installs TEN under `runtime_dir` (about 115 MB, rebuildable): `tman` from the pinned release, the registry packages in `tenapp/manifest.json`, `main_python` and `websocket_server` copied from the pinned TEN tag, and a Python 3.10 venv. Then it launches one TEN app on `ws://127.0.0.1:8765` with logs in `<runtime_dir>/app.log`, credentials redacted. `--prepare-only` stops after the install.

Requirements: macOS or Linux, `git`, `uv`, network access to GitHub and the TEN registry. No Docker, no GPU.

## What was measured

Seconds from end of speech to first audio, home connection, synthetic speech from macOS `say`, Apple M2 Pro, 2026-11-02.

| Setup | First audio | Notes |
|---|---|---|
| Current Nexus call | 8 to 40 | User report |
| TEN cascade, OpenAI only (`gpt-4o-transcribe`, `gpt-4o-mini`, `gpt-4o-mini-tts`), warm | 2.7 to 3.0 | ASR final about 1.0, LLM first token about 0.7, TTS first byte 0.8 to 0.95 |
| TEN through this module's route, fake ABI with a 1.5 s tool call, warm | 1.6 to 2.9 | Filler spoken first. Real ABI adds its own time to first token |
| OpenAI Realtime `gpt-realtime`, `semantic_vad` high eagerness | 1.2 | 0.8 of that is the turn detector waiting |
| OpenAI Realtime `gpt-realtime`, `server_vad` 300 ms | 0.84 to 0.87 | Meets the under 1 s target |
| OpenAI Realtime, tool turn | filler 1.36, tool call 2.27 | Answer about 0.5 after the tool result |
| `gpt-realtime-mini`, `server_vad` 300 ms | 1.0 to 1.16 | Not faster; spoke a filler where no tool was needed |

Barge-in was not measured. TEN's `main_python` interrupts on every ASR result, and Realtime has `interrupt_response`. The route has not run against a real ABI agent yet; the end-to-end runs used a fake `AgentStreamPort`.

## TEN facts that matter

- **Agora is not mandatory.** `websocket_server` takes 16 kHz mono PCM as base64 JSON. It accepts one client per TEN process, so each concurrent call needs its own process.
- **OpenAI-only cascade works** with `OPENAI_API_KEY` alone. Deepgram, ElevenLabs and Cartesia are optional speed-ups.
- **Turn detection model.** `TEN_Turn_Detection` is a 7.6B model served over an OpenAI-compatible API; TEN's example deploys it to an NVIDIA A10. It cannot run on a 16 GB Mac and is not used here.
- **Docker image is `linux/amd64` only** and publishes ports 8000 to 9001. This module runs TEN natively instead (TEN ships macOS arm64 builds).
- **Native macOS needs three fixes**, all in `TENAgentRuntime`: `TEN_PYTHON_LIB_PATH` to an arm64 libpython 3.10, `samplerate>=0.2.1` (0.1.0 loads an Intel libsamplerate on mixed Homebrew Macs), and `httpx[http2]`.
- **Upstream packaging bug:** the registry's `websocket_server` 0.0.2 contains no Python sources (its `package.include` lists no `*.py`), so it is copied from the tag.
- **`openai_llm2_python` logs its `api_key` at info level.** Here that is the caller's Nexus token; the runtime redacts it from `app.log`. Mint a short-lived token per call before any shared deployment.

## Cost per call minute (estimates)

List prices as last known; check current pricing.

- **Realtime (options B and C):** roughly $0.05 to $0.15 per conversation minute, plus ABI's LLM cost on tool turns.
- **TEN cascade, OpenAI only:** about $0.02 per minute for ASR and TTS, plus ABI's LLM on every turn.
- **Agora (if used):** free for the first 10,000 minutes a month.

## Next steps

1. `OpenAIRealtimeIntegration` as a second `VoiceEnginePort`: `open_session` mints an ephemeral key with the instructions, `server_vad` at 300 ms and an `ask_abi` tool. The real key never reaches the browser.
2. A route on this module that returns that session to the browser, and a `realtime-call-engine.ts` behind a flag in Nexus. On `response.function_call_arguments.done` it calls the voice route (non-streaming, `X-Voice-Session` set to the call id), then sends `function_call_output` and `response.create`.
3. Enable the module in dev and measure with `realtime_latency_probe.py` and a real ABI agent.
4. Test barge-in and a long ABI tool run in the browser.
5. Revisit the TEN adapter for SIP telephony; report the `websocket_server` packaging bug and the API key log line upstream.

## Tests

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/ten_agent
```
