# `messages`

## What it is
Utilities for working with NATS message sizing and replies in a way that matches what the NATS broker counts against `max_payload` (payload **plus** header block). Also provides a safe reply helper that avoids sending oversized messages.

## Public API
- `message_size(payload: bytes, headers: dict[str, str] | None) -> int`
  - Computes the number of bytes the NATS server counts toward `max_payload`.
  - Includes:
    - `payload` bytes
    - Header block bytes when `headers is not None` (even if empty)
- `reply(msg: Any, data: bytes, headers: dict[str, str] | None = None) -> None` *(async)*
  - Publishes a reply to `msg.reply` using the underlying NATS client (`msg._client`).
  - Validates message size against `client.max_payload` and raises before sending if too large.

## Configuration/Dependencies
- Depends on `nats.errors.MaxPayloadError`.
- Expects `msg` to have:
  - `msg.reply` (reply subject string or falsy)
  - `msg._client` with:
    - `max_payload: int`
    - `publish(subject: str, payload: bytes, headers: dict[str, str] | None)` async method

## Usage
```python
from naas_abi_sdk.messages import message_size, reply

# sizing example
size = message_size(b"hello", headers={"k": "v"})
print(size)

# reply example (inside an async NATS message handler)
async def handler(msg):
    await reply(msg, b"ok", headers={"x": "1"})
```

## Caveats
- `message_size` treats `headers is not None` as “a header block will be sent” (including empty dicts).
- `reply()` raises:
  - `ValueError` if `msg.reply` is missing/falsey.
  - `MaxPayloadError` if the computed size exceeds `msg._client.max_payload` (nothing is sent).
