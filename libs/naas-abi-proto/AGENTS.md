# Standalone package

Keep this package independent of naas-abi-core, naas-abi, and marketplace.
Transport DTOs are protobuf messages. Do not introduce engine domain objects.
Generated artifacts are checked in; regenerate with `make generate` in the proto package.
Use UV. `make deps`, `make test`, `make lint`, and `make build` are the local gates.
Tests live under tests/. Update the standalone module demonstration when adding endpoints.
`tool_registry/v1` is the serving engine's tool catalog (list, get, search: read only) and `invoke_tool`, which runs an engine tool on the engine (its request repeats `tool/v1.InvokeToolRequest`'s fields and numbers and adds `secret_refs`: config key -> engine secret *name*; keep the two in step). Its
`ToolDefinition` is the portable form of a tool definition, to be reused by the messages for
tools published by modules and for remote execution: add to it, never carry a binding value or a
credential in it (a requirement names a key; `secret` marks it). Limits are enforced by the
serving engine (no Protovalidate) and written in the proto's header: change both together. No
field grants rights: the caller's scopes come from its verified service identity.
`tool/v1` is the call to a tool a module serves (`abi.mod.<project>.<instance>.tool.<name>.invoke`):
JSON arguments, JSON configuration (plain values, never a secret), a JSON result. Its
`ToolDefinition` is `tool_registry/v1`'s, declared in `ModuleDescriptor.tools` (discovery
validates it; `remote` is set by the engine). Its limits are enforced by the serving module and
written in the proto's header: change both together. `tool_registry/v1.InvokeToolRequest` (running
engine tools, ADR 20261023) repeats these messages' fields, never carries a secret value, and gets its
rights from the verified identity like the catalog.
