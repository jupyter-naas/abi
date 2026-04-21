"""Audio transcription endpoint backed by OpenAI."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.core.config import settings

OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
TRANSCRIBE_MODEL = "gpt-4o-transcribe"

router = APIRouter()

openai_api_key = (
    ABIModule.get_instance()
    .engine.modules["naas_abi_marketplace.ai.chatgpt"]
    .configuration.openai_api_key
)


@router.post("", include_in_schema=True)
@router.post("/", include_in_schema=False)
async def transcribe_audio(
    audio: UploadFile = File(...),
    api_key_override: str | None = Form(default=openai_api_key, alias="apiKey"),
    conversation_id: str | None = Form(default=None, alias="conversation_id"),
) -> JSONResponse:
    if not audio.filename:
        filename = "recording.webm"
    else:
        filename = audio.filename

    content = await audio.read()
    if not content:
        return JSONResponse({"error": "Missing audio file"}, status_code=400)

    api_key = (api_key_override or "").strip() or (settings.openai_api_key or "").strip()
    if not api_key:
        return JSONResponse(
            {"error": "OPENAI_API_KEY not configured on the server"},
            status_code=500,
        )

    preserved_conversation_id = (conversation_id or "").strip() or None

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                OPENAI_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": TRANSCRIBE_MODEL},
                files={
                    "file": (
                        filename,
                        content,
                        audio.content_type or "application/octet-stream",
                    )
                },
            )
    except Exception as exc:
        message = str(exc) if str(exc) else "Unknown error"
        return JSONResponse({"error": message}, status_code=500)

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
