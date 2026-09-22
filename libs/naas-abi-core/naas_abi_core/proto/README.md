# Legacy protobuf import paths

Canonical contracts now live in `libs/naas-abi-proto/naas_abi_proto`.
These Python modules re-export the standalone package's generated classes so
existing core callers remain compatible. Install `naas-abi-core[nats]` to include
the optional proto package. Legacy `.proto` files forward with `import public`;
include both the core and standalone package roots when compiling downstream schemas.

Do not generate duplicate classes here. Regenerate from `libs/naas-abi-proto`
with `make generate`. Wire packages, field numbers, message names, and NATS
subjects are unchanged. See that package's README for validation and versioning.
