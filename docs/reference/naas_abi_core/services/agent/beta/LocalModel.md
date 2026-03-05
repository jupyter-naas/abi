# AirgapChatOpenAI

## What it is
- `AirgapChatOpenAI` is a small subclass of `langchain_openai.ChatOpenAI` that:
  - Builds a single prompt combining any `SystemMessage` content with the latest `HumanMessage`.
  - Adds a plain-text “tool list” to the prompt when tools are bound.
  - Parses model output for simple tool calls (`TOOL_CALL: ...`) and (optionally) runs the tools, then re-prompts the model with tool results.

## Public API
### Class: `AirgapChatOpenAI(ChatOpenAI)`
- Purpose: Minimal wrapper around `ChatOpenAI` with basic, prompt-based tool support.

#### `__init__(**kwargs)`
- Pass-through to `ChatOpenAI.__init__`.
- Initializes an internal tool registry (`self._tools = []`).

#### `bind_tools(tools, **kwargs)`
- Stores `tools` in `self._tools` and returns `self`.
- Tools are expected (by convention) to expose:
  - `name` and `description` attributes (for prompt listing)
  - Either an `invoke(args: dict)` method **or** be callable (`tool(**args)`)

#### `bind(**kwargs)`
- Calls `ChatOpenAI.bind(**clean_kwargs)` but **removes** any kwargs whose key contains `"tool"` (case-insensitive).
- If no supported kwargs remain, returns `self`.

#### `_generate(messages, stop=None, run_manager=None, **kwargs) -> ChatResult`
- Overrides `ChatOpenAI._generate`.
- Behavior:
  - Extracts and concatenates all system-message `content` strings into a `system_prompt`.
  - Uses the last `HumanMessage` content as the user message.
  - If tools are bound, appends:
    - A list of tools (`- {name}: {description}`)
    - Instruction: `To use a tool, respond with: TOOL_CALL: tool_name {json_args}`
  - Replaces `messages` with a single `HumanMessage` containing the constructed prompt.
  - Filters generation kwargs to only: `temperature`, `max_tokens`, `stop`.
  - After first generation, if tools are bound:
    - Scans the model output for `TOOL_CALL:\s*(\w+)\s*({.*?})` (DOTALL)
    - For each match:
      - Parses JSON args
      - Finds tool by `tool.name`
      - Executes via `tool.invoke(args)` if present, else `tool(**args)`
      - Collects results/errors
    - If any tool results exist, re-calls the model with:
      - Original content
      - `Tool results:` block
      - `Provide a final response:`

## Configuration/Dependencies
- Requires:
  - `langchain_openai.ChatOpenAI`
  - `langchain_core` message/output/callback types
- Uses standard library:
  - `json`, `re`
- Runtime configuration is inherited from `ChatOpenAI` (e.g., model, API settings, etc.).

## Usage
```python
from langchain_core.messages import HumanMessage
from naas_abi_core.services.agent.beta.LocalModel import AirgapChatOpenAI

class EchoTool:
    name = "echo"
    description = "Echo back the provided text."
    def invoke(self, args):
        return args["text"]

llm = AirgapChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools([EchoTool()])

# Ask the model; if it emits "TOOL_CALL: echo {...}", the tool will run and a final answer is requested.
result = llm._generate([HumanMessage(content="Use the echo tool with text='hello' and then answer.")])
print(result.generations[0].message.content)
```

## Caveats
- Tool calling is **prompt-based and regex-parsed**, not using OpenAI/LC structured tool-call APIs.
- Only tool names matching `\w+` are recognized, and JSON args must match `{.*?}` in the output.
- Only the last `HumanMessage` is used; multiple user turns are not preserved as separate messages.
- `_generate` is an internal LangChain method; depending on your LangChain usage, you may prefer calling higher-level interfaces that eventually delegate to `_generate`.
