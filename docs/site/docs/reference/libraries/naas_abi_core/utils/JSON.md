# JSON (utils)

## What it is
Utility functions to extract and parse a JSON object/array from LLM-style completion text, including markdown ```json fences and common formatting issues.

## Public API
- `extract_json_from_completion(completion_text: str) -> list | dict`
  - Extracts JSON from a completion string.
  - Supports:
    - JSON wrapped in markdown fences (` ```json ... ``` `).
    - Parsing the entire text if no fences exist.
    - Multiple cleanup attempts (remove fences, whitespace, replace single quotes, quote unquoted keys).
    - Fallback raw decoding to find the first `{...}` or `[...]` embedded in prose.
  - Returns parsed `dict`/`list` on success; returns `{}` on failure.

## Configuration/Dependencies
- Standard library:
  - `json` for parsing
  - `re` for cleanup (quoting unquoted keys)
- `naas_abi_core.logger` for debug/error logs during parsing attempts

## Usage
```python
from naas_abi_core.utils.JSON import extract_json_from_completion

text = """
Some preamble text.
```json
{foo: "bar", "n": 1}
```
"""

data = extract_json_from_completion(text)
print(data)  # {'foo': 'bar', 'n': 1}
```

## Caveats
- On failure, returns an empty dict `{}` (not `None`) and logs an error.
- Cleanup heuristics may alter content (e.g., removing whitespace globally, converting `'` to `"`).
- The “unquoted keys” regex is heuristic and may not be safe for all JSON-like strings.
