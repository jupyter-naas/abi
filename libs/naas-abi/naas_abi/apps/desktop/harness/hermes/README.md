# Hermes harness adapter

Not implemented. Add `HermesAdapter` here when wiring the Hermes coding-agent runtime.

Steps to add a new harness provider:

1. Create `harness/<provider>/adapter.py` implementing :class:`~desktop.harness.port.HarnessPort`.
2. Add colocated `adapter_test.py` with offline fakes (no real binary, no network).
3. Export the adapter from `harness/<provider>/__init__.py`.
4. Register the provider in `harness/factory.py` (`KNOWN_HARNESSES` + `create_harness` branch).
5. If the adapter needs a low-level client, add it under `core/` (not under `api/`).
