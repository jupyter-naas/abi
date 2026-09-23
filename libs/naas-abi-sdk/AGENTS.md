# Standalone package

Keep this package independent of naas-abi-core, naas-abi, and marketplace.
Transport DTOs are protobuf messages. Public service facades expose Python values
and generated SDK dataclasses, never engine domain objects. See services/AGENTS.md.
Generated artifacts are checked in; regenerate with `make generate` in the proto package.
Use UV. `make deps`, `make test`, `make lint`, and `make build` are the local gates.
Tests live under tests/. Update the standalone module demonstration when adding endpoints.

LangGraph support lives in langgraph.py and is opt-in via [langgraph]; never import
it from package __init__ or make it a base dependency. Only async graph execution
is supported. Keep checkpoint schema versions and pending-write semantics explicit.
Document module namespaces are a programming boundary, not authorization.


AgentProxy and AgentHost use document CAS for durable invocations and non-expiring
conversation claims. Never infer execution ownership from discovery leases or
replay an orphaned run. Core Agent/IntentAgent compatibility belongs in core's
RemoteAgentAdapter; only agent_tools imports optional LangChain dependencies.
Agent streaming preserves string event/data pairs and sequence-based replay.
