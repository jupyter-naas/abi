# opencode — AI coding assistant

[opencode](https://opencode.ai) is an open-source terminal-based AI coding agent that runs alongside Nexus and provides the AI pane in the Lab section.

## How it works

```
Nexus Lab (port 3042)
    └── AI pane → SSE → opencode web server (port 4242)
                            └── LLM (Anthropic / OpenRouter)
                            └── MCP: filesystem → ~/aia
                            └── MCP: abi → http://localhost:9879/mcp
```

The AI can read and write any file under `~/aia` via the filesystem MCP server, and call ABI API tools via the ABI MCP server.

## Starting

```bash
make up           # starts Docker stack + opencode in background
make opencode-start  # restart opencode only
```

opencode logs go to `/tmp/opencode-web.log`.

## Configuration

**File**: `src/opencode/config/opencode.json`

```json
{
  "model": "anthropic/claude-haiku-4-5",
  "instructions": ["AGENTS.md", "SLIDES.md"],
  "mcp": {
    "filesystem": {
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/Users/jrvmac/aia"],
      "enabled": true
    },
    "abi": {
      "type": "remote",
      "url": "{env:ABI_API_BASE}/mcp",
      "enabled": true
    }
  }
}
```

### Changing the model

Edit `"model"` in `opencode.json`. Supported providers: `anthropic/`, `openai/`, `ollama/` (local). After changing, restart opencode with `make opencode-start`.

### System instructions

opencode loads these files as system context on startup:
- `~/aia/AGENTS.md` — project overview and module structure
- `~/aia/SLIDES.md` — slide deck format spec (so AI generates correct HTML)

To add more context, drop a `.md` file in `~/aia/` and add its name to `"instructions"` in `opencode.json`.

## Environment variables

API keys are read from `~/aia/.env` (sourced by the Makefile before starting opencode):

```env
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
OLLAMA_URL=http://localhost:11434
```

## Using the AI pane in Lab

The AI pane opens automatically when you navigate to Lab. Select **opencode** as the agent in the pane footer.

**Useful prompts:**

```
# Generate a new slide deck
Create a 5-slide deck about Q1 OKRs at src/myproject/slides.html

# Modify an existing file
In src/aia/config.py, add a new REDIS_URL config field with default localhost:6379

# Create a new module
Create a new module src/summarizer/ with FastAPI backend that summarises text using Anthropic

# Explore codebase
What does src/qdrant/ do and how is it started?
```

## Caveats

- Shell commands require confirmation (configured as `"bash": "ask"` in `opencode.json`)
- Images in slide previews load via the raw-file API (`/api/lab/fs/raw/`); opencode writes them as binary files if needed
- The AI pane streams responses via SSE; if the stream stalls, refresh the Lab page
