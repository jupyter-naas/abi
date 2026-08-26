# chat_interface

## What it is
- A Streamlit chat app for interacting with an `AbiAgent` discovered from `naas_abi.modules`.
- Maintains chat history in `st.session_state`, supports `@mentions` to set an “active agent” label and rewrites the prompt into an orchestration-style command (e.g., `ask claude ...`).

## Public API
This file is primarily a Streamlit app script (executes on import). The following top-level functions are defined:

- `load_agent(agent_class: str)`
  - Imports `naas_abi.modules`, iterates loaded modules/agents, and returns the first agent whose class name matches `agent_class`.
  - Writes debug info to the Streamlit page; returns `None` on failures.

- `initialize_agent()`
  - Lazy-initializes `st.session_state.agent` by calling `load_agent("AbiAgent")`.
  - Returns the agent instance or `None`.

- `handle_agent_response(response)`
  - Extracts text from:
    - `response.content`, or
    - `response` if it’s a `str`, or
    - concatenated `.messages[*].content` if present.
  - Removes `<think>...</think>` blocks and appends an assistant message to `st.session_state.messages`.

- `process_user_input(user_input: str) -> str`
  - Detects the first `@mention` (`@(\w+)`) and, if in `AGENT_MAPPING`:
    - updates `st.session_state.active_agent`,
    - rewrites input:
      - `@agent some text` → `ask agent some text`
      - `@agent` alone → `I want to talk to agent`
  - If unknown mention: reports an error via Streamlit and returns the original input.

- `send_message(user_input: str)`
  - Calls `st.session_state.agent.invoke(user_input)` and forwards the result to `handle_agent_response()`.

Other module-level items:
- `AGENT_MAPPING: dict[str, str]`
  - Maps mention keys (e.g., `"claude"`) to display names (e.g., `"Claude"`).

## Configuration/Dependencies
- Environment / runtime behavior:
  - Calls `dotenv.load_dotenv()` at import time.
  - Computes a `project_root` relative to this file, inserts it into `sys.path`, and `os.chdir()` to it.
  - Sets:
    - `os.environ["ENV"] = "dev"`
    - `os.environ["LOG_LEVEL"] = "ERROR"`
- External dependencies:
  - `streamlit`
  - `python-dotenv`
- Internal dependencies / expectations:
  - Imports `naas_abi.modules` and expects modules to expose `.agents` collections containing an `AbiAgent` instance.
  - Attempts `import src` (fails the agent load if unavailable).

## Usage
Run as a Streamlit app:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/chat-mode/chat_interface.py
```

In the UI:
- Type into the chat input.
- Use `@mentions` (from the sidebar list) to switch the displayed active agent and rewrite the prompt, e.g.:
  - `@claude Summarize this` → sent as `ask claude Summarize this`
  - `@claude` → sent as `I want to talk to claude`

## Caveats
- The script executes Streamlit UI code at import time; it is not structured as a reusable library module.
- `active_agent` is a UI/session-state label; all messages are still sent through the single loaded agent via `agent.invoke(...)`, relying on prompt rewriting (`ask <agent> ...`) for routing.
- The app changes the current working directory and mutates `sys.path`, which can affect imports and file resolution. Debug output is written directly to the Streamlit page.
