# Standalone package

Keep this package independent of naas-abi-core, naas-abi, and marketplace.
Transport DTOs are protobuf messages. Do not introduce engine domain objects.
Generated artifacts are checked in; regenerate with `make generate` in the proto package.
Use UV. `make deps`, `make test`, `make lint`, and `make build` are the local gates.
Tests live under tests/. Update the standalone module demonstration when adding endpoints.
`tool_registry/v1` is the serving engine's tool catalog, read only (list, get, search). Its
`ToolDefinition` is the portable form of a tool definition, to be reused by the messages for
tools published by modules and for remote execution: add to it, never carry a binding value or a
credential in it (a requirement names a key; `secret` marks it). Limits are enforced by the
serving engine (no Protovalidate) and written in the proto's header: change both together. No
field grants rights: the caller's scopes come from its verified service identity.
