"""Audio transcription endpoint (OpenRouter or native OpenAI)."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    get_current_user_required,
)

OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
OPENROUTER_TRANSCRIBE_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
OPENAI_TRANSCRIBE_MODEL = "gpt-4o-transcribe"
OPENROUTER_TRANSCRIBE_MODEL = "openai/gpt-4o-transcribe"
DEFAULT_DOMAIN_VOCABULARY = "ABI, NaasAI, Nexus, Ontology, BFO, SPARQL, Oxigraph, Qdrant, TEN"

router = APIRouter(dependencies=[Depends(get_current_user_required)])

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Return a shared warm AsyncClient with keep-alive pooling for low-latency turns."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=180.0, write=60.0, pool=30.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            follow_redirects=True,
        )
    return _http_client


def build_transcription_prompt(custom_prompt: str | None = None) -> str:
    """Combine default platform domain vocabulary with optional caller vocabulary hints."""
    extra = (custom_prompt or "").strip()
    if not extra:
        return DEFAULT_DOMAIN_VOCABULARY
    if DEFAULT_DOMAIN_VOCABULARY.lower() in extra.lower():
        return extra
    return f"{DEFAULT_DOMAIN_VOCABULARY}, {extra}"


def normalize_transcription_language(raw: str | None) -> str | None:
    """Return an ISO-639-1 code from a hint like ``fr-FR``, or None when unusable.

    Without a language, Whisper-family models guess one from noise (often Chinese).
    """
    code = (raw or "").strip().lower().replace("_", "-").split("-", 1)[0]
    if len(code) == 2 and code.isalpha():
        return code
    return None


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
    prompt: str | None = Form(default=None, alias="prompt"),
    language: str | None = Form(default=None, alias="language"),
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
    effective_prompt = build_transcription_prompt(prompt)

    headers = {"Authorization": f"Bearer {api_key}"}
    if "openrouter.ai" in url:
        from naas_abi.apps.nexus.apps.api.app.services.openrouter_attribution import (
            openrouter_attribution_headers,
        )

        headers.update(openrouter_attribution_headers())

    form: dict[str, str] = {
        "model": model,
        "response_format": "json",
        "prompt": effective_prompt,
    }
    language_code = normalize_transcription_language(language)
    if language_code:
        form["language"] = language_code

    try:
        client = _get_http_client()
        response = await client.post(
            url,
            headers=headers,
            data=form,
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
