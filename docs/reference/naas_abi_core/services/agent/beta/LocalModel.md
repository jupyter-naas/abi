# AirgapChatOpenAI

## What it is
- `AirgapChatOpenAI` is a minimal wrapper around `langchain_openai.ChatOpenAI` intended for environments like a Docker Model Runner.
- It adds basic “tool” support by:
  - injecting tool descriptions into the prompt, and
  - parsing tool calls from model output and executing them, then
  - re-prompting the model with tool results to produce a final response.

## Public API
### Class: `AirgapChatOpenAI(ChatOpenAI)`
- **`__init__(**kwargs)`**
  - Initializes the underlying `ChatOpenAI` and an internal tool registry (`self._tools`).

- **`bind_tools(tools, **kwargs)`**
  - Stores `tools` on the instance (no additional binding behavior).
  - Returns `self`.

- **`bind(**kwargs)`**
  - Filters out any keyword arguments whose key contains `"tool"` (case-insensitive).
  - Delegates to `ChatOpenAI.bind(**clean_kwargs)` if any remain; otherwise returns `self`.

- **`_generate(messages, stop=None, run_manager=None, **kwargs) -> ChatResult`**
  - Builds a single prompt from:
    - concatenated “system” message contents (detected by string matching `'SystemMessage'` in the message type name), and
    - the last `HumanMessage` content found.
  - If tools are bound:
    - appends an “Available tools” section (`name` and `description`),
    - instructs the model to respond with `TOOL_CALL: tool_name {json_args}` to invoke tools.
  - Calls the base model generation with a restricted set of kwargs: `temperature`, `max_tokens`, `stop`.
  - If tool calls are found in the first generation:
    - executes each tool call by matching `tool.name`,
    - calls `tool.invoke(args)` if present, else calls the tool as a callable `tool(**args)`,
    - re-prompts the model with the tool results appended and asks for a final response.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `langchain_core` message/output/callback types
- Tool objects are expected (by convention) to expose:
  - `name` (string)
  - `description` (string)
  - either `invoke(dict)` or be callable (`__call__(**kwargs)`)

## Usage
```python
from langchain_core.messages import HumanMessage
from naas_abi_core.services.agent.beta.LocalModel import AirgapChatOpenAI

# Define a minimal tool
class AddTool:
    name = "add"
    description = "Add two numbers: expects JSON {\"a\": ..., \"b\": ...}"

    def invoke(self, args):
        return args["a"] + args["b"]

llm = AirgapChatOpenAI(model="gpt-4o-mini", temperature=0)
llm.bind_tools([AddTool()])

# Ask in a way that may trigger the TOOL_CALL format
result = llm._generate([HumanMessage(content="Use the add tool to compute 2 + 3, then answer.")])
print(result.generations[0].message.content)
```

## Caveats
- Tool calls are detected only via the regex pattern: `TOOL_CALL:\s*(\w+)\s*({.*?})` (must be a word-like tool name and JSON object).
- Only the first generation (`result.generations[0]`) is inspected for tool calls.
- System messages are detected by checking whether `'SystemMessage'` appears in `str(type(msg))` (not by importing a `SystemMessage` type).
- Only `temperature`, `max_tokens`, and `stop` are forwarded from `**kwargs` into the underlying `_generate` call; other parameters are dropped.
- This implementation calls the protected method `_generate` directly; typical LangChain usage may prefer higher-level invocation APIs.
