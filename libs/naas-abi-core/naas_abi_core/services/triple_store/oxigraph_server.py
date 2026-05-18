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

    The store is opened once at startup and shared across requests. FastAPI
    serves them serially under uvicorn's default single-worker config, which
    sidesteps any concurrency questions inside the store itself.
    """
    Path(store_path).mkdir(parents=True, exist_ok=True)
    store = Store(path=store_path)
    logger.info("Opened oxigraph store at %s", store_path)

    app = FastAPI(title="abi-dev oxigraph", docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # SPARQL query (SELECT/CONSTRUCT/ASK/DESCRIBE)
    # ------------------------------------------------------------------
    @app.post("/query")
    async def query(request: Request) -> Response:
        body = (await request.body()).decode("utf-8")
        if not body:
            # Some clients pass the query as a URL-encoded form param.
            form = await request.form()
            raw = form.get("query")
            body = raw.strip() if isinstance(raw, str) else ""
        if not body:
            raise HTTPException(status_code=400, detail="empty SPARQL query")

        accept = request.headers.get("accept", "")
        try:
            result = store.query(body)
        except SyntaxError as exc:
            raise HTTPException(status_code=400, detail=f"SPARQL syntax: {exc}")
        except Exception as exc:  # pragma: no cover - bubble unexpected
            logger.exception("query failed")
            raise HTTPException(status_code=500, detail=str(exc))

        # CONSTRUCT / DESCRIBE → RDF format. SELECT / ASK → results format.
        payload: bytes | None
        if isinstance(result, QueryTriples):
            rdf_fmt, media = _rdf_format_for_accept(accept)
            payload = result.serialize(format=rdf_fmt)
        else:
            res_fmt, media = _query_format_for_accept(accept)
            payload = result.serialize(format=res_fmt)
        return Response(content=payload, media_type=media)

    # ------------------------------------------------------------------
    # SPARQL update (INSERT/DELETE/CREATE/DROP/...)
    # ------------------------------------------------------------------
    @app.post("/update")
    async def update(request: Request) -> Response:
        body = (await request.body()).decode("utf-8")
        if not body:
            raise HTTPException(status_code=400, detail="empty SPARQL update")
        try:
            store.update(body)
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
        store.dump(buf, format=fmt)
        return Response(content=buf.getvalue(), media_type=media)

    @app.post("/store")
    async def store_post(request: Request) -> Response:
        content_type = request.headers.get("content-type", "application/n-triples")
        body = await request.body()
        fmt, _ = _rdf_format_for_accept(content_type)
        try:
            store.bulk_load(io.BytesIO(body), format=fmt)
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
        # Parse the payload into a temporary store, then remove each quad.
        from pyoxigraph import parse

        fmt, _ = _rdf_format_for_accept(content_type)
        try:
            for quad in parse(io.BytesIO(body), format=fmt):
                store.remove(quad)
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
