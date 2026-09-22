# Standalone package

Keep this package independent of naas-abi-core, naas-abi, and marketplace.
Transport DTOs are protobuf messages. Do not introduce engine domain objects.
Generated artifacts are checked in; regenerate with `make generate` in the proto package.
Use UV. `make deps`, `make test`, `make lint`, and `make build` are the local gates.
Tests live under tests/. Update the standalone module demonstration when adding endpoints.

LangGraph support lives in langgraph.py and is opt-in via [langgraph]; never import
it from package __init__ or make it a base dependency. Only async graph execution
is supported. Keep checkpoint schema versions and pending-write semantics explicit.
Document module namespaces are a programming boundary, not authorization.
