# `export_conversation_as_response`

## What it is
Utility function that exports a chat conversation (conversation metadata + messages) into a downloadable `StreamingResponse` in one of three formats:
- `txt` (plain text)
- `json` (JSON document)
- default (Markdown)

## Public API
- `export_conversation_as_response(conversation_id: str, format: str, user_id: str, conversation: Any, messages: list[Any]) -> StreamingResponse`
  - Builds export content from `conversation` and `messages`.
  - Returns a `fastapi.responses.StreamingResponse` with:
    - `Content-Disposition` set to an attachment filename based on `conversation_id` and format.
    - `media_type` set according to format (`text/plain`, `application/json`, `text/markdown`).

## Configuration/Dependencies
- **FastAPI**: `fastapi.responses.StreamingResponse`
- **Timezone**: `naas_abi.apps.nexus.apps.api.app.core.datetime_compat.UTC` used for export timestamp.
- **Expected attributes** (duck-typed):
  - `conversation`: `title`, `workspace_id`, `created_at`, `updated_at`
  - each `msg` in `messages`: `id`, `role`, `content`, `agent`, `created_at`
- **Format handling**:
  - `"txt"` and `"json"` are explicit; any other value results in Markdown output.

## Usage
Minimal example (works without FastAPI app wiring, but returns a `StreamingResponse` object):

```python
from datetime import datetime, timezone
from types import SimpleNamespace

from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__export import (
    export_conversation_as_response,
)

conversation = SimpleNamespace(
    title="Demo",
    workspace_id="ws_1",
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
)

messages = [
    SimpleNamespace(
        id="m1",
        role="user",
        content="Hello",
        agent=None,
        created_at=datetime.now(timezone.utc),
    ),
    SimpleNamespace(
        id="m2",
        role="assistant",
        content="Hi there!",
        agent="default",
        created_at=datetime.now(timezone.utc),
    ),
]

resp = export_conversation_as_response(
    conversation_id="c1",
    format="json",  # "txt", "json", or anything else => markdown
    user_id="u1",
    conversation=conversation,
    messages=messages,
)
```

## Caveats
- `format` is not validated beyond `"txt"` and `"json"` checks; any other value produces Markdown.
- The function assumes `conversation.*` and `msg.*` fields exist and that `created_at/updated_at` support `.isoformat()`.
