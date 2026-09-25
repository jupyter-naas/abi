# Standalone module demonstration

The worker may import only naas_abi_sdk, naas_abi_proto, their dependencies,
and the standard library. Engine bootstrapping belongs exclusively in engine_host/.
Run `make demo` from this directory. The runner builds wheels and creates an
isolated worker environment without ABI core. All data must stay in a temporary
directory and the broker must listen on loopback. Never use real credentials or
external email/source-control providers for this demo.
Every current RPC endpoint must be exercised or explicitly reported unsupported.
Assertions must verify results and state changes, not just lack of exceptions.

`core_agent_consumer.py` is a separate compatibility example that intentionally
imports core for the existing Agent/IntentAgent classes. It starts no engine and
constructs no provider models; all inference uses SDK proxies to engine_host in
another process. Keep this distinct from the core-free workers above.
