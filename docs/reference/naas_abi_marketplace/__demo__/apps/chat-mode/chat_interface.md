# chat_interface

## What it is
- A Streamlit-based chat UI for interacting with an `AbiAgent` loaded from `naas_abi.modules`.
- Provides basic chat history, agent initialization/reset, and `@mention` parsing to switch the displayed “active agent” context and route input via an orchestration-style prompt.

## Public API
This file is primarily a Streamlit app script; the following top-level functions are defined and callable:

- `load_agent(agent_class: str)`
  - Searches `naas_abi.modules` for an agent whose class name matches `agent_class` (e.g., `"AbiAgent"`), and returns that agent instance (or `None`).
- `initialize_agent()`
  - Initializes and stores the `AbiAgent` in `st.session_state.agent` (lazy init). Returns the agent or `None`.
- `handle_agent_response(response)`
  - Extracts text content from `response` (string, `.content`, or `.messages[*].content`), strips `<think>...</think>` blocks, and appends an assistant message to `st.session_state.messages`.
- `process_user_input(user_input: str) -> str`
  - Detects `@mentions` (e.g., `@claude`), updates `st.session_state.active_agent`, and rewrites the user input into an orchestration prompt:
    - `@agent some text` → `ask agent some text`
    - `@agent` alone → `I want to talk to agent`
- `send_message(user_input: str)`
  - Calls `st.session_state.agent.invoke(user_input)` and passes the result to `handle_agent_response()`.

Other notable module-level items:
- `AGENT_MAPPING`: maps mention keys (e.g., `"claude"`) to display names (e.g., `"Claude"`).

## Configuration/Dependencies
- Runtime environment:
  - Loads environment variables via `dotenv.load_dotenv()` at import time.
  - Forces:
    - `os.environ["ENV"] = "dev"`
    - `os.environ["LOG_LEVEL"] = "ERROR"`
  - Changes working directory to a computed project root and inserts it into `sys.path`.
- Python packages:
  - `streamlit`
  - `python-dotenv`
- Internal dependencies:
  - Imports `naas_abi.modules` and expects an agent class named `AbiAgent` to be present within loaded modules.
  - Attempts to import `src` (for debug/validation).

## Usage
Run as a Streamlit app:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/chat-mode/chat_interface.py
```

In the UI:
- Type messages in the chat input.
- Use `@mentions` to switch “Active Agent” and rewrite the message, e.g.:
  - `@claude Summarize this` → sent as `ask claude Summarize this`
- Sidebar:
  - **Clear Chat** resets `st.session_state.messages`.
  - **Reset Agent** clears `st.session_state.agent` and resets active agent to `"Abi"`.

## Caveats
- This script executes Streamlit UI code at import time; it is not structured as a reusable library module.
- The “active agent” is a UI/session-state concept; messages are always sent through `st.session_state.agent.invoke(...)` (the loaded `AbiAgent`), with routing implied by the rewritten prompt (e.g., `ask claude ...`).
- Extensive debug output is written to the Streamlit page (working directory, import status, module/agent discovery).
