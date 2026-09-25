# naas-abi-proto

The canonical ABI v1 protobuf schemas, generated Python classes, and type stubs.
The only runtime dependency is `protobuf`. This package does not import ABI core,
the SDK, NATS, domain implementations, or engine frameworks.

```python
from naas_abi_proto.object_storage.v1 import object_storage_pb2
request = object_storage_pb2.PutObjectRequest(prefix="demo", key="hello", content=b"world")
```

Schemas live in `naas_abi_proto/<service>/v1/`. Wire packages (`abi.<service>.v1`),
field numbers, message names, and NATS subjects are unchanged by extraction.
Core's old Python modules re-export these exact classes; old `.proto` files import
publicly from this package. Compile legacy schemas with both package roots in the
include path. Do not regenerate duplicate definitions under the old namespace.

Generated files are checked in and included in both wheels and source distributions.
Run `make generate` with UV to use pinned `grpcio-tools==1.78.0`, isolated from the
engine's dependency environment. It regenerates Python files and SDK clients,
then applies the repository formatter. Run `make deps test lint build` locally.

Only additive changes belong in v1. Breaking changes require v2 schemas and subjects.
This extraction preserves existing validation semantics: v1 currently has no
Protovalidate annotations. The engine's adapters remain the validation boundary;
this package does not claim client-side semantic validation. Introducing annotations
and the corresponding runtime is a separate contract change.
