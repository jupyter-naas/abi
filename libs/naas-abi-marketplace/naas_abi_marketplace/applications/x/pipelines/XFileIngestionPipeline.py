"""Stream tweets out of a dataset file in object storage into the X graph.

The companion to :class:`XSearchRecentTweetsPipeline` for the bulk case:
where the search pipeline asks X v2 for a few hundred recent tweets per
tick, this one consumes a previously-collected dataset that was dropped
into object storage — typically a JSON file with millions of tweets.

The hard constraint is memory: a 12 GB JSON tweet dump must NOT be
buffered. So:

  * the file is opened through :meth:`ObjectStorageService.get_object_stream`,
    not :meth:`get_object`, so the body is read incrementally from the
    backing FS / S3 stream;
  * NDJSON is detected by sniffing the first non-whitespace byte and
    parsed line by line;
  * JSON arrays are streamed by ``ijson`` (``items(stream, "item")`` /
    ``items(stream, "data.item")``) — never materialised as one big
    Python list;
  * ``gzip``-compressed files are detected by magic bytes and decompressed
    on the fly through ``gzip.GzipFile``;
  * tweets are accumulated in a per-batch :class:`rdflib.Graph` and
    flushed with ``triple_store.insert`` every ``batch_size`` records, so
    the resident set stays bounded by *one batch*, not the file size.

Per file the pipeline emits a tiny provenance subgraph:

.. code-block:: turtle

    x:TweetFileImport/<sha256>  a x:TweetFileImport ;
        rdfs:label "Tweet File Import <key>" ;
        x:imports_file <file_uri> ;
        x:produces_search_result <result_set_uri> ;
        x:created <when> ;
        x:record_count <n> .

    x:TweetFile/<sha256>  a x:TweetFile ;
        rdfs:label "<key>" ;
        x:sha256 "<sha256>" ;
        x:object_storage_prefix "<prefix>" ;
        x:object_storage_key "<key>" ;
        x:file_size_bytes <bytes> .

Dedupe is sha256-based: before downloading a file we ASK whether an
``x:TweetFile`` with that ``x:sha256`` already exists in the named
graph, and skip ingestion if it does. That means re-running the sensor
on a folder is always a no-op (modulo gauging which files are new).
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import IO, Annotated, BinaryIO, Iterator, Optional, cast

import ijson
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi.ontologies.modules.ABIOntology import TemporalInstant
from naas_abi_core import logger
from naas_abi_core.pipeline import (
    Pipeline,
    PipelineConfiguration,
    PipelineParameters,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    IObjectStorageDomain,
)
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    SearchInterval,
    SearchResultSet,
    TweetFile,
    TweetFileImport,
)
from naas_abi_marketplace.applications.x.pipelines.utils import (
    XTweetGraphBuilder,
    uri_for,
)
from pydantic import Field
from rdflib import Graph, Namespace, URIRef


@dataclass
class XFileIngestionPipelineConfiguration(PipelineConfiguration):
    """Wiring needed to run :class:`XFileIngestionPipeline`.

    Attributes:
        object_storage: Source of the file bytes. Must support
            :meth:`get_object_stream` (added to the port in this PR).
        triple_store: Target named graph + dedupe ASK destination.
        graph_name: Named graph IRI to insert into.
        batch_size: Records per INSERT round trip. Larger = fewer round trips
            but more memory; smaller = lower memory ceiling.
    """

    object_storage: IObjectStorageDomain
    triple_store: ITripleStoreService
    graph_name: URIRef
    batch_size: int = 500


class XFileIngestionPipelineParameters(PipelineParameters):
    prefix: Annotated[
        str,
        Field(
            description=(
                "Object-storage prefix the file lives under, e.g. "
                "'x/uploads'. Combined with ``key`` to address the file."
            ),
            example="x/uploads",
        ),
    ]
    key: Annotated[
        str,
        Field(
            description=(
                "Object key under *prefix*. Supported extensions: ``.json`` "
                "(array of tweets OR NDJSON, auto-detected), ``.ndjson`` "
                "(one tweet per line), ``.json.gz`` / ``.ndjson.gz`` "
                "(gzipped variants)."
            ),
            example="archive-2026-06-03.ndjson",
        ),
    ]
    query: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Optional search query string that was used to collect "
                "the tweets in this file (e.g. 'Roland Garros lang:en'). "
                "When provided a SearchQuery individual is linked to the "
                "TweetFileImport process in the knowledge graph."
            ),
        ),
    ] = None
    search_start: Annotated[
        Optional[datetime],
        Field(
            default=None,
            description=(
                "Optional UTC start of the time window covered by the "
                "tweet file. Used to populate the SearchInterval node."
            ),
        ),
    ] = None
    search_end: Annotated[
        Optional[datetime],
        Field(
            default=None,
            description=(
                "Optional UTC end of the time window covered by the "
                "tweet file. Used to populate the SearchInterval node."
            ),
        ),
    ] = None
    delete_after_ingest: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, delete the source object after ingestion "
                "completes. Use carefully — re-runs become impossible."
            ),
        ),
    ] = False


class XFileIngestionPipeline(Pipeline):
    """Streams an X-format JSON tweet dump into the configured named graph."""

    __configuration: XFileIngestionPipelineConfiguration

    def __init__(self, configuration: XFileIngestionPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self._namespace = ABIModule.get_instance().configuration.ontology_namespace
        self.namespace = Namespace(self._namespace)

    # ----- Top-level run --------------------------------------------------------

    def run(self, parameters: XFileIngestionPipelineParameters) -> Graph:  # type: ignore[override]
        if not isinstance(parameters, XFileIngestionPipelineParameters):
            raise ValueError(
                "Parameters must be of type XFileIngestionPipelineParameters"
            )

        prefix = parameters.prefix
        key = parameters.key

        # ----- Step 1: sha256 hash of the file (one streaming pass) ------------
        # We compute the sha256 in a first streaming pass so we can dedupe
        # without parsing anything yet. For a 12 GB file this is a
        # straight read-and-discard at SSD/network speed; cheap relative
        # to the parse-and-insert pass that follows.
        sha256, size_bytes = self._sha256_and_size(prefix, key)
        logger.info(
            f"XFileIngestionPipeline: file {prefix}/{key} -> "
            f"sha256={sha256}, size={size_bytes} bytes"
        )

        if self._already_ingested(sha256):
            logger.info(
                f"XFileIngestionPipeline: sha256 {sha256} already ingested; skipping"
            )
            return Graph()

        import_start = datetime.now(timezone.utc)

        # ----- Step 2: provenance subgraph (file + import process + interval)
        provenance, result_set_uri, interval_uri = self._build_provenance_graph(
            prefix=prefix,
            key=key,
            sha256=sha256,
            size_bytes=size_bytes,
            import_start=import_start,
        )
        self.__configuration.triple_store.insert(
            provenance, self.__configuration.graph_name
        )

        # ----- Step 3: stream the tweets through the shared graph builder ------
        builder = XTweetGraphBuilder(
            self.__configuration.triple_store, self.__configuration.graph_name
        )
        batch_size = self.__configuration.batch_size
        batch = Graph()
        batch.bind("x", self.namespace)
        batch_count = 0
        total_count = 0

        for record in self._iter_records(prefix, key):
            try:
                batch += builder.build_tweet(record, source_set_uri=result_set_uri)
            except KeyError:
                # Records without `id` are unusable. Log + skip; don't tank
                # the whole 12 GB import for one malformed row.
                logger.warning(
                    f"XFileIngestionPipeline: skipping record without id: "
                    f"keys={list(record.keys())[:10]}"
                )
                continue
            batch_count += 1
            total_count += 1
            if batch_count >= batch_size:
                self._flush(batch, total_count)
                batch = Graph()
                batch.bind("x", self.namespace)
                batch_count = 0

        if batch_count:
            self._flush(batch, total_count)

        # ----- Step 4: stamp record_count + close the temporal interval --------
        import_end = datetime.now(timezone.utc)
        end_instant_uri = self._instant_uri(import_end)

        final = Graph()
        final.bind("x", self.namespace)
        final += TweetFileImport(
            _uri=self._uri("TweetFileImport", sha256),
            record_count=total_count,
        ).rdf()
        final += SearchResultSet(
            _uri=result_set_uri,
            result_count=total_count,
        ).rdf()
        final += TemporalInstant(
            _uri=end_instant_uri,
            label=import_end.isoformat(),
        ).rdf()
        final += SearchInterval(
            _uri=interval_uri,
            search_ended_at=[URIRef(end_instant_uri)],
        ).rdf()
        self.__configuration.triple_store.insert(final, self.__configuration.graph_name)

        logger.info(
            f"XFileIngestionPipeline: ingested {total_count} tweets from "
            f"{prefix}/{key} (sha256={sha256})"
        )

        if parameters.delete_after_ingest:
            self.__configuration.object_storage.delete_object(prefix, key)
            logger.info(f"XFileIngestionPipeline: deleted source object {prefix}/{key}")

        return final

    # ----- Streaming primitives -------------------------------------------------

    def _sha256_and_size(self, prefix: str, key: str) -> tuple[str, int]:
        """Single streaming pass that returns (sha256_hex, size_in_bytes)."""
        h = hashlib.sha256()
        size = 0
        with self.__configuration.object_storage.get_object_stream(prefix, key) as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
                size += len(chunk)
        return h.hexdigest(), size

    def _iter_records(self, prefix: str, key: str) -> Iterator[dict]:
        """Yield individual tweet dicts from *prefix/key*.

        Accepts three shapes (auto-detected by sniffing the first
        non-whitespace byte), so we can ingest either raw tweet dumps or
        the verbatim output of X v2 ``GET /2/tweets/search/recent``:

        1. **NDJSON of envelopes** — most useful for "JSONL of query
           results". Each line is one X v2 response of the form
           ``{"data": [...tweets...], "meta": {...}}``. Every tweet inside
           ``data`` is yielded.
        2. **NDJSON of tweets** — each line is a bare tweet dict with
           ``id`` + ``text``. Yielded as-is.
        3. **JSON array** — either an array of envelopes or an array of
           tweets, streamed item-by-item via ``ijson``. Same per-item
           detection as the NDJSON case.

        Gzip-compressed variants (``.gz`` suffix or ``0x1f 0x8b`` magic
        bytes) are decompressed on the fly.
        """
        for raw_record in self._iter_raw_records(prefix, key):
            yield from _unwrap_envelope(raw_record)

    def _iter_raw_records(self, prefix: str, key: str) -> Iterator[dict]:
        """Yield the top-level JSON objects in the file (no envelope unwrap).

        ``_iter_records`` then takes care of the envelope semantics. Kept
        separate so the format-detection logic stays focused on bytes,
        not on schema.
        """
        with self.__configuration.object_storage.get_object_stream(prefix, key) as raw:
            stream = self._maybe_decompress(raw, key)
            first = self._peek_nonblank_byte(stream)
            if first == b"[":
                # JSON array — ijson incrementally yields each top-level item.
                # We re-prepend the byte ijson consumed via _PrependByte.
                wrapped = cast(IO[bytes], _PrependByte(first, stream))
                yield from ijson.items(wrapped, "item", use_float=True)
            elif first == b"{":
                # NDJSON: each line is its own JSON object — either a v2
                # envelope or a bare tweet. We read line by line; the
                # unwrap step in _iter_records handles either shape.
                wrapped = cast(IO[bytes], _PrependByte(first, stream))
                first_line = self._read_line(wrapped)
                try:
                    yield json.loads(first_line)
                except json.JSONDecodeError:
                    # Not NDJSON — the first non-whitespace byte was `{`
                    # but the rest of the file isn't a line-delimited
                    # object stream. Treat the whole file as one big
                    # JSON object and stream tweets out of common
                    # nesting paths (X v2 envelope / "tweets" wrapper).
                    yield from self._iter_records_via_ijson(prefix, key)
                    return
                for line in self._iter_lines(wrapped):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        logger.warning(
                            f"XFileIngestionPipeline: skipping malformed "
                            f"NDJSON line: {exc}"
                        )
            elif first == b"":
                return  # empty file
            else:
                raise ValueError(
                    f"Unexpected first character {first!r} in {prefix}/{key}; "
                    "expected '[' (JSON array) or '{' (JSON object / NDJSON)"
                )

    def _iter_records_via_ijson(self, prefix: str, key: str) -> Iterator[dict]:
        """Hunt for a tweet list under common nesting paths in a JSON object.

        Handles the single-response case where the whole file is one
        ``GET /2/tweets/search/recent`` response: ``{"data":[...]}``.
        """
        with self.__configuration.object_storage.get_object_stream(prefix, key) as raw:
            stream = self._maybe_decompress(raw, key)
            try:
                yield from ijson.items(stream, "data.item", use_float=True)
                return
            except ijson.JSONError:
                pass
        with self.__configuration.object_storage.get_object_stream(prefix, key) as raw:
            stream = self._maybe_decompress(raw, key)
            yield from ijson.items(stream, "tweets.item", use_float=True)

    @staticmethod
    def _maybe_decompress(raw: BinaryIO, key: str) -> BinaryIO:
        """Return a stream decompressed if the file is gzipped, else pass-through."""
        if key.endswith(".gz"):
            return gzip.GzipFile(fileobj=raw)  # type: ignore[return-value]
        # Sniff gzip magic without consuming the byte semantically — peek
        # via read(2) + put it back through _PrependByte.
        head = raw.read(2)
        if head == b"\x1f\x8b":
            return cast(
                BinaryIO,
                gzip.GzipFile(fileobj=cast(IO[bytes], _PrependBytes(head, raw))),
            )
        # Not gzipped — re-prepend the 2 bytes we just consumed.
        return cast(BinaryIO, _PrependBytes(head, raw))

    @staticmethod
    def _peek_nonblank_byte(stream: BinaryIO) -> bytes:
        """Skip leading whitespace and return the first content byte (or b'')."""
        while True:
            b = stream.read(1)
            if not b:
                return b""
            if b not in (b" ", b"\t", b"\n", b"\r"):
                return b

    @staticmethod
    def _read_line(stream: IO[bytes]) -> str:
        """Read until '\\n' (inclusive), return as text. Returns '' at EOF."""
        chunks: list[bytes] = []
        while True:
            ch = stream.read(1)
            if not ch:
                break
            chunks.append(ch)
            if ch == b"\n":
                break
        return b"".join(chunks).decode("utf-8", errors="replace")

    @staticmethod
    def _iter_lines(stream: IO[bytes]) -> Iterator[str]:
        buf = b""
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                if buf:
                    yield buf.decode("utf-8", errors="replace")
                return
            buf += chunk
            while True:
                nl = buf.find(b"\n")
                if nl < 0:
                    break
                line, buf = buf[:nl], buf[nl + 1 :]
                yield line.decode("utf-8", errors="replace")

    # ----- Helpers --------------------------------------------------------------

    def _flush(self, graph: Graph, total_so_far: int) -> None:
        triples = len(graph)
        if not triples:
            return
        self.__configuration.triple_store.insert(graph, self.__configuration.graph_name)
        logger.info(
            f"XFileIngestionPipeline: flushed {triples} triples "
            f"(running total: {total_so_far} tweets)"
        )

    def _uri(self, class_name: str, stable_id: str) -> str:
        return uri_for(self._namespace, class_name, stable_id)

    def _instant_uri(self, dt: datetime) -> str:
        safe_ts = dt.strftime("%Y%m%dT%H%M%S%fZ")
        return self._uri("TemporalInstant", safe_ts)

    def _already_ingested(self, sha256: str) -> bool:
        """ASK whether an x:TweetFile with this sha256 is already in the graph."""
        sha256_prop = TweetFile._property_uris["sha256"]
        sparql = (
            f"ASK {{ GRAPH <{self.__configuration.graph_name}> {{ "
            f"?f a <{TweetFile._class_uri}> ; <{sha256_prop}> "
            f'"{sha256}" . }} }}'
        )
        try:
            return bool(self.__configuration.triple_store.query(sparql).askAnswer)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"XFileIngestionPipeline: dedupe ASK failed ({exc}); "
                "assuming not ingested and proceeding"
            )
            return False

    def _build_provenance_graph(
        self,
        *,
        prefix: str,
        key: str,
        sha256: str,
        size_bytes: int,
        import_start: datetime,
    ) -> tuple[Graph, str, str]:
        file_uri = self._uri("TweetFile", sha256)
        result_set_id = f"file-{sha256}"
        result_set_uri = self._uri("SearchResultSet", result_set_id)
        interval_uri = self._uri("SearchInterval", f"import-{sha256}")
        start_instant_uri = self._instant_uri(import_start)

        g = Graph()
        g.bind("x", self.namespace)

        g += TweetFile(
            _uri=file_uri,
            label=key,
            sha256=sha256,
            object_storage_prefix=prefix,
            object_storage_key=key,
            file_size_bytes=size_bytes,
        ).rdf()

        g += SearchResultSet(
            _uri=result_set_uri,
            label=f"Tweet File Result Set {sha256[:8]}",
            result_set_id=result_set_id,
        ).rdf()

        g += TemporalInstant(
            _uri=start_instant_uri,
            label=import_start.isoformat(),
        ).rdf()

        g += SearchInterval(
            _uri=interval_uri,
            label=f"Import Interval {sha256[:8]}",
            search_started_at=[URIRef(start_instant_uri)],
        ).rdf()

        g += TweetFileImport(
            _uri=self._uri("TweetFileImport", sha256),
            label=f"Tweet File Import {sha256[:8]}",
            imports_file=[URIRef(file_uri)],
            has_search_interval=[URIRef(interval_uri)],
            created=import_start,
        ).rdf()

        return g, result_set_uri, interval_uri

    # ----- Framework hooks ------------------------------------------------------

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_ingest_tweets_from_file",
                description=(
                    "Stream an X v2 tweet dump from object storage into "
                    "the ABI knowledge graph. Pass `prefix` + `key`. "
                    "Accepts (auto-detected): a JSON array of bare "
                    "tweets (the shape XIntegration.search_recent_tweets's "
                    "cache writes); a single X v2 response envelope "
                    "{data:[...], meta:{...}}; or NDJSON of either. "
                    "`.gz` variants also work. Dedup'd by sha256 — "
                    "re-running on the same file is a no-op."
                ),
                func=lambda **kwargs: self.run(
                    XFileIngestionPipelineParameters(**kwargs)
                ).serialize(format="turtle"),
                args_schema=XFileIngestionPipelineParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None


# ----- Envelope unwrapping --------------------------------------------------


def _unwrap_envelope(record: dict) -> Iterator[dict]:
    """Yield individual tweet dicts from one parsed JSON object.

    Three input shapes are recognised; everything else is logged + skipped
    so a single malformed line never tanks a multi-GB import:

    * **X v2 search_recent_tweets response envelope**:
      ``{"data": [tweet, ...], "meta": {...}}`` — yield each item of
      ``data`` that looks like a tweet (a dict).
    * **Single tweet** with top-level ``id`` + ``text``: yield as-is.
    * **Includes/expansions-only envelope** (no ``data`` array, just
      ``includes`` or ``meta``): nothing to yield, skip silently.

    The envelope path also tolerates ``includes`` and ``meta`` siblings
    of ``data`` — they're just ignored. Per-tweet provenance like the
    originating ``query`` (when present at the envelope level) is not
    currently captured: file-level provenance via ``x:TweetFile`` /
    ``x:TweetFileImport`` already attributes tweets to the source dump.
    """
    if not isinstance(record, dict):
        logger.warning(
            f"XFileIngestionPipeline: skipping non-object record "
            f"({type(record).__name__})"
        )
        return
    data = record.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "id" in item:
                yield item
        return
    if "id" in record and "text" in record:
        yield record
        return
    # Envelope with only "includes" / "meta" / "errors" — nothing to
    # ingest but not an error condition (every paginated search has at
    # least one such response at the tail).
    if any(k in record for k in ("includes", "meta", "errors")):
        return
    logger.warning(
        f"XFileIngestionPipeline: skipping record of unknown shape, "
        f"keys={list(record.keys())[:10]}"
    )


# ----- Tiny helpers for "peek then put back" semantics ---------------------


class _PrependByte:
    """Wrap *stream* so the first ``read`` returns ``head`` then drains stream."""

    def __init__(self, head: bytes, stream: BinaryIO) -> None:
        self._head: bytes = head
        self._stream = stream

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        if not self._head:
            return self._stream.read(size)
        if size < 0:
            out = self._head + self._stream.read()
            self._head = b""
            return out
        if len(self._head) >= size:
            out, self._head = self._head[:size], self._head[size:]
            return out
        remainder = size - len(self._head)
        out = self._head + self._stream.read(remainder)
        self._head = b""
        return out


class _PrependBytes(_PrependByte):
    """Alias for clarity when the buffered head is multiple bytes."""
