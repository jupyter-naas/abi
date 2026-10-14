"""The broker's HTTP monitoring endpoint (``nats-server -m``): /varz, /connz, /jsz.

Configured as ``nats.monitoring_url`` (e.g. ``http://nats:8222``). The endpoint
has no authentication of its own: keep it on the private network.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    JetStreamConsumer,
    JetStreamStream,
    JetStreamSummary,
    NatsConnection,
    NatsServer,
    SourceUnavailable,
)

SOURCE = "nats_monitor"


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_server(varz: dict[str, Any]) -> NatsServer:
    jetstream = varz.get("jetstream") or {}
    return NatsServer(
        server_id=str(varz.get("server_id", "")),
        server_name=str(varz.get("server_name", "")),
        version=str(varz.get("version", "")),
        uptime=str(varz.get("uptime", "")),
        connections=_int(varz.get("connections")),
        total_connections=_int(varz.get("total_connections")),
        subscriptions=_int(varz.get("subscriptions")),
        slow_consumers=_int(varz.get("slow_consumers")),
        in_msgs=_int(varz.get("in_msgs")),
        out_msgs=_int(varz.get("out_msgs")),
        in_bytes=_int(varz.get("in_bytes")),
        out_bytes=_int(varz.get("out_bytes")),
        mem_bytes=_int(varz.get("mem")),
        cpu_percent=_float(varz.get("cpu")),
        max_payload=_int(varz.get("max_payload")),
        jetstream=bool(jetstream.get("config")),
    )


def parse_connections(connz: dict[str, Any]) -> list[NatsConnection]:
    return [
        NatsConnection(
            cid=_int(c.get("cid")),
            name=str(c.get("name", "") or ""),
            ip=str(c.get("ip", "")),
            port=_int(c.get("port")),
            lang=str(c.get("lang", "") or ""),
            version=str(c.get("version", "") or ""),
            uptime=str(c.get("uptime", "")),
            rtt=str(c.get("rtt", "") or ""),
            subscriptions=_int(c.get("subscriptions")),
            pending_bytes=_int(c.get("pending_bytes")),
            in_msgs=_int(c.get("in_msgs")),
            out_msgs=_int(c.get("out_msgs")),
            in_bytes=_int(c.get("in_bytes")),
            out_bytes=_int(c.get("out_bytes")),
        )
        for c in connz.get("connections") or ()
        if isinstance(c, dict)
    ]


def _consumer(detail: dict[str, Any]) -> JetStreamConsumer:
    config = detail.get("config") or {}
    filters = config.get("filter_subjects") or []
    return JetStreamConsumer(
        name=str(detail.get("name", "")),
        filter_subject=str(config.get("filter_subject") or ", ".join(filters)),
        pending=_int(detail.get("num_pending")),
        ack_pending=_int(detail.get("num_ack_pending")),
        redelivered=_int(detail.get("num_redelivered")),
        waiting=_int(detail.get("num_waiting")),
    )


def _stream(detail: dict[str, Any]) -> JetStreamStream:
    state = detail.get("state") or {}
    config = detail.get("config") or {}
    consumers = tuple(
        _consumer(c) for c in detail.get("consumer_detail") or () if isinstance(c, dict)
    )
    return JetStreamStream(
        name=str(detail.get("name", "")),
        subjects=tuple(str(s) for s in config.get("subjects") or ()),
        messages=_int(state.get("messages")),
        bytes=_int(state.get("bytes")),
        first_seq=_int(state.get("first_seq")),
        last_seq=_int(state.get("last_seq")),
        consumer_count=_int(state.get("consumer_count")) or len(consumers),
        consumers=consumers,
    )


def parse_jetstream(jsz: dict[str, Any]) -> JetStreamSummary:
    api = jsz.get("api") or {}
    streams = [
        _stream(s)
        for account in jsz.get("account_details") or ()
        if isinstance(account, dict)
        for s in account.get("stream_detail") or ()
        if isinstance(s, dict)
    ]
    return JetStreamSummary(
        streams=tuple(sorted(streams, key=lambda s: s.name)),
        memory_bytes=_int(jsz.get("memory")),
        storage_bytes=_int(jsz.get("storage")),
        api_requests=_int(api.get("total")),
        api_errors=_int(api.get("errors")),
    )


def _default_client(base_url: str, timeout: float) -> Any:
    import httpx

    return httpx.AsyncClient(base_url=base_url, timeout=timeout)


class NatsHttpMonitor:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 5.0,
        client_factory: Callable[[str, float], Any] = _default_client,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client_factory = client_factory

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with self._client_factory(self._base_url, self._timeout) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:  # noqa: BLE001 - unreachable, refused, bad status or body
            raise SourceUnavailable(SOURCE, str(exc) or type(exc).__name__) from exc
        if not isinstance(body, dict):
            raise SourceUnavailable(SOURCE, f"unexpected {path} response")
        return body

    async def server(self) -> NatsServer:
        return parse_server(await self._get("/varz"))

    async def connections(self, *, limit: int = 256) -> list[NatsConnection]:
        return parse_connections(await self._get("/connz", {"limit": limit, "sort": "cid"}))

    async def jetstream(self) -> JetStreamSummary:
        params = {"accounts": "true", "streams": "true", "consumers": "true", "config": "true"}
        return parse_jetstream(await self._get("/jsz", params))
