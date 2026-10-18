---
sidebar_position: 7
title: "SDK and proto internals"
---

# SDK and proto internals

`naas-abi-proto` and `naas-abi-sdk` are standalone packages: they build without
`naas-abi-core`, and a remote module installs only them. This page points to where
their internals are documented.

| You want | Go to |
|---|---|
| To write a remote module | [Build a Remote Module](/user-guide/build/sdk/build-a-remote-module) |
| How remote modules, discovery and jobs work | [Remote modules and jobs](/developer-guide/architecture/remote-modules), [NATS and the kernel services](/developer-guide/architecture/nats) |
| The SDK's modules (clients, host, runtime, agents, apps, jobs) | [`naas_abi_sdk` reference](/developer-guide/reference/libraries/naas_abi_sdk) |
| The protobuf contracts of the kernel services | [`naas_abi_proto` reference](/developer-guide/reference/libraries/naas_abi_proto/overview) |
| Why they are separate packages | [ADR: standalone protobuf contracts and NATS SDK](https://github.com/jupyter-naas/abi/blob/main/docs/adr/20260922_standalone-proto-sdk.md), [SDK service facades](https://github.com/jupyter-naas/abi/blob/main/docs/adr/20260923_sdk-service-facades-and-module-context.md) |
| To change them | `libs/naas-abi-sdk/AGENTS.md` and `libs/naas-abi-proto/AGENTS.md` in the repository |
| A runnable example | `examples/standalone_module/` in the repository |

## Working on them

```bash
uv run --project libs/naas-abi-proto pytest libs/naas-abi-proto/tests -q
uv run --project libs/naas-abi-sdk pytest libs/naas-abi-sdk/tests -q
```

The SDK never imports `naas_abi_core`; a change to a kernel service's contract starts in the
`.proto` file under `libs/naas-abi-proto`, then in the engine's primary adapter and the SDK's
facade. See [Testing](/developer-guide/contributing/testing#the-sdk-and-proto-packages) for the
integration tests against a real broker and [Releasing](/developer-guide/releasing/release-process)
for how the two are published first.
