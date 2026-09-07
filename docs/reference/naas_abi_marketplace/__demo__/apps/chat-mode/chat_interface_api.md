# chat_interface_api.py

## What it is
- A Streamlit chat UI that talks to the ABI Agents through an HTTP API (`POST /agents/{Agent}/completion`).
- Supports switching the active agent via `@mentions` (e.g., `@claude`) or simple “switch/talk to …” phrases (including a few French variants).
- Optionally lists and loads past conversation threads from PostgreSQL (`checkpoints` table) when `POSTGRES_URL` is set.

## Public API
This file is primarily a Streamlit app script; the following module-level functions are the callable surface:

- `get_postgres_connection() -> psycopg.Connection | None`
  - Connects to PostgreSQL using `POSTGRES_URL`. Returns `None` if not configured or on failure (also emits a Streamlit error).

- `get_conversation_threads() -> list[dict]`
  - Queries `checkpoints` to list up to 50 recent `thread_id`s and attempts to derive a short title from early human messages.

- `load_conversation_from_db(thread_id: str) -> None`
  - Loads all checkpoints for a thread, extracts human/ai messages, de-duplicates them, and populates `st.session_state.messages`. Sets `st.session_state.thread_id` and `current_conversation_id`.

- `create_new_conversation() -> None`
  - Creates a new random numeric `thread_id` (10000–99999) and resets the current conversation state.

- `check_api_status() -> bool`
  - Checks API availability by requesting `GET {ABI_API_BASE}/openapi.json` with a short timeout.

- `call_abi_api(agent_name: str, prompt: str, thread_id: int = 1) -> dict`
  - Calls `POST {ABI_API_BASE}/agents/{MappedAgent}/completion` with bearer auth.
  - Returns `{"success": True, "content": ...}` on HTTP 200; otherwise `{"success": False, "error": ...}`.

- `process_user_input(user_input: str) -> tuple[str, str]`
  - Detects agent switching:
    - `@agent` mentions (`AGENT_MAPPING` keys)
    - phrases like `talk to grok`, `switch to claude`, `use gemini`, plus some French variants
  - Updates `st.session_state.active_agent` and returns `(agent_name, processed_input)`.

- `send_message(user_input: str) -> None`
  - Appends the user message, calls the API, appends the assistant response (or error), and triggers `st.rerun()` if an agent switch occurred.

## Configuration/Dependencies

### Environment variables
- `ABI_API_KEY` (**required**)
  - If missing, the app displays an error and stops.
- `ABI_API_BASE` (optional; default: `http://localhost:9879`)
  - Base URL for the ABI API.
- `POSTGRES_URL` (optional)
  - Enables listing/loading conversation history from PostgreSQL.

### Python dependencies
- `streamlit`
- `requests`
- `python-dotenv` (`load_dotenv()` is called at import time)
- `psycopg` (only needed if `POSTGRES_URL` is set)

### External services / endpoints
- ABI API must expose:
  - `GET /openapi.json`
  - `POST /agents/{AgentName}/completion` (expects JSON: `{"prompt": "...", "thread_id": "..."}`)

### Agent mapping
- Mentions/phrases map via `AGENT_MAPPING`, e.g.:
  - `claude -> Claude`, `chatgpt -> ChatGPT`, `deepseek -> DeepSeek`, etc.

## Usage

Run as a Streamlit app:

```bash
export ABI_API_KEY="your_key"
export ABI_API_BASE="http://localhost:9879"  # optional
# export POSTGRES_URL="postgresql://user:pass@host:5432/db"  # optional

streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/chat-mode/chat_interface_api.py
```

In the UI:
- Send a normal message to use the current active agent.
- Switch agents by:
  - `@claude Explain ...`
  - `switch to grok`
  - `talk to gemini`

## Caveats
- The script executes Streamlit UI code at import time; it is not structured as an importable library module.
- PostgreSQL integration assumes a `checkpoints` table with columns including `thread_id`, `checkpoint`, `checkpoint_id`, `checkpoint_ns`.
- Loaded message timestamps are set to `datetime.now()` during extraction (original checkpoint timestamps are not preserved).
- Assistant responses strip `<think>...</think>` blocks via regex before display.
- The API response body is treated as text and unwrapped with `strip('"')` (assumes a simple quoted string response).
