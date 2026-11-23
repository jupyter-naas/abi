"""
Minimal HTTP SPARQL server wrapping :class:`pyoxigraph.Store`.

This exists for the `abi dev` no-docker dev runtime: api and dagster need to
share a triple store concurrently, but the in-process oxigraph adapter is
single-writer file-locked. Running this server in its own process gives the
other services a real SPARQL 1.1 endpoint over HTTP, while staying inside
the no-docker / pure-Python promise (pyoxigraph is already a dependency).

The endpoint surface is the subset consumed by the existing `Oxigraph`
secondary adapter at:
``libs/naas-abi-core/naas_abi_core/services/triple_store/adaptors/secondary/Oxigraph.py``

Endpoints:
  GET  /query?query=… or POST /query (application/sparql-query) — SPARQL
                  query; Accept controls format; default-graph-uri /
                  named-graph-uri confine its dataset
  POST /update  — SPARQL update (application/sparql-update only)
  GET  /store          — dump default graph (text/turtle)
  POST /store?default  — bulk insert default graph (application/n-triples)
  DELETE /store?default — bulk delete default graph (application/n-triples)

Who may call it: a request is served only when its ``Host`` names the bound
address or loopback (a page that rebinds a name to 127.0.0.1 is refused), and,
when the server has a token (``OXIGRAPH_TOKEN``, which ``abi dev`` sets per run
and hands to the services it starts), only with ``Authorization: Bearer
<token>``. Bodies are taken only with their SPARQL or RDF media type, never as a
form or plain text, which a browser sends cross-site without asking.
``/health`` needs no token.

Run with::

    OXIGRAPH_TOKEN=... python -m naas_abi_core.services.triple_store.oxigraph_server \\
        --location ./storage/triplestore/oxigraph \\
        --bind 127.0.0.1:7878
"""

from __future__ import annotations

import argparse
import hmac
import io
import logging
import os
import queue
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pyoxigraph import NamedNode, QueryResultsFormat, QueryTriples, RdfFormat, Store
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

_CHUNK_BYTES = 64 * 1024
TOKEN_ENV = "OXIGRAPH_TOKEN"
# Host names a request may carry, besides the bound address.
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
_WILDCARD_HOSTS = ("0.0.0.0", "::", "*")  # nosec B104 - names, not a bind
_SPARQL_QUERY = "application/sparql-query"
_SPARQL_UPDATE = "application/sparql-update"
_RDF_TYPES = ("application/n-triples", "text/turtle", "application/n-quads")


def _media_type(request: Request) -> str:
    return request.headers.get("content-type", "").split(";")[0].strip().lower()


def _require_media_type(request: Request, *accepted: str) -> None:
    if _media_type(request) not in accepted:
        raise HTTPException(
            status_code=415, detail=f"content type must be one of {', '.join(accepted)}"
        )


def _host_name(host: str) -> str:
    """The name of a ``Host`` header, without its port (``[::1]:7878`` → ``::1``)."""
    host = host.strip().lower()
    if host.startswith("["):
        return host[1:].split("]", 1)[0]
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


class _Abandoned(Exception):
    """The client went away; stop serializing."""


class _ChunkWriter(io.RawIOBase):
    """Where pyoxigraph serializes a result: hands 64 KiB chunks to the response."""

    def __init__(self, put: Callable[[tuple], bool]) -> None:
        self._put = put
        self._buffer = bytearray()

    def writable(self) -> bool:
        return True

    def write(self, data) -> int:  # type: ignore[override]
        self._buffer.extend(data)
        if len(self._buffer) >= _CHUNK_BYTES:
            self.drain()
        return len(data)

    def drain(self) -> None:
        if self._buffer and not self._put(("chunk", bytes(self._buffer))):
            raise _Abandoned()
        self._buffer.clear()


async def _streamed(
    work: Callable[[Callable[[str], bool], _ChunkWriter], None],
) -> Response:
    """Stream what ``work(announce, writer)`` serializes, without holding it.

    ``work`` runs on ONE dedicated thread from start to end (pyoxigraph results
    are bound to the thread that produced them) and calls ``announce(media)``
    before writing. An error before ``announce`` becomes an HTTP status; one
    after it truncates the body, as a SPARQL server streaming its result does.
    """
    chunks: queue.Queue = queue.Queue(maxsize=8)
    stopped = threading.Event()

    def put(item: tuple) -> bool:
        while not stopped.is_set():
            try:
                chunks.put(item, timeout=0.2)
                return True
            except queue.Full:
                continue
        return False

    def run() -> None:
        writer = _ChunkWriter(put)
        try:
            work(lambda media: put(("media", media)), writer)
            writer.drain()
        except _Abandoned:
            return
        except BaseException as exc:  # noqa: BLE001 - reported to the response
            put(("error", exc))
            return
        put(("end", None))

    async def next_item() -> tuple:
        while True:
            try:
                return await run_in_threadpool(chunks.get, True, 0.5)
            except queue.Empty:
                continue

    threading.Thread(target=run, name="oxigraph-stream", daemon=True).start()
    kind, value = await next_item()
    if kind == "error":
        stopped.set()
        if isinstance(value, SyntaxError):
            raise HTTPException(status_code=400, detail=f"SPARQL syntax: {value}")
        logger.error("query failed: %s", value)
        raise HTTPException(status_code=500, detail=str(value))

    async def body() -> AsyncIterator[bytes]:
        try:
            while True:
                kind, item = await next_item()
                if kind == "chunk":
                    yield item
                elif kind == "error":
                    logger.error("query failed mid-stream: %s", item)
                    return
                else:
                    return
        finally:
            stopped.set()

    return StreamingResponse(body(), media_type=value)


def _query_format_for_accept(accept: str) -> tuple[QueryResultsFormat, str]:
    """Pick a SPARQL results format from the request's Accept header.

    Defaults to JSON if nothing specific is asked for — that's what RDFLib's
    client expects.
    """
    if "application/sparql-results+xml" in accept or "xml" in accept:
        return QueryResultsFormat.XML, "application/sparql-results+xml"
    if "text/csv" in accept:
        return QueryResultsFormat.CSV, "text/csv"
    if "text/tab-separated-values" in accept:
        return QueryResultsFormat.TSV, "text/tab-separated-values"
    return QueryResultsFormat.JSON, "application/sparql-results+json"


def _rdf_format_for_accept(accept: str) -> tuple[RdfFormat, str]:
    if "application/n-triples" in accept or "n-triples" in accept:
        return RdfFormat.N_TRIPLES, "application/n-triples"
    if "text/turtle" in accept or "turtle" in accept:
        return RdfFormat.TURTLE, "text/turtle"
    if "application/n-quads" in accept or "n-quads" in accept:
        return RdfFormat.N_QUADS, "application/n-quads"
    return RdfFormat.TURTLE, "text/turtle"


def create_app(
    store_path: str,
    *,
    token: str | None = None,
    hosts: Iterable[str] = LOOPBACK_HOSTS,
) -> FastAPI:
    """Build the FastAPI app for the given store path.

    Requests are served only when their ``Host`` is one of ``hosts`` and, with
    a ``token``, only when they carry it as a bearer credential (``/health``
    excepted).

    The store is opened once at startup and shared across requests. Every blocking
    pyoxigraph call is dispatched to a worker thread (``run_in_threadpool``) so the single
    uvicorn event loop stays responsive under concurrent requests; pyoxigraph's ``Store``
    is thread-safe, so concurrent reads and serialized writes are handled by the store.
    """
    Path(store_path).mkdir(parents=True, exist_ok=True)
    store = Store(path=store_path)
    logger.info("Opened oxigraph store at %s", store_path)

    app = FastAPI(
        title="abi-dev oxigraph", docs_url=None, redoc_url=None, openapi_url=None
    )
    allowed_hosts = frozenset(h.lower() for h in hosts)
    expected = f"Bearer {token}".encode() if token else None

    @app.middleware("http")
    async def callers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if _host_name(request.headers.get("host", "")) not in allowed_hosts:
            return Response("host not served", status_code=421)
        if expected is not None and request.url.path != "/health":
            given = request.headers.get("authorization", "").encode()
            if not hmac.compare_digest(given, expected):
                return Response(
                    "token required",
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)

    # pyoxigraph's Store calls (query/update/dump/bulk_load) are synchronous and can take
    # a while. The handlers below are ``async`` (so they can ``await request.body()``),
    # which means running those blocking calls inline would freeze the event loop and the
    # whole single-worker server stops accepting connections under any concurrency. We
    # offload every blocking Store operation to a worker thread; pyoxigraph's Store is
    # thread-safe (MVCC), so concurrent reads + serialized writes are safe.

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    def _dataset_options(request: Request) -> dict:
        """SPARQL Protocol dataset parameters, as Oxigraph's server reads them:
        ``default-graph-uri`` replaces the default graph, ``named-graph-uri``
        the named graphs; either absent keeps the store's."""
        options: dict = {}
        defaults = request.query_params.getlist("default-graph-uri")
        named = request.query_params.getlist("named-graph-uri")
        if defaults:
            options["default_graph"] = [NamedNode(iri) for iri in defaults]
        if named:
            options["named_graphs"] = [NamedNode(iri) for iri in named]
        return options

    # ------------------------------------------------------------------
    # SPARQL query (SELECT/CONSTRUCT/ASK/DESCRIBE)
    # ------------------------------------------------------------------
    def _query_into(
        query_str: str, accept: str, announce, writer, options: dict | None = None
    ) -> None:
        """Run query + serialize on ONE thread (see ``_streamed``).

        pyoxigraph's query result (``QuerySolutions``/``QueryTriples``) is *unsendable* —
        it's bound to the thread that produced it and panics the interpreter if touched
        from another thread. So the whole query→serialize chain stays on one thread.
        """
        result = store.query(query_str, **(options or {}))
        # CONSTRUCT / DESCRIBE → RDF format. SELECT / ASK → results format.
        if isinstance(result, QueryTriples):
            rdf_fmt, media = _rdf_format_for_accept(accept)
            announce(media)
            result.serialize(writer, format=rdf_fmt)
            return
        res_fmt, media = _query_format_for_accept(accept)
        announce(media)
        result.serialize(writer, format=res_fmt)

    async def _run_query(query_str: str, accept: str, request: Request) -> Response:
        if not query_str:
            raise HTTPException(status_code=400, detail="empty SPARQL query")
        options = _dataset_options(request)
        return await _streamed(
            lambda announce, writer: _query_into(
                query_str, accept, announce, writer, options
            )
        )

    @app.get("/query")
    async def query_get(request: Request) -> Response:
        """SPARQL 1.1 protocol: GET /query?query=...  (URL-encoded)."""
        query_str = (request.query_params.get("query") or "").strip()
        accept = request.headers.get("accept", "")
        return await _run_query(query_str, accept, request)

    @app.post("/query")
    async def query_post(request: Request) -> Response:
        """SPARQL 1.1 protocol: POST /query, ``application/sparql-query`` with
        the query in the raw body."""
        _require_media_type(request, _SPARQL_QUERY)
        query_str = (await request.body()).decode("utf-8").strip()
        accept = request.headers.get("accept", "")
        return await _run_query(query_str, accept, request)

    # ------------------------------------------------------------------
    # SPARQL update (INSERT/DELETE/CREATE/DROP/...)
    # ------------------------------------------------------------------
    @app.post("/update")
    async def update(request: Request) -> Response:
        _require_media_type(request, _SPARQL_UPDATE)
        body = (await request.body()).decode("utf-8").strip()
        if not body:
            raise HTTPException(status_code=400, detail="empty SPARQL update")
        try:
            await run_in_threadpool(store.update, body)
        except SyntaxError as exc:
            raise HTTPException(status_code=400, detail=f"SPARQL syntax: {exc}")
        except Exception as exc:  # pragma: no cover
            logger.exception("update failed")
            raise HTTPException(status_code=500, detail=str(exc))
        return Response(status_code=204)

    # ------------------------------------------------------------------
    # /store — bulk RDF I/O on the default graph
    # ------------------------------------------------------------------
    @app.get("/store")
    async def store_get(request: Request) -> Response:
        accept = request.headers.get("accept", "text/turtle")
        fmt, media = _rdf_format_for_accept(accept)

        def dump(announce, writer) -> None:
            announce(media)
            store.dump(writer, format=fmt)

        return await _streamed(dump)

    @app.post("/store")
    async def store_post(request: Request) -> Response:
        _require_media_type(request, *_RDF_TYPES)
        content_type = _media_type(request)
        body = await request.body()
        fmt, _ = _rdf_format_for_accept(content_type)
        try:
            await run_in_threadpool(store.bulk_load, io.BytesIO(body), format=fmt)
        except Exception as exc:  # pragma: no cover
            logger.exception("bulk load failed")
            raise HTTPException(status_code=500, detail=str(exc))
        return Response(status_code=204)

    @app.delete("/store")
    async def store_delete(request: Request) -> Response:
        """Remove every triple supplied in the request body.

        N-Triples / Turtle in, each parsed triple is removed from the default
        graph. Matches the contract the existing Oxigraph adapter expects.
        """
        _require_media_type(request, *_RDF_TYPES)
        content_type = _media_type(request)
        body = await request.body()
        if not body:
            return Response(status_code=204)
        # Parse the payload, then remove each quad. The whole loop is blocking, so run it
        # off the event loop in a worker thread.
        from pyoxigraph import parse

        fmt, _ = _rdf_format_for_accept(content_type)

        def _remove_all() -> None:
            for quad in parse(io.BytesIO(body), format=fmt):
                store.remove(quad)

        try:
            await run_in_threadpool(_remove_all)
        except Exception as exc:  # pragma: no cover
            logger.exception("bulk delete failed")
            raise HTTPException(status_code=500, detail=str(exc))
        return Response(status_code=204)

    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="abi-oxigraph-server")
    parser.add_argument(
        "--location",
        required=True,
        help="Directory where the oxigraph store lives (will be created).",
    )
    parser.add_argument(
        "--bind",
        default="127.0.0.1:7878",
        help="host:port to bind (default: 127.0.0.1:7878).",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug"],
    )
    args = parser.parse_args(argv)

    host, _, port_s = args.bind.rpartition(":")
    if not host:
        host = "127.0.0.1"
    port = int(port_s)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [oxigraph-server] %(levelname)s %(message)s",
    )

    token = os.environ.get(TOKEN_ENV) or None
    if token is None:
        logger.warning(
            "%s is not set: any local process may read and write this store", TOKEN_ENV
        )
    hosts = [*LOOPBACK_HOSTS]
    if host.lower() not in _WILDCARD_HOSTS:
        hosts.append(host)
    app = create_app(args.location, token=token, hosts=hosts)

    # Local import keeps pure-import-time cost low when this module is
    # touched without running the server.
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level=args.log_level)


if __name__ == "__main__":
    main()
