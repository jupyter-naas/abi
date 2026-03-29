# Agent logos

Agent list entries in the Chat sidebar automatically resolve the correct logo for each AI provider.

## How it works

A `LOGO_MAP` array in `chat-section.tsx` matches the agent name against regex patterns and returns a logo URL + an `invert` flag (for monochrome SVG icons that need CSS `dark:invert` in dark mode).

### Priority order

| Pattern | Source | Invert in dark mode? |
|---|---|---|
| `openai`, `gpt-*`, `o1/o3/o4` | `cdn.simpleicons.org/openai` | Yes |
| `claude`, `anthropic` | `cdn.simpleicons.org/anthropic` | Yes |
| `gemini`, `gemma` | `cdn.simpleicons.org/googlegemini` | No (coloured) |
| `llama`, `meta:` | `cdn.simpleicons.org/meta` | Yes |
| `perplexity` | `cdn.simpleicons.org/perplexity` | Yes |
| `ollama` | `cdn.simpleicons.org/ollama` | Yes |
| `mistral`, `mixtral` | `mistral.ai/favicon.ico` | No |
| `deepseek` | `deepseek.com/favicon.ico` | No |
| `grok`, `xai` | `x.ai/favicon.ico` | Yes |
| `openrouter` | `openrouter.ai/favicon.ico` | No |
| `groq` | `groq.com/favicon.ico` | No |
| `qwen` | Google favicon proxy | No |
| `cohere` | `cohere.com/favicon.ico` | No |
| `amazon`, `bedrock`, `nova` | Google favicon proxy | No |
| *(no match)* | Coloured 2-letter initials badge | — |

If an agent has an explicit `logoUrl` set in the database, that takes priority over the pattern match.

## List / Grid toggle

The **Agents** section header has a toggle button (list icon ↔ grid icon):

- **List** (default) — compact tree rows, 16×16 logo + full name
- **Grid** — 3-column grid, 32×32 logo + first word of name, full name in tooltip

## Source files

`.abi/.../web/src/components/shell/sidebar/chat-section.tsx` — `LOGO_MAP`, `resolveAgentLogo()`, list/grid rendering.
