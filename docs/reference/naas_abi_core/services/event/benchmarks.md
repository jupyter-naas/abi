# EventService — benchmarks

Single-process microbench on macOS arm64 (Apple Silicon, Python 3.11.9). Numbers are median of 3 runs, freshly-created SQLite file per run. Events have 4 string properties on top of `LogProcess`. See [`benchmark.py`](../../../../../libs/naas-abi-core/naas_abi_core/services/event/benchmark.py).

Run yourself:
```bash
uv run python -m naas_abi_core.services.event.benchmark
```

## Results

| Operation | Throughput | Per-op latency |
|---|---:|---:|
| **`publish(...)`** (no bus) | **3,372 /s** | 0.30 ms |
| `publish(...)` (in-memory bus, no subscriber) | 3,405 /s | 0.29 ms |
| `publish(...)` (PythonQueueAdapter bus) | 3,356 /s | 0.30 ms |
| `publish(...)` (in-memory bus, 1 sync subscriber)¹ | 296 /s | 3.4 ms |
| **`query(...)` (eager, full reconstruction)** | **324 /s** | 3.09 ms |
| `iter_query(batch_size=500)` | 330 /s | 3.03 ms |
| `iter_query_for_consumer(...)` | 330 /s | 3.03 ms |
| `adapter.append(...)` (raw SQLite, no RDF) | **26,120 /s** | 0.038 ms |
| `adapter.query(...)` (raw SQLite, no RDF) | **526,804 /s** | 0.002 ms |

¹ Synchronous in-memory bus: the subscriber callback runs inline on the publisher thread. With a real async bus (RabbitMQ, NATS) reconstruction happens in a separate consumer and does not slow down publish. Measure with a real bus to project subscriber-side throughput.

## What the gaps tell us

- **Publish bottleneck is RDF serialization, not SQLite.** Service publish at 3.4k/sec vs. raw `adapter.append` at 26k/sec means ~87% of publish time is in `event.rdf().serialize(format="nt")`. SQLite has ~8x more headroom.
- **Read bottleneck is RDF reconstruction.** Service `query` at 324/sec vs. raw `adapter.query` at 527k/sec — three orders of magnitude. Every event triggers an rdflib `Graph.parse` plus a SPARQL `SELECT ?p ?o` to rebuild the Pydantic instance. This is the single hottest path.
- **Bus overhead is essentially free** (when the bus itself isn't slow). In-memory and PythonQueueAdapter both add ~0% overhead for fire-and-forget publishes. RabbitMQ adds network latency but doesn't change throughput much in async fire-and-forget mode.

## What to expect in production

Single Python process, single thread, fire-and-forget publishes, no live subscribers in the same process:

| Sustained rate | Verdict |
|---|---|
| **< 1,000 events/sec** | Comfortable. No tuning needed. |
| **1,000 – 3,000 events/sec** | Works. RDF serialization is the bottleneck. |
| **3,000 – 5,000 events/sec** | At the limit of one Python process. Spread across processes (each owns its own connection, WAL serializes file writes). |
| **> 5,000 events/sec sustained** | Optimize first (see below); otherwise swap the adapter. |
| **> 25,000 events/sec** | SQLite raw can do it, but Python + RDF can't — move to Postgres or a real log store. |

For reads, plan on **~300 events/sec per reader thread** at full RDF reconstruction. If you're doing analytics over millions of events, drop to `adapter.query` (raw `StoredEvent` records) — that's 527k/sec.

## If you outgrow these numbers

In order of effort, before swapping the adapter:

1. **Drop the per-call `threading.Lock`** — currently we serialize all adapter operations. SQLite WAL allows concurrent readers; let reads run lockless. Probably 2–3x on read-heavy workloads.
2. **Replace RDF n-triples with JSON-serialized Pydantic** as the storage payload. Keeps SPARQL-via-`from_iri` for the cases that need it, but cuts the common-path serialize / parse cost by an order of magnitude. Probably 5–10x publish, 10–20x read.
3. **Batch publishes** — add `publish_many(events)` that does a single `INSERT ... VALUES (...), (...)`. ~5x for batched workloads.
4. **Skip the live broadcast for high-frequency event types** that no one subscribes to. Pass `broadcast=False` to publish. Currently the bus call is cheap, but it scales with subscriber count.

Once those tap out, the `IEventAdapter` interface lets you swap to Postgres (`LISTEN/NOTIFY` + a real log table) or a Kafka-backed adapter without touching caller code.

## Caveats

- These are microbench numbers — single-thread, in-temp-directory SQLite, no disk pressure, no concurrent readers. Real workloads with concurrent processes or backing-up writers will be slower.
- Event payload size matters. Our bench event has 4 fields ≈ ~1 KB n-triples. Bigger events scale serialization cost roughly linearly.
- Apple Silicon is fast. On a typical x86 cloud VM, expect ~50–70% of these numbers.
