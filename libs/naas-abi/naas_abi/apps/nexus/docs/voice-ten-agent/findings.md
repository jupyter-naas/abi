# TEN Agent as the Nexus voice engine: findings

Refs [jupyter-naas/abi#1405](https://github.com/jupyter-naas/abi/issues/1405). Explored on 2026-11-02 against TEN Framework 0.11.74 on an Apple M2 Pro (16 GB, macOS 15.5).

## Recommendation

Build option C first: browser WebRTC to OpenAI Realtime, with ABI as an `ask_abi` function tool served by the new `/api/v1/voice/chat/completions` route. Keep TEN for later, if Nexus needs phone calls (TEN ships Twilio, Telnyx and Plivo SIP examples) or non-OpenAI voices.

The 8 to 40 s delay is ABI's time to first token, not the voice transport. Any cascade, TEN included, waits for the LLM before it can speak, so options A and B inherit ABI's latency on every turn. Only a speech-to-speech model in front of ABI separates chit-chat latency from ABI. Option C does that with no new runtime, no Agora account and no GPU.

## What was measured

All numbers are seconds from end of speech to first audio, on a home connection, with synthetic speech from macOS `say`.

| Setup | First audio | Notes |
|---|---|---|
| Current Nexus call | 8 to 40 | User report |
| TEN cascade, OpenAI only (`gpt-4o-transcribe`, `gpt-4o-mini`, `gpt-4o-mini-tts`), warm | 2.7 to 3.0 | ASR final about 1.0, LLM first token about 0.7, TTS first byte 0.8 to 0.95. First turn 5.9 (cold LLM connection) |
| TEN cascade into the voice route, fake ABI with a 1.5 s tool call | 1.6 to 3.0 | Filler spoken first, answer after the tool. Real ABI adds its own time to first token |
| OpenAI Realtime `gpt-realtime`, `semantic_vad` high eagerness | 1.2 | 0.8 of that is the turn detector waiting |
| OpenAI Realtime `gpt-realtime`, `server_vad` 300 ms | 0.84 to 0.87 | Meets the under 1 s target |
| OpenAI Realtime, tool turn | filler 1.36, tool call 2.27 | Answer about 0.5 after the tool result |
| `gpt-realtime-mini`, `server_vad` 300 ms | 1.0 to 1.16 | Not faster; spoke a filler where no tool was needed |

Barge-in was not measured. Both TEN (`main_python` sends an interrupt on every ASR result) and Realtime (`interrupt_response`) implement it.

## TEN facts that matter

- **Agora is not mandatory.** The `websocket-example` graph uses `websocket_server` (16 kHz mono PCM as base64 JSON). It accepts one client per TEN process, so each concurrent call needs its own worker. TEN's Go server spawns them (`WORKERS_MAX`).
- **OpenAI-only cascade works.** `openai_asr_python` (Realtime transcription), `openai_llm2_python` and `openai_tts2_python` need only `OPENAI_API_KEY`. The graph used here is in `tenapp/property.json`.
- **Realtime in TEN is `openai_mllm_python`.** The shipped `voice-assistant-realtime` example uses `agora_rtc`; swapping in `websocket_server` was not tried.
- **Turn detection model.** `TEN_Turn_Detection` is a 7.6B text model served over an OpenAI-compatible API (vLLM). TEN's example deploys it to an NVIDIA A10 on Cerebrium. It cannot run on this Mac.
- **Docker image is `linux/amd64` only** (`ten_agent_build:0.7.14`, 0.65 GB compressed) and publishes ports 8000 to 9001, which collide with local ABI services. Docker was not started for this exploration.
- **Native macOS arm64 works.** `tman` 0.11.74 and the runtime ship arm64 builds. Three fixes were needed: `TEN_PYTHON_LIB_PATH` pointing at an arm64 `libpython3.10.dylib`, `samplerate>=0.2.1` (0.1.0 loads an Intel `libsamplerate` from `/usr/local`), and `httpx[http2]` for the TTS extension.
- **Security: `openai_llm2_python` logs its `api_key` at info level.** In option A that key is the caller's Nexus token. Patch the log line or mint a short-lived token per call before any deployment.

## The bridge in this branch

`POST /api/v1/voice/chat/completions` is an OpenAI-compatible route next to the existing Continue gateway. It is off unless `VOICE_GATEWAY_ENABLED=true`, and the current browser call path does not use it.

- Streams speakable sentences only. Markdown, fenced tool output, URLs and the hidden chat marker never reach TTS (`services/openai_gateway/voice.py`).
- The first tool call becomes one spoken filler ("One moment, let me check.") unless the agent already said something.
- Every turn carries a short voice style instruction, because ABI agents only read the latest user message.
- One call keeps one ABI thread through an `X-Voice-Session` header, scoped to the authenticated user.

Serves option A as the LLM endpoint and options B and C as the `ask_abi` backend (non-streaming).

Verified: 12 new unit tests plus the existing gateway tests pass. The TEN graph called the route end to end with a fake ABI agent: bearer token and session header arrived, both turns used `voice-user-1-call-smoke-1`, and only clean sentences were spoken. The route has not run against a real ABI agent.

## Cost, per call minute (estimates)

These are list prices as we last knew them; check current pricing before committing.

- **C or B (`gpt-realtime`)**: roughly $0.05 to $0.15 per conversation minute (audio in and out plus re-sent context), plus ABI's own LLM cost for tool turns.
- **A, OpenAI only**: about $0.02 per minute for ASR and TTS, plus ABI's LLM on every turn. Deepgram Nova-3 and Cartesia or ElevenLabs are similar or cheaper and faster.
- **A with Agora**: Agora's free tier covers the first 10,000 minutes a month.
- **Turn detection GPU**: an A10 on a serverless GPU host, billed per second while warm.

## Next steps

1. Nexus API: `POST /api/voice/realtime/session` mints an OpenAI Realtime ephemeral key with the instructions, `server_vad` at 300 ms and the `ask_abi` tool. The real key never reaches the browser.
2. Web: a `realtime-call-engine.ts` behind a feature flag. It opens WebRTC to OpenAI, listens on the data channel, and on `response.function_call_arguments.done` calls `/api/v1/voice/chat/completions` (non-streaming, `X-Voice-Session` set to the call id), then sends `function_call_output` and `response.create`.
3. Enable `VOICE_GATEWAY_ENABLED` in dev and measure with `realtime_latency_probe.py` and a real ABI agent.
4. Test barge-in and a long ABI tool run in the browser.
5. Revisit TEN when Nexus needs SIP telephony or provider-neutral ASR and TTS. Start from `tenapp/` here and patch the API key log line first.

## Reproduce the TEN cascade natively

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/TEN-framework/ten-framework.git
cd ten-framework && git sparse-checkout set --no-cone '/ai_agents/agents/ten_packages/extension/' '/ai_agents/agents/examples/websocket-example/'
mkdir ai_agents/agents/examples/nexus-voice && cd ai_agents/agents/examples/nexus-voice
tman create app tenapp --template default_app_python
cp -R ../websocket-example/tenapp/ten_packages tenapp/   # main_python controller
cp <this folder>/tenapp/*.json tenapp/
cd tenapp && tman install
uv venv -p 3.10 .venv && . .venv/bin/activate
pip install -r ten_packages/system/ten_runtime_python/requirements.txt -r ten_packages/system/ten_ai_base/requirements.txt \
  $(for r in ten_packages/extension/*/requirements.txt; do echo -r $r; done) 'samplerate>=0.2.1' 'httpx[http2]'
export TEN_PYTHON_LIB_PATH=$(python -c 'import sys;print(sys.base_prefix)')/lib/libpython3.10.dylib
export PYTHONPATH=ten_packages/system/ten_runtime_python/lib:ten_packages/system/ten_runtime_python/interface:ten_packages/system/ten_ai_base/interface:ten_packages/system:$(python -c 'import site;print(site.getsitepackages()[0])')
export DYLD_LIBRARY_PATH=$PWD/ten_packages/system/ten_runtime/lib
export OPENAI_API_KEY=... TEN_LLM_API_KEY=...   # TEN_LLM_BASE_URL=<nexus>/api/v1/voice and TEN_LLM_MODEL=<agent> to use ABI
python main.py   # websocket_server on 127.0.0.1:8765
```
