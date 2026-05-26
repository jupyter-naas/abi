# EventService — benchmarks

Single-process microbench on macOS arm64 (Apple Silicon). Numbers are median of 3 runs, freshly-created SQLite file per run. Events have 4 string properties on top of `LogProcess`. See [`benchmark.py`](./benchmark.py).

Run yourself:
```bash
uv run python -m naas_abi_core.services.event.benchmark
```

## Results (JSON codec — current)

Python 3.12.6:

| Operation | Throughput | Per-op latency |
|---|---:|---:|
| **`publish(...)`** (no bus) | **11,131 /s** | 0.09 ms |
| `publish(...)` (in-memory bus, no subscriber) | 11,488 /s | 0.09 ms |
| `publish(...)` (PythonQueueAdapter bus) | 8,618 /s | 0.12 ms |
| `publish(...)` (in-memory bus, 1 sync subscriber)¹ | 8,834 /s | 0.11 ms |
| **`query(...)` (eager, full reconstruction)** | **98,227 /s** | 0.010 ms |
| `iter_query(batch_size=500)` | 99,018 /s | 0.010 ms |
| `iter_query_for_consumer(...)` | 101,465 /s | 0.010 ms |
| `adapter.append(...)` (raw SQLite, no codec) | 15,732 /s | 0.064 ms |
| `adapter.query(...)` (raw SQLite, no codec) | 560,828 /s | 0.002 ms |

### Versus the previous RDF-canonical codec

For reference, the same benchmark when events were stored as RDF n-triples (initial design, Python 3.11.9):

| Operation | RDF (initial) | JSON (current) | Speedup |
|---|---:|---:|---:|
| `publish` (no bus) | 3,372 /s | 11,131 /s | **3.3×** |
| `publish` (1 live subscriber) | 296 /s | 8,834 /s | **30×** |
| `query` (eager) | 324 /s | 98,227 /s | **303×** |
| `iter_query` | 330 /s | 99,018 /s | **300×** |

The bottleneck moved from RDF (rdflib serialize + SPARQL parse) to actual storage I/O. Reads in particular are now bound by SQLite + Pydantic deserialization rather than by graph manipulation.

¹ Synchronous in-memory bus: the subscriber callback runs inline on the publisher thread. With a real async bus (RabbitMQ, NATS) reconstruction happens in a separate consumer and does not slow down publish. Measure with a real bus to project subscriber-side throughput.

## What the gaps tell us

- **Publish is now within ~30% of raw `adapter.append`.** The remaining gap is Pydantic + JSON encoding. SQLite is no longer the bottleneck.
- **Reads run at ~100k/sec with full Pydantic reconstruction**, which is ~17% of raw `adapter.query` — Pydantic's `model_validate_json` is the dominant cost from here on.
- **Bus overhead is essentially free** when the bus itself isn't slow. In-memory bus adds ~0% overhead; PythonQueueAdapter adds ~25% because it has its own SQLite-backed queue (write contention).
- **Live subscribers no longer collapse throughput.** Subscriber-side reconstruction is now ~0.1 ms, so a synchronous subscriber barely shows up.

## What to expect in production

Single Python process, single thread, fire-and-forget publishes:

| Sustained rate | Verdict |
|---|---|
| **< 5,000 events/sec** | Comfortable. No tuning needed. |
| **5,000 – 10,000 events/sec** | Works. Pydantic encoding is the bottleneck. |
| **10,000 – 15,000 events/sec** | At the limit of one Python process. Spread across processes (each owns its own connection, WAL serializes file writes). |
| **> 15,000 events/sec sustained** | Add `publish_many` for batched inserts, or swap the adapter to Postgres / a real log store. |

For reads, plan on **~100k events/sec per reader thread** with full reconstruction. For analytics over millions of events, drop to `adapter.query` (raw `StoredEvent` records) at ~560k/sec — or push filtering down via the `filter=` dict, which compiles to indexed JSON1 SQL.

## If you outgrow these numbers

In order of effort, before swapping the adapter:

1. **Drop the per-call `threading.Lock`** — currently we serialize all adapter operations. SQLite WAL allows concurrent readers; let reads run lockless. Probably 2–3× on concurrent read-heavy workloads.
2. **Batch publishes** — add `publish_many(events)` that does a single `INSERT ... VALUES (...), (...)`. ~5× for batched workloads.
3. **Declare JSON1 indexes for hot filter paths** — `CREATE INDEX ix_user_id ON events(json_extract(payload, '$.user_id'))`. Turns a filter scan into an index lookup; bounded by index lookup cost regardless of table size.
4. **Skip the live broadcast for high-frequency event types** that no one subscribes to. Pass `broadcast=False` to publish.

Once those tap out, the `IEventAdapter` interface lets you swap to Postgres (`LISTEN/NOTIFY` + JSONB) or a Kafka-backed adapter without touching caller code.

## Caveats

- These are microbench numbers — single-thread, in-temp-directory SQLite, no disk pressure, no concurrent readers. Real workloads with concurrent processes or backing-up writers will be slower.
- Event payload size matters. Our bench event has 4 fields ≈ ~1 KB n-triples. Bigger events scale serialization cost roughly linearly.
- Apple Silicon is fast. On a typical x86 cloud VM, expect ~50–70% of these numbers.
