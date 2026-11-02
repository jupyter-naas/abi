"""Stream a 16 kHz mono PCM utterance into TEN's websocket_server and time the reply.

Usage: python ws_latency_probe.py question.pcm
Make one with: say -v Samantha --data-format=LEI16@16000 -o q.wav "..." (then strip the WAV header).
"""

import asyncio
import base64
import json
import sys
import time

import websockets

FRAME = 640  # 20 ms of 16 kHz mono s16le


async def main(pcm: bytes, port: int = 8765) -> None:
    pcm += b"\x00" * (16000 * 2 * 3)  # 3 s of trailing silence
    marks: dict[str, float] = {}
    audio_bytes = 0
    texts: list[str] = []
    async with websockets.connect(f"ws://127.0.0.1:{port}", max_size=None) as ws:

        async def reader() -> None:
            nonlocal audio_bytes
            async for raw in ws:
                msg = json.loads(raw)
                now = time.perf_counter()
                kind, name = msg.get("type"), msg.get("name")
                data = msg.get("data") or {}
                if kind == "audio":
                    marks.setdefault("first_audio", now)
                    audio_bytes += len(base64.b64decode(msg["audio"]))
                    marks["last_audio"] = now
                elif kind == "data" and name == "asr_result" and data.get("final"):
                    marks.setdefault("asr_final", now)
                    texts.append("USER: " + str(data.get("text")))
                elif kind == "data" and name == "text_data":
                    if data.get("role") == "assistant" and data.get("text"):
                        marks.setdefault("first_llm_text", now)
                        if data.get("is_final"):
                            texts.append("ASSISTANT: " + str(data.get("text")))
                elif kind == "error":
                    texts.append("ERROR: " + str(msg))

        task = asyncio.create_task(reader())
        await asyncio.sleep(4)  # let the greeting play out
        marks.clear()
        audio_bytes = 0
        texts.clear()
        speech_end = None
        for i in range(0, len(pcm), FRAME):
            await ws.send(
                json.dumps({"audio": base64.b64encode(pcm[i : i + FRAME]).decode()})
            )
            if speech_end is None and i >= len(pcm) - 16000 * 2 * 3:
                speech_end = time.perf_counter()
            await asyncio.sleep(0.02)
        await asyncio.sleep(8)
        task.cancel()
    for k in ("asr_final", "first_llm_text", "first_audio", "last_audio"):
        if k in marks:
            print(f"{k}: +{marks[k] - speech_end:.2f}s after end of speech")
    print(f"tts audio received: {audio_bytes / 48000:.1f}s at 24 kHz")
    print("\n".join(texts))


with open(sys.argv[1], "rb") as f:
    asyncio.run(main(f.read()))
