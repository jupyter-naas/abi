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

# Default Kokoro voices by detected language (prefix-coded in the model).
KOKORO_LANG_VOICES: dict[str, str] = {
    "en": "af_heart",
    "fr": "ff_siwis",
    "es": "ef_dora",
    "pt": "pf_dora",
    "it": "if_sara",
    "ja": "jf_alpha",
    "zh": "zf_xiaoxiao",
    "hi": "hf_alpha",
}

MAI_LANG_VOICES: dict[str, str] = {
    "en": "en-US-Harper:MAI-Voice-2",
    "fr": "fr-FR-Soleil:MAI-Voice-2",
    "es": "es-MX-Valeria:MAI-Voice-2",
    "de": "de-DE-Klaus:MAI-Voice-2",
}

VOXTRAL_LANG_VOICES: dict[str, str] = {
    "en": "en_paul_neutral",
    "fr": "fr_marie_neutral",
}

_FR_WORDS = frozenset(
    {
        "je",
        "tu",
        "nous",
        "vous",
        "bonjour",
        "merci",
        "oui",
        "non",
        "avec",
        "pour",
        "une",
        "des",
        "les",
        "que",
        "pas",
        "très",
        "bien",
        "est",
        "suis",
        "vais",
        "entends",
        "parfaitement",
        "aussi",
        "mais",
        "donc",
        "comme",
        "cette",
        "tout",
        "tous",
        "bonjour",
        "salut",
    }
)
_ES_WORDS = frozenset(
    {"hola", "gracias", "porque", "también", "está", "están", "qué", "más", "pero", "como"}
)
_PT_WORDS = frozenset(
    {"olá", "obrigado", "obrigada", "você", "não", "também", "está", "são", "como", "muito"}
)
_IT_WORDS = frozenset(
    {"ciao", "grazie", "perché", "anche", "sono", "come", "questo", "questa", "molto", "bene"}
)
_EN_WORDS = frozenset(
    {"the", "and", "you", "are", "is", "hello", "thanks", "with", "that", "this", "have", "what"}
)

router = APIRouter()


class SpeechRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str | None = None
    model: str | None = None
    language: str | None = None


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


def detect_speech_language(text: str) -> str:
    """Lightweight language guess for TTS voice routing (no extra dependency)."""
    sample = text.strip()
    if not sample:
        return "en"

    if re.search(r"[\u3040-\u30ff]", sample):
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", sample):
        return "zh"
    if re.search(r"[\u0900-\u097f]", sample):
        return "hi"

    lower = sample.lower()
    tokens = re.findall(r"[a-zàâäáãåæçéèêëíìîïñóòôöõœúùûüýÿß']+", lower, flags=re.IGNORECASE)
    scores: dict[str, float] = {"en": 0.0, "fr": 0.0, "es": 0.0, "pt": 0.0, "it": 0.0}

    if re.search(r"[àâäéèêëïîôùûüçœæ]", lower):
        scores["fr"] += 3.0
    if re.search(r"[ñ¿¡]", lower):
        scores["es"] += 3.0
    if re.search(r"[ãõ]", lower):
        scores["pt"] += 2.5
    if "'" in lower or "’" in sample:
        # Common in French contractions: t'entends, j'ai, c'est
        scores["fr"] += 1.0

    for token in tokens:
        if token in _FR_WORDS:
            scores["fr"] += 1.0
        if token in _ES_WORDS:
            scores["es"] += 1.0
        if token in _PT_WORDS:
            scores["pt"] += 1.0
        if token in _IT_WORDS:
            scores["it"] += 1.0
        if token in _EN_WORDS:
            scores["en"] += 0.6

    lang, score = max(scores.items(), key=lambda item: item[1])
    if score < 1.5:
        return "en"
    return lang


def resolve_voice_for_text(
    text: str,
    model: str,
    *,
    explicit_voice: str | None,
    explicit_language: str | None,
    default_voice: str,
) -> str:
    """Pick a voice matching the text language unless the caller forced one."""
    if explicit_voice:
        return explicit_voice

    auto_raw = (_secret("OPENROUTER_TTS_AUTO_LANGUAGE") or "1").strip().lower()
    if auto_raw in {"0", "false", "no", "off"}:
        return default_voice

    lang = (explicit_language or "").strip().lower() or detect_speech_language(text)
    if lang.startswith("fr"):
        lang = "fr"
    elif lang.startswith("es"):
        lang = "es"
    elif lang.startswith("pt"):
        lang = "pt"
    elif lang.startswith("it"):
        lang = "it"
    elif lang.startswith("ja"):
        lang = "ja"
    elif lang.startswith("zh") or lang.startswith("cn"):
        lang = "zh"
    elif lang.startswith("hi"):
        lang = "hi"
    elif lang.startswith("de"):
        lang = "de"
    elif lang.startswith("en"):
        lang = "en"

    model_l = model.lower()
    if "kokoro" in model_l:
        return KOKORO_LANG_VOICES.get(lang, default_voice)
    if "mai-voice" in model_l:
        return MAI_LANG_VOICES.get(lang, default_voice)
    if "voxtral" in model_l:
        return VOXTRAL_LANG_VOICES.get(lang, default_voice)
    return default_voice


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
    voice = resolve_voice_for_text(
        prepared,
        model,
        explicit_voice=(body.voice or "").strip() or None,
        explicit_language=(body.language or "").strip() or None,
        default_voice=default_voice,
    )

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
