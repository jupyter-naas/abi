# `transcribe.py`

## What it is
- A FastAPI endpoint that accepts an uploaded audio file and forwards it to OpenAI’s audio transcription API.
- Returns JSON containing the transcribed text and an optional `conversation_id`.

## Public API
- `router: fastapi.APIRouter`
  - Provides POST routes for transcription.
- `get_api_key() -> str`
  - Retrieves `OPENAI_API_KEY` from `naas_abi.ABIModule.get_instance().engine.services.secret`.
  - Asserts the key is present (raises `AssertionError` if missing).
- `transcribe_audio(audio: UploadFile, conversation_id: str | None) -> JSONResponse` (async)
  - **Routes**:
    - `POST ""` (included in schema)
    - `POST "/"` (not included in schema)
  - **Inputs (multipart/form-data)**:
    - `audio` (file, required)
    - `conversation_id` (form field, optional; alias: `"conversation_id"`)
  - **Behavior**:
    - Sends file bytes to `https://api.openai.com/v1/audio/transcriptions` with:
      - `model="gpt-4o-transcribe"`
      - `response_format="json"`
    - Normalizes `conversation_id`: strips whitespace; empty becomes `null`.
  - **Responses**:
    - `200`: `{"text": "<transcript>", "conversation_id": <str|null>}`
    - `400`: missing/empty audio content
    - `500`: missing server API key; unexpected errors
    - `502`: network/HTTP client errors calling OpenAI
    - `504`: OpenAI request timeout
    - `>=400` from OpenAI: `{"error": "...", "detail": "<response text>", "conversation_id": ...}` with same status code

## Configuration/Dependencies
- **Secret**: `OPENAI_API_KEY` must be available via:
  - `naas_abi.ABIModule.get_instance().engine.services.secret.get("OPENAI_API_KEY")`
- **External services**:
  - OpenAI transcription endpoint: `https://api.openai.com/v1/audio/transcriptions`
- **Libraries**:
  - `fastapi` (router, file/form handling)
  - `httpx` (async HTTP client)

## Usage
Minimal FastAPI integration:

```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints.transcribe import router as transcribe_router

app = FastAPI()
app.include_router(transcribe_router, prefix="/transcribe", tags=["transcribe"])
```

Example request (client-side) using `httpx`:

```python
import httpx

with open("audio.webm", "rb") as f:
    files = {"audio": ("audio.webm", f, "audio/webm")}
    data = {"conversation_id": "abc123"}
    r = httpx.post("http://localhost:8000/transcribe", files=files, data=data)
    print(r.json())
```

## Caveats
- If `OPENAI_API_KEY` is missing, `get_api_key()` uses `assert` and may raise `AssertionError` rather than returning a JSON error.
- Timeouts are fixed in code (`connect=10s`, `read=180s`, `write=60s`, `pool=30s`).
- If the uploaded file has no filename, it defaults to `recording.webm`.
