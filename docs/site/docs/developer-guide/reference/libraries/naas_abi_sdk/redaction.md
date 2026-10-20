# `redaction` (secret scrubbing)

## What it is
A small stdlib-only utility that removes common credential values from text (e.g., exception messages, stack traces, telemetry) by replacing them with `"[REDACTED]"` while keeping surrounding context readable.

## Public API
- `REDACTED: str`
  - Constant string used as the replacement value (`"[REDACTED]"`).
- `scrub_secrets(text: str) -> str`
  - Applies a sequence of regex-based redactions to `text` and returns the scrubbed string.

## Configuration/Dependencies
- Dependencies: Python standard library only (`re`).
- No runtime configuration; behavior is defined by internal regex patterns.

## Usage
```python
from naas_abi_sdk.redaction import scrub_secrets

msg = 'Authorization: Bearer eyJabc.def.ghi password=supersecret sk-1234567890abcdef'
print(scrub_secrets(msg))
# Authorization: Bearer [REDACTED] password=[REDACTED] [REDACTED]
```

## Caveats
- Redaction is regex-based:
  - It targets known token/key shapes and common key/value names (e.g., `password`, `token`, `api_key`, `secret`, `credential`, etc.).
  - It may miss secrets that don’t match the implemented patterns.
- Values already equal to `"[REDACTED]"` are not re-redacted for key/value matches.
