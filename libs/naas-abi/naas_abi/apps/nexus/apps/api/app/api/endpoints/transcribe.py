"""Audio transcription endpoint (OpenRouter or native OpenAI)."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
OPENROUTER_TRANSCRIBE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
OPENAI_TRANSCRIBE_MODEL = "gpt-4o-transcribe"
OPENROUTER_TRANSCRIBE_MODEL = "openai/gpt-4o-transcribe"

router = APIRouter()


def _secret(name: str) -> str | None:
    from naas_abi import ABIModule

    value = ABIModule.get_instance().engine.services.secret.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_transcription_backend() -> tuple[str, str, str] | None:
    """Return (url, api_key, model) for the best available transcription backend.

    Prefer OpenRouter when an OpenRouter key is present (this deployment's default).
    Fall back to native OpenAI only when a non-OpenRouter key is available.
    """
    openrouter_key = _secret("OPENROUTER_API_KEY")
    openai_key = _secret("OPENAI_API_KEY")
    transcribe_key = _secret("OPENAI_TRANSCRIBE_API_KEY")

    # Explicit native override wins when it is not an OpenRouter key.
    if transcribe_key and not transcribe_key.startswith("sk-or-"):
        return OPENAI_TRANSCRIBE_URL, transcribe_key, OPENAI_TRANSCRIBE_MODEL

    for key in (openrouter_key, openai_key, transcribe_key):
        if key and key.startswith("sk-or-"):
            return OPENROUTER_TRANSCRIBE_URL, key, OPENROUTER_TRANSCRIBE_MODEL

    if openai_key and not openai_key.startswith("sk-or-"):
        return OPENAI_TRANSCRIBE_URL, openai_key, OPENAI_TRANSCRIBE_MODEL

    return None


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

    backend = resolve_transcription_backend()
    if backend is None:
        return JSONResponse(
            {
                "error": (
                    "No transcription API key configured. Set OPENROUTER_API_KEY "
                    "(preferred) or a native OPENAI_TRANSCRIBE_API_KEY."
                )
            },
            status_code=500,
        )

    url, api_key, model = backend
    preserved_conversation_id = (conversation_id or "").strip() or None

    headers = {"Authorization": f"Bearer {api_key}"}
    if "openrouter.ai" in url:
        from naas_abi.apps.nexus.apps.api.app.services.openrouter_attribution import (
            openrouter_attribution_headers,
        )

        headers.update(openrouter_attribution_headers())

    timeout = httpx.Timeout(connect=10.0, read=180.0, write=60.0, pool=30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(
                url,
                headers=headers,
                data={"model": model, "response_format": "json"},
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
                "error": "Transcription request timed out",
                "conversation_id": preserved_conversation_id,
            },
            status_code=504,
        )
    except httpx.HTTPError as exc:
        message = str(exc) if str(exc) else "Network error while calling transcription API"
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
                "error": f"Transcription failed ({response.status_code})",
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
