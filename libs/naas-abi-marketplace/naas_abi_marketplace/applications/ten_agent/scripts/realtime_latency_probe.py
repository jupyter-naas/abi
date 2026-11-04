"""Time OpenAI Realtime speech-to-speech: end of speech to first audio, plus a tool turn.

Usage: OPENAI_API_KEY=... <runtime_dir>/venv/bin/python realtime_latency_probe.py a.pcm chitchat b.pcm tool
Input: 24 kHz mono s16le PCM. RT_MODEL picks the model; RT_TD overrides turn_detection as JSON,
e.g. RT_TD='{"type":"server_vad","silence_duration_ms":300}'.
"""

import asyncio
import base64
import json
import os
import sys
import time

import websockets

MODEL = os.environ.get("RT_MODEL", "gpt-realtime")
URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"
FRAME = 960  # 20 ms at 24 kHz s16le

TOOL = {
    "type": "function",
    "name": "ask_abi",
    "description": "Ask the ABI agent anything about the user's company data, CRM, documents or knowledge graph.",
    "parameters": {
        "type": "object",
        "properties": {"question": {"type": "string"}},
        "required": ["question"],
    },
}


async def turn(ws, pcm: bytes, label: str) -> None:
    marks: dict[str, float] = {}
    transcript: list[str] = []
    for i in range(0, len(pcm), FRAME):
        await ws.send(
            json.dumps(
                {
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(pcm[i : i + FRAME]).decode(),
                }
            )
        )
        await asyncio.sleep(0.02)
    speech_end = time.perf_counter()
    silence = base64.b64encode(b"\x00" * FRAME).decode()
    done = False
    tool_called = False

    async def pump_silence() -> None:
        while not done:
            await ws.send(
                json.dumps({"type": "input_audio_buffer.append", "audio": silence})
            )
            await asyncio.sleep(0.02)

    pumper = asyncio.create_task(pump_silence())
    while True:
        ev = json.loads(await asyncio.wait_for(ws.recv(), 30))
        now = time.perf_counter() - speech_end
        t = ev["type"]
        if t == "input_audio_buffer.speech_stopped":
            marks.setdefault("vad_stop", now)
        elif t == "response.output_audio.delta":
            marks.setdefault(
                "first_audio" if not tool_called else "first_audio_after_tool", now
            )
        elif t == "response.output_audio_transcript.done":
            transcript.append(ev.get("transcript", ""))
        elif t == "response.function_call_arguments.done":
            marks["tool_call"] = now
            tool_called = True
            await asyncio.sleep(1.5)  # pretend ABI took 1.5 s
            await ws.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": ev["call_id"],
                            "output": json.dumps(
                                {
                                    "answer": "Three open deals: Acme 40k, Globex 25k, Initech 12k."
                                }
                            ),
                        },
                    }
                )
            )
            await ws.send(json.dumps({"type": "response.create"}))
        elif t == "response.done":
            out = ev["response"].get("output", [])
            if not any(o.get("type") == "function_call" for o in out):
                break
        elif t == "error":
            print("ERROR", ev.get("error", {}).get("message"))
            break
    done = True
    await pumper
    print(
        label, {k: round(v, 2) for k, v in marks.items()}, "|", " / ".join(transcript)
    )


async def main(turns: list[tuple[bytes, str]]) -> None:
    headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}
    async with websockets.connect(URL, additional_headers=headers, max_size=None) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "session.update",
                    "session": {
                        "type": "realtime",
                        "instructions": "You are a concise voice assistant. Reply in one or two short sentences. Before calling a tool, first say a short filler like 'Let me check.'",
                        "audio": {
                            "input": {
                                "format": {"type": "audio/pcm", "rate": 24000},
                                "turn_detection": json.loads(
                                    os.environ.get(
                                        "RT_TD",
                                        '{"type": "semantic_vad", "eagerness": "high"}',
                                    )
                                ),
                            },
                            "output": {
                                "format": {"type": "audio/pcm", "rate": 24000},
                                "voice": "marin",
                            },
                        },
                        "tools": [TOOL],
                    },
                }
            )
        )
        for pcm, label in turns:
            await turn(ws, pcm, label)


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


asyncio.run(
    main([(_read(p), label) for p, label in zip(sys.argv[1::2], sys.argv[2::2])])
)
