# `secrets_crypto`

## What it is
Utility functions for encrypting and decrypting secret values using `cryptography.fernet.Fernet`, with the encryption key derived from `settings.secret_key` (SHA-256 hashed and URL-safe base64 encoded).

## Public API
- `get_fernet() -> Fernet`
  - Builds and returns a `Fernet` instance using a key derived from `settings.secret_key`.
- `encrypt_secret_value(value: str) -> str`
  - Encrypts a UTF-8 string and returns the encrypted token as a UTF-8 string.
- `decrypt_secret_value(encrypted_value: str) -> str`
  - Decrypts a Fernet token string and returns the original UTF-8 string.
  - Raises if the token is invalid or decryption fails.
- `try_decrypt_secret_value(encrypted_value: str) -> str | None`
  - Attempts to decrypt; returns plaintext on success, otherwise `None`.
  - Catches `InvalidToken` and any other `Exception`.

## Configuration/Dependencies
- Depends on:
  - `cryptography.fernet.Fernet`
  - `naas_abi.apps.nexus.apps.api.app.core.config.settings`
- Required setting:
  - `settings.secret_key` (string), used to derive the Fernet key:
    - `sha256(secret_key).digest()` → `base64.urlsafe_b64encode(...)`

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.secrets_crypto import (
    encrypt_secret_value,
    decrypt_secret_value,
    try_decrypt_secret_value,
)

token = encrypt_secret_value("my-secret")
plaintext = decrypt_secret_value(token)
maybe_plaintext = try_decrypt_secret_value("not-a-valid-token")  # None
```

## Caveats
- Changing `settings.secret_key` will make previously encrypted values undecryptable.
- `decrypt_secret_value` may raise on invalid tokens; use `try_decrypt_secret_value` to avoid exceptions.
- `try_decrypt_secret_value` suppresses all exceptions (not only `InvalidToken`), returning `None` on any failure.
