"""Audio transcription endpoint backed by OpenAI."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
TRANSCRIBE_MODEL = "gpt-4o-transcribe"

router = APIRouter()


def get_api_key():
    from naas_abi import ABIModule

    api_key = (
        ABIModule.get_instance()
        .engine.modules["naas_abi_marketplace.ai.chatgpt"]
        .configuration.openai_api_key
    )
    assert api_key is not None
    return api_key


@router.post("", include_in_schema=True)
@router.post("/", include_in_schema=False)
async def transcribe_audio(
    audio: UploadFile = File(...),
    conversation_id: str | None = Form(default=None, alias="conversation_id"),
) -> JSONResponse:
    if not audio.filename:
        filename = "recording.webm"
    else:
        filename = audio.filename

    content = await audio.read()
    if not content:
        return JSONResponse({"error": "Missing audio file"}, status_code=400)

    api_key = get_api_key()
    if not api_key:
        return JSONResponse(
            {"error": "OPENAI_API_KEY not configured on the server"},
            status_code=500,
        )

    preserved_conversation_id = (conversation_id or "").strip() or None

    timeout = httpx.Timeout(connect=10.0, read=180.0, write=60.0, pool=30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(
                OPENAI_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": TRANSCRIBE_MODEL, "response_format": "json"},
                files={
                    "file": (
                        filename,
                        content,
                        audio.content_type or "application/octet-stream",
                    )
                },
            )
    except httpx.TimeoutException:
        return JSONResponse(
            {
                "error": "OpenAI transcription request timed out",
                "conversation_id": preserved_conversation_id,
            },
            status_code=504,
        )
    except httpx.HTTPError as exc:
        message = str(exc) if str(exc) else "Network error while calling OpenAI"
        return JSONResponse(
            {"error": message, "conversation_id": preserved_conversation_id},
            status_code=502,
        )
    except Exception as exc:
        message = str(exc) if str(exc) else "Unknown error"
        return JSONResponse(
            {"error": message, "conversation_id": preserved_conversation_id},
            status_code=500,
        )

    if response.status_code >= 400:
        detail = response.text if response.text else ""
        return JSONResponse(
            {
                "error": f"OpenAI transcription failed ({response.status_code})",
                "detail": detail,
                "conversation_id": preserved_conversation_id,
            },
            status_code=response.status_code,
        )

    try:
        payload: dict[str, Any] = response.json()
    except ValueError:
        payload = {}

    return JSONResponse(
        {
            "text": str(payload.get("text") or ""),
            "conversation_id": preserved_conversation_id,
        }
    )
