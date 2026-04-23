# chat_interface_api.py

## What it is
- A Streamlit chat UI that talks to the ABI Agents via an HTTP API (`/agents/{Agent}/completion`).
- Supports switching agents via `@mentions` or simple natural-language phrases.
- Optionally lists/loads past conversation threads from PostgreSQL (checkpoints table) if `POSTGRES_URL` is set.

## Public API
This file is primarily a Streamlit app script; functions below are defined at module level:

- `get_postgres_connection() -> psycopg.Connection | None`
  - Connects to PostgreSQL using `POSTGRES_URL` (if set). Returns `None` if not configured or on failure.
- `get_conversation_threads() -> list[dict]`
  - Queries PostgreSQL `checkpoints` for up to 50 recent `thread_id`s and attempts to derive a title from early user messages.
- `load_conversation_from_db(thread_id: str) -> None`
  - Loads checkpoints for a `thread_id`, extracts messages, de-duplicates them, and populates `st.session_state.messages`.
- `create_new_conversation() -> None`
  - Creates a new random `thread_id` and resets the current chat state.
- `check_api_status() -> bool`
  - Checks API availability by requesting `GET {ABI_API_BASE}/openapi.json`.
- `call_abi_api(agent_name: str, prompt: str, thread_id: int = 1) -> dict`
  - Calls `POST {ABI_API_BASE}/agents/{MappedAgent}/completion` with bearer auth.
  - Returns a dict like `{"success": True, "content": ...}` or `{"success": False, "error": ...}`.
- `process_user_input(user_input: str) -> tuple[str, str]`
  - Parses user input for:
    - `@agent` mentions (e.g. `@claude`)
    - simple phrases like `talk to grok`, `switch to claude`, etc. (includes a few French variants)
  - Updates `st.session_state.active_agent` and returns `(agent_name, processed_input)`.
- `send_message(user_input: str) -> None`
  - Appends the user message to session history, calls the API, appends assistant response (or error), and reruns if agent switched.

## Configuration/Dependencies
Environment variables:
- `ABI_API_KEY` (required)
  - If missing, the app stops immediately with an error.
- `ABI_API_BASE` (optional, default: `http://localhost:9879`)
  - Base URL for ABI API.
- `POSTGRES_URL` (optional)
  - Enables conversation listing/loading from PostgreSQL.

Python packages / services:
- `streamlit`
- `requests`
- `python-dotenv` (used via `load_dotenv()`)
- `psycopg` (only needed if `POSTGRES_URL` is set)
- ABI API service exposing:
  - `GET /openapi.json`
  - `POST /agents/{AgentName}/completion` (expects JSON with `prompt` and `thread_id` as string)

Agent mapping used for `@mentions` and phrase detection:
- Keys like `abi`, `claude`, `gemini`, `mistral`, `chatgpt`, `grok`, `llama`, `perplexity`, `qwen`, `deepseek` mapped to API agent names (capitalized or specific).

## Usage
Run as a Streamlit app:

```bash
export ABI_API_KEY="your_key"
export ABI_API_BASE="http://localhost:9879"   # optional
# export POSTGRES_URL="postgresql://..."      # optional for persisted threads

streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/chat-mode/chat_interface_api.py
```

In the UI:
- Type messages normally to use the current active agent.
- Switch agents by:
  - `@claude What is...`
  - `switch to grok`
  - `talk to gemini`

## Caveats
- `ABI_API_KEY` is mandatory; the app stops if it is not set.
- API response content is treated as plain text; it strips `<think>...</think>` blocks if present.
- PostgreSQL integration assumes a `checkpoints` table with columns including `thread_id`, `checkpoint`, `checkpoint_id`, `checkpoint_ns`.
- Loaded conversation timestamps are set to `datetime.now()` during extraction (original message times are not preserved).
