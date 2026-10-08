# SDK service proxies

Expose async methods with core service argument names and defaults, while keeping
all runtime imports independent of ABI core. Protobuf conversion belongs here;
module business code receives Python values and SDK DTOs. User-requested service
facades supersede the original protobuf-only module API. Low-level clients remain
available through the explicitly named engine.rpc boundary.

DTOs in models.py are generated from protobuf descriptors. Regenerate with
`uv run python tools/generate_services.py` from the SDK project. Generated service
methods use core source signatures at generation time only. Cover behavior with
conversion tests and the isolated ergonomic module demo. Unsupported framework
operations must fail explicitly. Do not replay failed mutations.

`TripleStoreService.query_stream` and `export` are async context managers over
the engine's `transfer/v1` streams (docs/adr/20261003_nats-streamed-results.md):
`rows` and `triples` are async iterators read once inside the block, frames are
fetched as they are iterated, and an engine without the stream endpoint falls
back to the unary `query`/`get`.
