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
from typing import IO, Annotated, BinaryIO, Iterator, cast

import ijson
from langchain_core.tools import BaseTool, StructuredTool
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
from naas_abi_marketplace.applications.x import X_NAMESPACE
from naas_abi_marketplace.applications.x.pipelines._graph_builder import (
    XTweetGraphBuilder,
)
from pydantic import Field
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

# IRIs for the file-import provenance nodes. We add these as plain RDF
# triples rather than through onto2py-generated Python classes so the
# ontology TTL doesn't need to be regenerated to add file-ingestion
# support — the SPARQL competency questions match on these IRIs directly.
TWEET_FILE_IMPORT_CLASS = URIRef(f"{X_NAMESPACE}TweetFileImport")
TWEET_FILE_CLASS = URIRef(f"{X_NAMESPACE}TweetFile")
P_IMPORTS_FILE = URIRef(f"{X_NAMESPACE}imports_file")
P_PRODUCES_SEARCH_RESULT = URIRef(f"{X_NAMESPACE}producesSearchResult")
P_SHA256 = URIRef(f"{X_NAMESPACE}sha256")
P_OBJECT_STORAGE_PREFIX = URIRef(f"{X_NAMESPACE}object_storage_prefix")
P_OBJECT_STORAGE_KEY = URIRef(f"{X_NAMESPACE}object_storage_key")
P_FILE_SIZE_BYTES = URIRef(f"{X_NAMESPACE}file_size_bytes")
P_RECORD_COUNT = URIRef(f"{X_NAMESPACE}record_count")
P_CREATED = URIRef(f"{X_NAMESPACE}created")

# Reuse the existing SearchResultSet class via its IRI — it doesn't need
# to be a TweetFileImport-specific result-set type; conceptually it's
# "this batch of tweets came in together".
SEARCH_RESULT_SET_CLASS = URIRef(f"{X_NAMESPACE}SearchResultSet")
P_RESULT_SET_ID = URIRef(f"{X_NAMESPACE}result_set_id")
P_RESULT_COUNT = URIRef(f"{X_NAMESPACE}result_count")
P_IS_CONTAINED_IN_SEARCH_RESULT_SET = URIRef(
    f"{X_NAMESPACE}isContainedInSearchResultSet"
)


@dataclass
class XFileIngestionPipelineConfiguration(PipelineConfiguration):
    """Wiring needed to run :class:`XFileIngestionPipeline`.

    Attributes:
        object_storage: Source of the file bytes. Must support
            :meth:`get_object_stream` (added to the port in this PR).
        triple_store: Target named graph + dedupe ASK destination.
        graph_name: Named graph IRI to insert into.
        batch_size: Records per INSERT round trip — see
            :class:`naas_abi_marketplace.applications.x.XTweetFileIngestionConfiguration`.
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

        # ----- Step 2: provenance subgraph (file + import process + result set)
        provenance = self._build_provenance_graph(
            prefix=prefix, key=key, sha256=sha256, size_bytes=size_bytes
        )
        result_set_uri = self._uri("SearchResultSet", f"file-{sha256}")
        self.__configuration.triple_store.insert(
            provenance, self.__configuration.graph_name
        )

        # ----- Step 3: stream the tweets through the shared graph builder ------
        builder = XTweetGraphBuilder(
            self.__configuration.triple_store, self.__configuration.graph_name
        )
        batch_size = self.__configuration.batch_size
        batch = Graph()
        batch.bind("x", Namespace(X_NAMESPACE))
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
                batch.bind("x", Namespace(X_NAMESPACE))
                batch_count = 0

        if batch_count:
            self._flush(batch, total_count)

        # ----- Step 4: stamp the final record_count on the provenance node ----
        final = Graph()
        process_uri = URIRef(self._uri("TweetFileImport", sha256))
        final.add((process_uri, P_RECORD_COUNT, Literal(total_count)))
        result_set_uri_ref = URIRef(result_set_uri)
        final.add((result_set_uri_ref, P_RESULT_COUNT, Literal(total_count)))
        self.__configuration.triple_store.insert(
            final, self.__configuration.graph_name
        )

        logger.info(
            f"XFileIngestionPipeline: ingested {total_count} tweets from "
            f"{prefix}/{key} (sha256={sha256})"
        )

        if parameters.delete_after_ingest:
            self.__configuration.object_storage.delete_object(prefix, key)
            logger.info(
                f"XFileIngestionPipeline: deleted source object {prefix}/{key}"
            )

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
        """Yield tweet dicts from *prefix/key*, agnostic to NDJSON vs array.

        The file is opened once via ``get_object_stream``; the underlying
        body is gzip-decompressed transparently when the key ends in
        ``.gz`` or when the magic bytes look gzip-y. Format detection
        between NDJSON and JSON-array peeks at the first non-whitespace
        byte: ``[`` => array (ijson), anything else => NDJSON.
        """
        with self.__configuration.object_storage.get_object_stream(
            prefix, key
        ) as raw:
            stream = self._maybe_decompress(raw, key)
            first = self._peek_nonblank_byte(stream)
            if first == b"[":
                # JSON array — ijson incrementally yields each top-level item.
                # We re-prepend the byte ijson consumed via _PrependByte.
                wrapped = cast(IO[bytes], _PrependByte(first, stream))
                yield from ijson.items(wrapped, "item", use_float=True)
            elif first == b"{":
                # Two cases: (a) NDJSON whose first line happens to start
                # with `{`, or (b) a single big JSON object with an "items"
                # / "data" / "tweets" list under one of those keys. We try
                # NDJSON first (most common for big dumps); if the first
                # line fails to parse we fall back to ijson on the wrapped
                # object hunting for a list under `data` or `tweets`.
                wrapped = cast(IO[bytes], _PrependByte(first, stream))
                first_line = self._read_line(wrapped)
                try:
                    yield json.loads(first_line)
                except json.JSONDecodeError:
                    # Fall back to ijson, rewinding via a fresh stream
                    # because the line we consumed is unrecoverable from
                    # here. The cost of a second pass for the malformed
                    # case is acceptable.
                    yield from self._iter_records_via_ijson(prefix, key)
                    return
                # Continue NDJSON from where we left off
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
        """Hunt for a tweet list under common nesting paths in a JSON object."""
        with self.__configuration.object_storage.get_object_stream(
            prefix, key
        ) as raw:
            stream = self._maybe_decompress(raw, key)
            # Try the X v2 envelope first: `{"data":[...]}`
            try:
                yield from ijson.items(stream, "data.item", use_float=True)
                return
            except ijson.JSONError:
                pass
        with self.__configuration.object_storage.get_object_stream(
            prefix, key
        ) as raw:
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
        self.__configuration.triple_store.insert(
            graph, self.__configuration.graph_name
        )
        logger.info(
            f"XFileIngestionPipeline: flushed {triples} triples "
            f"(running total: {total_so_far} tweets)"
        )

    @staticmethod
    def _uri(class_name: str, stable_id: str) -> str:
        import re

        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", stable_id)
        return f"{X_NAMESPACE}{class_name}/{safe}"

    def _already_ingested(self, sha256: str) -> bool:
        """ASK whether an x:TweetFile with this sha256 is already in the graph."""
        sparql = (
            f"ASK {{ GRAPH <{self.__configuration.graph_name}> {{ "
            f"?f a <{TWEET_FILE_CLASS}> ; <{P_SHA256}> "
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
        self, *, prefix: str, key: str, sha256: str, size_bytes: int
    ) -> Graph:
        g = Graph()
        g.bind("x", Namespace(X_NAMESPACE))

        file_uri = URIRef(self._uri("TweetFile", sha256))
        g.add((file_uri, RDF.type, TWEET_FILE_CLASS))
        g.add((file_uri, RDFS.label, Literal(key)))
        g.add((file_uri, P_SHA256, Literal(sha256)))
        g.add((file_uri, P_OBJECT_STORAGE_PREFIX, Literal(prefix)))
        g.add((file_uri, P_OBJECT_STORAGE_KEY, Literal(key)))
        g.add(
            (
                file_uri,
                P_FILE_SIZE_BYTES,
                Literal(size_bytes, datatype=XSD.integer),
            )
        )

        result_set_uri = URIRef(self._uri("SearchResultSet", f"file-{sha256}"))
        g.add((result_set_uri, RDF.type, SEARCH_RESULT_SET_CLASS))
        g.add(
            (
                result_set_uri,
                RDFS.label,
                Literal(f"Tweet File Result Set {sha256[:8]}"),
            )
        )
        g.add((result_set_uri, P_RESULT_SET_ID, Literal(f"file-{sha256}")))

        process_uri = URIRef(self._uri("TweetFileImport", sha256))
        g.add((process_uri, RDF.type, TWEET_FILE_IMPORT_CLASS))
        g.add(
            (process_uri, RDFS.label, Literal(f"Tweet File Import {sha256[:8]}"))
        )
        g.add((process_uri, P_IMPORTS_FILE, file_uri))
        g.add((process_uri, P_PRODUCES_SEARCH_RESULT, result_set_uri))
        g.add(
            (
                process_uri,
                P_CREATED,
                Literal(datetime.now(timezone.utc), datatype=XSD.dateTime),
            )
        )

        return g

    # ----- Framework hooks ------------------------------------------------------

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_ingest_tweets_from_file",
                description=(
                    "Stream an X v2 tweet dump (JSON array, NDJSON, or "
                    "gzipped variants) from object storage into the ABI "
                    "knowledge graph. Pass `prefix` + `key`. Dedup'd by "
                    "sha256 — re-running on the same file is a no-op."
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
