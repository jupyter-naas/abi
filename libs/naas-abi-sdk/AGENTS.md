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

Model proxies/codec import optional LangChain through [models]. Never import them
from package __init__ or the base service catalog. Registry facades lazy-load
proxies on model lookup. ModelConnection keeps NATS I/O on the resolving loop;
sync callers must use another thread. Stream IDs are caller-bound, ephemeral,
sequence-checked handles; never retry inference or cursor reads automatically.

`transfer.py` owns shared chunk framing and session cleanup. Object facades stream
bounded reads; model proxies assemble logical protobuf frames. Preserve owner-loop
execution, sequence checks, caller binding and no automatic replay. Per-exchange
RPC timeouts must not impose a total model-generation deadline.
