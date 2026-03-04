# String

## What it is
Small collection of string utilities for:
- Creating URL-safe IDs
- Deriving deterministic UUIDs and SHA-256 hashes from strings
- Normalizing text (lowercasing, removing accents and punctuation)

## Public API
- `create_id_from_string(string: str) -> str`
  - Produces a URL-safe identifier by lowercasing, replacing spaces with `-`, and URL-encoding the result.
- `string_to_uuid(input_string: str) -> uuid.UUID`
  - Deterministically converts a string into a UUID by hashing with SHA-256 and using the first 32 hex chars.
- `create_hash_from_string(input_string: str) -> str`
  - Returns the SHA-256 hex digest of the input string.
- `normalize(text: str) -> str`
  - Normalizes text by:
    - converting to lowercase
    - Unicode NFKD normalization
    - removing punctuation (keeps word chars and whitespace)
    - removing combining marks (accents)

## Configuration/Dependencies
- Standard library only:
  - `urllib.parse.quote`
  - `hashlib`
  - `uuid`
  - `unicodedata`
  - `re`

## Usage
```python
from naas_abi_core.utils.String import (
    create_id_from_string,
    string_to_uuid,
    create_hash_from_string,
    normalize,
)

s = "Hello World!"
print(create_id_from_string(s))          # "hello-world%21"
print(string_to_uuid(s))                 # UUID derived from SHA-256
print(create_hash_from_string(s))        # SHA-256 hex digest
print(normalize("Café, déjà vu!"))       # "cafe deja vu"
```

## Caveats
- `string_to_uuid` is deterministic (same input → same UUID) but is not a standard UUID namespace scheme; it slices a SHA-256 digest to 32 hex chars.
- `create_id_from_string` only replaces literal spaces (`" "`) with `-` before encoding; other whitespace characters are not replaced.
