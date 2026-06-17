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
  POST /query   — SPARQL query;  body=sparql-query, Accept controls format
  POST /update  — SPARQL update; body=sparql-update
  GET  /store          — dump default graph (text/turtle)
  POST /store?default  — bulk insert default graph (application/n-triples)
  DELETE /store?default — bulk delete default graph (application/n-triples)

Run with::

    python -m naas_abi_core.services.triple_store.oxigraph_server \\
        --location ./storage/triplestore/oxigraph \\
        --bind 127.0.0.1:7878
"""

from __future__ import annotations

import argparse
import io
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from pyoxigraph import QueryResultsFormat, QueryTriples, RdfFormat, Store
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


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


def create_app(store_path: str) -> FastAPI:
    """Build the FastAPI app for the given store path.

    The store is opened once at startup and shared across requests. Every blocking
    pyoxigraph call is dispatched to a worker thread (``run_in_threadpool``) so the single
    uvicorn event loop stays responsive under concurrent requests; pyoxigraph's ``Store``
    is thread-safe, so concurrent reads and serialized writes are handled by the store.
    """
    Path(store_path).mkdir(parents=True, exist_ok=True)
    store = Store(path=store_path)
    logger.info("Opened oxigraph store at %s", store_path)

    app = FastAPI(title="abi-dev oxigraph", docs_url=None, redoc_url=None)

    # pyoxigraph's Store calls (query/update/dump/bulk_load) are synchronous and can take
    # a while. The handlers below are ``async`` (so they can ``await request.body()``),
    # which means running those blocking calls inline would freeze the event loop and the
    # whole single-worker server stops accepting connections under any concurrency. We
    # offload every blocking Store operation to a worker thread; pyoxigraph's Store is
    # thread-safe (MVCC), so concurrent reads + serialized writes are safe.

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # SPARQL query (SELECT/CONSTRUCT/ASK/DESCRIBE)
    # ------------------------------------------------------------------
    def _query_sync(query_str: str, accept: str) -> tuple[bytes | None, str]:
        """Run query + serialize on ONE thread and return (payload, media_type).

        pyoxigraph's query result (``QuerySolutions``/``QueryTriples``) is *unsendable* —
        it's bound to the thread that produced it and panics the interpreter if touched
        from another thread. So the whole query→serialize chain must stay on a single
        thread; we hand that one chunk of blocking work to the threadpool below.
        """
        result = store.query(query_str)
        # CONSTRUCT / DESCRIBE → RDF format. SELECT / ASK → results format.
        if isinstance(result, QueryTriples):
            rdf_fmt, media = _rdf_format_for_accept(accept)
            return result.serialize(format=rdf_fmt), media
        res_fmt, media = _query_format_for_accept(accept)
        return result.serialize(format=res_fmt), media

    async def _run_query(query_str: str, accept: str) -> Response:
        if not query_str:
            raise HTTPException(status_code=400, detail="empty SPARQL query")
        try:
            payload, media = await run_in_threadpool(_query_sync, query_str, accept)
        except SyntaxError as exc:
            raise HTTPException(status_code=400, detail=f"SPARQL syntax: {exc}")
        except Exception as exc:  # pragma: no cover - bubble unexpected
            logger.exception("query failed")
            raise HTTPException(status_code=500, detail=str(exc))
        return Response(content=payload, media_type=media)

    @app.get("/query")
    async def query_get(request: Request) -> Response:
        """SPARQL 1.1 protocol: GET /query?query=...  (URL-encoded)."""
        query_str = (request.query_params.get("query") or "").strip()
        accept = request.headers.get("accept", "")
        return await _run_query(query_str, accept)

    @app.post("/query")
    async def query_post(request: Request) -> Response:
        """SPARQL 1.1 protocol: POST /query.

        Accepts either ``application/sparql-query`` with the query in the
        raw body, or ``application/x-www-form-urlencoded`` with
        ``query=...``.
        """
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            raw = form.get("query")
            query_str = raw.strip() if isinstance(raw, str) else ""
        else:
            query_str = (await request.body()).decode("utf-8").strip()
        accept = request.headers.get("accept", "")
        return await _run_query(query_str, accept)

    # ------------------------------------------------------------------
    # SPARQL update (INSERT/DELETE/CREATE/DROP/...)
    # ------------------------------------------------------------------
    @app.post("/update")
    async def update(request: Request) -> Response:
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            raw = form.get("update")
            body = raw.strip() if isinstance(raw, str) else ""
        else:
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
        buf = io.BytesIO()
        await run_in_threadpool(store.dump, buf, format=fmt)
        return Response(content=buf.getvalue(), media_type=media)

    @app.post("/store")
    async def store_post(request: Request) -> Response:
        content_type = request.headers.get("content-type", "application/n-triples")
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
        content_type = request.headers.get("content-type", "application/n-triples")
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

    app = create_app(args.location)

    # Local import keeps pure-import-time cost low when this module is
    # touched without running the server.
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level=args.log_level)


if __name__ == "__main__":
    main()
