# `model_codec`

## What it is
A small wire codec for LangChain v1 chat messages that:
- Encodes/decodes message payloads as strict JSON (`allow_nan=False`, rejects non-finite numbers).
- Converts between `langchain_core.messages.BaseMessage` and `naas_abi_proto.model_registry.v1.model_registry_pb2.ChatMessage`.
- Validates message types against an allowlist (to avoid unsafe/destructive deserialization patterns).

## Public API
- `MESSAGE_TYPES: set[str]`
  - Allowlisted message types that can be encoded/decoded.

- `encode_json(value) -> bytes`
  - Serializes a Python value to compact UTF-8 JSON bytes.
  - Rejects NaN/Infinity (`allow_nan=False`).

- `decode_json(value: bytes, default=None)`
  - Parses JSON bytes into Python objects.
  - Returns `default` if `value` is empty/falsey.
  - Rejects non-finite numbers (NaN/Infinity) via strict parsing.

- `encode_message(message: BaseMessage) -> pb.ChatMessage`
  - Converts a LangChain `BaseMessage` into a protobuf `ChatMessage`:
    - `type` is taken from `message_to_dict(message)["type"]`
    - `data_json` contains encoded JSON of the message `"data"` field
  - Raises `ValueError` if the message type is not supported.

- `decode_message(message: pb.ChatMessage) -> BaseMessage`
  - Converts a protobuf `ChatMessage` back into a LangChain `BaseMessage`.
  - Validates:
    - `message.type` is supported
    - decoded `data_json` is a `dict`
    - if `data` includes `"type"`, it must match `message.type`
  - Raises `ValueError` on invalid type or malformed data.

## Configuration/Dependencies
- Python stdlib: `json`, `math`
- LangChain: `langchain_core.messages` (`BaseMessage`, `message_to_dict`, `messages_from_dict`)
- Protobuf: `naas_abi_proto.model_registry.v1.model_registry_pb2` (expects `pb.ChatMessage` with fields `type` and `data_json`)

## Usage
```python
from langchain_core.messages import HumanMessage
from naas_abi_sdk.model_codec import encode_message, decode_message

msg = HumanMessage(content="hello")

wire = encode_message(msg)         # pb.ChatMessage
roundtrip = decode_message(wire)   # BaseMessage

print(type(roundtrip).__name__, roundtrip.content)
```

## Caveats
- Only message types in `MESSAGE_TYPES` are accepted; others raise `ValueError`.
- JSON decoding is strict:
  - rejects NaN/Infinity
  - empty/falsey `data_json` returns `None` by default, which will fail `decode_message` validation (expects a `dict`).
