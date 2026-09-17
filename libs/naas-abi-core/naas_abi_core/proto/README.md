# naas_abi_core/proto/

Protobuf contracts for kernel domain services exposed over NATS. See
`docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md` ("Protobuf contract shapes",
"Decisions locked in") for why these live here rather than a standalone package, and why they're
hand-designed per kernel domain rather than auto-derived (that auto-derivation problem is scoped
to arbitrary module components — Agent/Workflow/Pipeline/Tool — which is Stage 2, not this).

## Layout

- `common/v1/common.proto` — `CallContext`/`CallError`, embedded in every domain's requests/responses.
- `<domain>/v1/<domain>.proto` — one file per kernel domain, mirroring that domain's Python port
  1:1 (e.g. `object_storage/v1/object_storage.proto` mirrors `ObjectStoragePort.py`).

Generated `*_pb2.py`/`*_pb2.pyi` files are committed, not regenerated at install/build time — this
is a small, slow-changing contract set, and committing avoids every developer/CI environment
needing a correctly-pinned `protoc` just to run the test suite.

## Regenerating after editing a `.proto` file

`grpcio-tools` is deliberately **not** a workspace dependency — it depends on `protobuf>=7.35`,
which conflicts with `dagster`'s `protobuf<7` pin in this same project. Run it isolated via `uvx`,
pinned to the `protobuf` version this project actually runs (check with `uv pip show protobuf`),
so the generated code's minimum-runtime-version check matches what's actually installed:

```sh
cd libs/naas-abi-core
uvx --from "grpcio-tools" --with "protobuf==$(uv run python -c 'import google.protobuf; print(google.protobuf.__version__)')" \
  python -m grpc_tools.protoc \
  -I . \
  --python_out=. \
  --pyi_out=. \
  naas_abi_core/proto/common/v1/common.proto \
  naas_abi_core/proto/object_storage/v1/object_storage.proto
```

The `-I .` (include root = the `naas-abi-core` package root, not `naas_abi_core/proto/`) is what
makes the generated imports come out as `from naas_abi_core.proto.common.v1 import common_pb2`
instead of a bare `from common.v1 import common_pb2` that doesn't match this package's actual
import path — `import` statements inside `.proto` files must be written relative to that same
root (e.g. `import "naas_abi_core/proto/common/v1/common.proto";`), not relative to the file
doing the importing.

## Versioning

Additive fields only within a `v1` package; a breaking change gets a new `v2` package and a new
NATS subject (`abi.svc.<domain>.v2.<method>`) running alongside `v1`, not a replacement — see the
RFC's versioning section for why (same side-by-side pattern as module extraction).
