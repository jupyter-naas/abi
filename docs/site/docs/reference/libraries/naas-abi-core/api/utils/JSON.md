# JSON

## What it is
Utility function to extract and parse a JSON object/array from a text completion, including content wrapped in Markdown code fences (```json ... ```), with a few cleanup attempts.

## Public API
- `extract_json_from_completion(completion_text: str) -> list | dict`
  - Extracts JSON from `completion_text` (optionally inside a ```json fenced block) and attempts to `json.loads()` it.
  - On repeated parse failures, logs and returns `{}`.

## Configuration/Dependencies
- Standard library:
  - `json` for parsing
  - `re` for one cleanup pass (quoting unquoted keys)
- Internal:
  - `naas_abi_core.logger` used for debug/error logs

## Usage
```python
from naas_abi_core.utils.JSON import extract_json_from_completion

text = """Here is the result:
```json
{"ok": true, "items": [1, 2, 3]}
```
"""

data = extract_json_from_completion(text)
print(data["ok"])          # True
print(data["items"])       # [1, 2, 3]
```

## Caveats
- If no ```json fence is found, the entire input is treated as JSON.
- Cleanup attempts are limited and may change content (e.g., removing whitespace, replacing `'` with `"`).
- If all parse attempts fail, the function returns an empty dict `{}` (even though the return type allows `list`).
