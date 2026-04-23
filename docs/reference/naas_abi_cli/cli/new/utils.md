# utils (case conversion helpers)

## What it is
Small utility module providing string case-conversion helpers for generating identifiers from arbitrary text.

## Public API
- `to_pascal_case(text)`
  - Converts `text` into PascalCase by extracting alphanumeric chunks and capitalizing each chunk.
- `to_snake_case(text)`
  - Converts `text` into snake_case by extracting alphanumeric chunks, lowercasing them, and joining with `_`.
- `to_kebab_case(text)`
  - Converts `text` into kebab-case by extracting alphanumeric chunks, lowercasing them, and joining with `-`.

## Configuration/Dependencies
- Standard library:
  - `re` (used to find alphanumeric chunks via regex pattern `r"[A-Za-z0-9]+"`)

## Usage
```python
from naas_abi_cli.cli.new.utils import to_pascal_case, to_snake_case, to_kebab_case

text = "hello world_42!"
print(to_pascal_case(text))  # HelloWorld42
print(to_snake_case(text))   # hello_world_42
print(to_kebab_case(text))   # hello-world-42
```

## Caveats
- Only ASCII letters and digits are considered (`[A-Za-z0-9]+`); other characters are treated as separators and removed.
- Existing capitalization is not preserved:
  - `to_pascal_case("myAPI")` becomes `Myapi` (chunk is capitalized, not title-cased per acronym rules).
