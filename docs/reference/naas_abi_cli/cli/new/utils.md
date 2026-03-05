# `utils` (case conversion helpers)

## What it is
Small set of string helpers for converting arbitrary text into common identifier formats using regex tokenization.

## Public API
- `to_pascal_case(text)`
  - Converts `text` into `PascalCase` by extracting alphanumeric tokens and capitalizing each.
- `to_snake_case(text)`
  - Converts `text` into `snake_case` by extracting alphanumeric tokens, lowercasing them, and joining with `_`.
- `to_kebab_case(text)`
  - Converts `text` into `kebab-case` by extracting alphanumeric tokens, lowercasing them, and joining with `-`.

## Configuration/Dependencies
- Standard library only:
  - `re` for token extraction via `re.findall(r"[A-Za-z0-9]+", text)`.

## Usage
```python
from naas_abi_cli.cli.new.utils import to_pascal_case, to_snake_case, to_kebab_case

s = "Hello, world! v2"
print(to_pascal_case(s))  # HelloWorldV2
print(to_snake_case(s))   # hello_world_v2
print(to_kebab_case(s))   # hello-world-v2
```

## Caveats
- Only ASCII letters and digits are considered tokens (`[A-Za-z0-9]+`).
  - Other characters (spaces, punctuation, underscores, hyphens, non-ASCII letters) act as separators and are not preserved.
