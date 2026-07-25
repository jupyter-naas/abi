"""Text-to-speech endpoint (OpenRouter or native OpenAI)."""

from __future__ import annotations

import re
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"
OPENROUTER_SPEECH_URL = "https://openrouter.ai/api/v1/audio/speech"

# Cheap, reliable default on OpenRouter. Override via OPENROUTER_TTS_MODEL / VOICE.
OPENROUTER_TTS_MODEL = "hexgrad/kokoro-82m"
OPENROUTER_TTS_VOICE = "af_heart"

# Native OpenAI fallback.
OPENAI_TTS_MODEL = "tts-1"
OPENAI_TTS_VOICE = "alloy"

MAX_INPUT_CHARS = 3500

router = APIRouter()


class SpeechRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str | None = None
    model: str | None = None


def _secret(name: str) -> str | None:
    from naas_abi import ABIModule

    value = ABIModule.get_instance().engine.services.secret.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_speech_backend() -> tuple[str, str, str, str] | None:
    """Return (url, api_key, model, voice) for the best available TTS backend.

    Prefer OpenRouter when an OpenRouter key is present (this deployment's default).
    Fall back to native OpenAI only when a non-OpenRouter key is available.
    """
    openrouter_key = _secret("OPENROUTER_API_KEY")
    openai_key = _secret("OPENAI_API_KEY")
    speech_key = _secret("OPENAI_SPEECH_API_KEY")

    model_override = _secret("OPENROUTER_TTS_MODEL")
    voice_override = _secret("OPENROUTER_TTS_VOICE")

    if speech_key and not speech_key.startswith("sk-or-"):
        return (
            OPENAI_SPEECH_URL,
            speech_key,
            _secret("OPENAI_TTS_MODEL") or OPENAI_TTS_MODEL,
            voice_override or _secret("OPENAI_TTS_VOICE") or OPENAI_TTS_VOICE,
        )

    for key in (openrouter_key, openai_key, speech_key):
        if key and key.startswith("sk-or-"):
            return (
                OPENROUTER_SPEECH_URL,
                key,
                model_override or OPENROUTER_TTS_MODEL,
                voice_override or OPENROUTER_TTS_VOICE,
            )

    if openai_key and not openai_key.startswith("sk-or-"):
        return (
            OPENAI_SPEECH_URL,
            openai_key,
            _secret("OPENAI_TTS_MODEL") or OPENAI_TTS_MODEL,
            voice_override or _secret("OPENAI_TTS_VOICE") or OPENAI_TTS_VOICE,
        )

    return None


def prepare_speech_text(raw: str) -> str:
    """Strip common markdown so TTS does not read fencing and link syntax aloud."""
    text = raw.strip()
    if not text:
        return ""

    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~|>]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > MAX_INPUT_CHARS:
        text = text[: MAX_INPUT_CHARS - 3].rstrip() + "..."
    return text


@router.post("", include_in_schema=True)
@router.post("/", include_in_schema=False)
async def synthesize_speech(body: SpeechRequest) -> Response:
    prepared = prepare_speech_text(body.text)
    if not prepared:
        return JSONResponse({"error": "No speakable text provided"}, status_code=400)

    backend = resolve_speech_backend()
    if backend is None:
        return JSONResponse(
            {
                "error": (
                    "No speech API key configured. Set OPENROUTER_API_KEY "
                    "(preferred) or a native OPENAI_SPEECH_API_KEY."
                )
            },
            status_code=500,
        )

    url, api_key, default_model, default_voice = backend
    model = (body.model or "").strip() or default_model
    voice = (body.voice or "").strip() or default_voice

    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter.ai" in url:
        from naas_abi.apps.nexus.apps.api.app.services.openrouter_attribution import (
            openrouter_attribution_headers,
        )

        headers.update(openrouter_attribution_headers())

    payload: dict[str, Any] = {
        "model": model,
        "input": prepared,
        "voice": voice,
        "response_format": "mp3",
    }

    timeout = httpx.Timeout(connect=10.0, read=180.0, write=60.0, pool=30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        return JSONResponse({"error": "Speech request timed out"}, status_code=504)
    except httpx.HTTPError as exc:
        message = str(exc) if str(exc) else "Network error while calling speech API"
        return JSONResponse({"error": message}, status_code=502)
    except Exception as exc:
        message = str(exc) if str(exc) else "Unknown error"
        return JSONResponse({"error": message}, status_code=500)

    if response.status_code >= 400:
        detail = response.text if response.text else ""
        return JSONResponse(
            {
                "error": f"Speech synthesis failed ({response.status_code})",
                "detail": detail,
            },
            status_code=response.status_code,
        )

    content_type = response.headers.get("content-type") or "audio/mpeg"
    return Response(
        content=response.content,
        media_type=content_type,
        headers={"Cache-Control": "no-store"},
    )
