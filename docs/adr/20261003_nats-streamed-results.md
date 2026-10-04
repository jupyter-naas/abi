# Streamed results for large reads over NATS

Status: Accepted

Date: 2026-10-03

## Context

RPC overflow (20261003_nats-rpc-overflow.md) lets any reply above the broker
limit through, up to 256 MiB, but the value is still built whole on both ends:
the backend's response, the decoded result, the serialized reply, the client's
copy. Whole-graph reads and large SPARQL results are the main case: the triple
store adapters read the HTTP body into memory and parse it, the primary
materializes an rdflib result into one `QueryResult`, and the client decodes it
back. Memory grows with the result, and nothing above 256 MiB can be read.

## Decision

Large result sets are streamed end to end, with memory bounded by one batch,
starting with the triple store.

- **Domain API.** `ITripleStorePort` and `TripleStoreService` gain
  `query_stream(sparql)` and `export(graph_name=None)`, both context managers.
  `query_stream` yields a `QueryStream`: `result_type`, `vars`, `ask_answer`,
  and lazy `rows` (dicts of rdflib terms, unbound variables absent) or
  `triples`. `export` yields the triples of one named graph, or of the store as
  `get()` returns it. Read them once, inside the `with`; leaving it releases
  the backend response or the transfer session.
- **Defaults.** Both methods have working defaults on the port (the
  materialized `query` / `get`), so every adapter keeps working. Adapters that
  can stream override them: the SPARQL HTTP adapters (Apache Jena TDB2,
  Oxigraph) request TSV results and N-Triples and parse them line by line
  (`adaptors/secondary/base/sparql_stream.py`); the embedded Oxigraph adapter
  iterates pyoxigraph's lazy results.
- **Wire.** The NATS primary hosts `transfer/v1` sessions on
  `abi.svc.triple_store.v1.transfer` (operations `query` and `export`), with no
  new protobuf messages. `query` metadata is a `QueryRequest`; its first frame
  is a `QueryResult` header (result type, SELECT variables or the ASK answer),
  then each frame is a batch: a `SelectResult` holding only rows for SELECT,
  N-Triples lines for CONSTRUCT and DESCRIBE. `export` metadata is the graph
  name (empty for the whole store) and every frame is N-Triples lines. Batches
  close at about 256 KiB; the backend is read on a worker thread one batch at a
  time, and the transfer queue holds at most two chunks.
- **Clients.** The core NATS client exposes the same context managers and
  decodes frames as the caller iterates; against an engine without the
  transfer endpoint it falls back to the unary call. The SDK triple store
  facade exposes async iterators over the same protocol.
- Blank nodes keep their identity across batches within one stream.

The same shape (a domain-level iterator, a default that materializes, a
transfer operation per stream, batched frames) applies to the next services:
dataset query results and write batches, vector listing, event and activity
queries, and document `find` pages.

## Consequences

- A whole-graph read or a large SELECT costs memory for one batch per hop, not
  for the result, and is not capped by the overflow limit.
- A stream is single-use and holds a backend response (or a transfer session,
  idle-expired after 60 seconds) until the `with` exits; slow consumers must
  keep reading.
- An error after the first rows (for example Fuseki aborting mid-response)
  raises from the iterator; rows already yielded stay valid. Nothing is
  retried once rows have been yielded.
- Results arrive in backend order, not sorted, unless the query asks for it.
- Callers move to the streaming API one by one; `get()` and `query()` keep
  their behaviour (bounded by RPC overflow).

## Status of the rollout

- Triple store: `query_stream` and `export`, every layer (above).
- Dataset: `query_stream(sql, namespace, snapshot_id)` yields a `RowStream`
  (`columns`, lazy `rows`). DuckLake fetches 1,000 rows at a time on the
  stream's own cursor; the wire is `abi.svc.dataset.v1.transfer` operation
  `query`, a `QueryResult` with the columns, then `QueryResult`s with rows only
  (one JSON object per row, as the unary reply: see the dataset AGENTS.md).
  Core client and SDK facade, with the unary fallback.
- Dataset writes: `write_stream(name, rows, ...)` takes an iterator of rows,
  commits them in one snapshot (all or none). The client uploads one JSON
  object per line on the same transfer prefix, operation `write`; the transfer
  host spools the upload to disk and the primary feeds it line by line to the
  adapter; the one reply frame is the `WriteResponse`. DuckLake stages the rows
  in batches to a local Parquet file, so transaction retries replay the file.
- Not yet: vector listing, event and activity queries, byte-bounded document
  `find` pages.
