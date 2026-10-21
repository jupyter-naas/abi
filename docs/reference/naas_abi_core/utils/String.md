# String Utilities (`naas_abi_core.utils.String`)

## What it is
A small set of helper functions for:
- Creating URL-safe IDs from arbitrary strings
- Deriving deterministic UUIDs and SHA-256 hashes from strings
- Normalizing text (lowercasing, removing accents and punctuation)

## Public API
- `create_id_from_string(string: str) -> str`
  - Builds a URL-safe identifier:
    - replaces spaces with `-`
    - lowercases
    - URL-encodes the result (no safe characters)
- `string_to_uuid(input_string: str) -> uuid.UUID`
  - Produces a deterministic `UUID` by:
    - computing SHA-256 of the input
    - using the first 32 hex characters (128 bits) to construct a UUID
- `create_hash_from_string(input_string: str) -> str`
  - Returns the full SHA-256 hex digest of the input string
- `normalize(text: str) -> str`
  - Normalizes text by:
    - lowercasing
    - Unicode NFKD normalization
    - removing punctuation (keeps word chars and whitespace)
    - removing combining diacritics (accents)

## Configuration/Dependencies
- Standard library only:
  - `urllib.parse.quote`
  - `hashlib`, `uuid`
  - `unicodedata`, `re`

## Usage
```python
from naas_abi_core.utils.String import (
    create_id_from_string,
    string_to_uuid,
    create_hash_from_string,
    normalize,
)

print(create_id_from_string("Hello World!"))     # URL-encoded, spaces -> hyphens, lowercased
print(string_to_uuid("my input"))                # deterministic UUID for the given string
print(create_hash_from_string("my input"))       # SHA-256 hex digest
print(normalize("Café — déjà vu!"))              # "cafe  deja vu"
```

## Caveats
- `create_id_from_string` URL-encodes **all** characters (`safe=""`), so characters like `-` will be percent-encoded (e.g., `-` becomes `%2D`).
- `string_to_uuid` is deterministic for the same input but is **not** a standard UUIDv3/v5 namespace-based UUID; it’s derived from SHA-256 truncated to 128 bits.
