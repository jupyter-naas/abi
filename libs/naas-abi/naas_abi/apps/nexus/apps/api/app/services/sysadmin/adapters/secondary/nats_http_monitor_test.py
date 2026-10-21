import asyncio

import httpx
import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_http_monitor import (
    NatsHttpMonitor,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import NatsServerMonitorContract
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable

VARZ = {
    "server_id": "NSRV",
    "server_name": "nats",
    "version": "2.14.7",
    "uptime": "1h2m",
    "mem": 2048,
    "cpu": 0.4,
    "connections": 2,
    "total_connections": 7,
    "subscriptions": 33,
    "slow_consumers": 0,
    "in_msgs": 10,
    "out_msgs": 11,
    "in_bytes": 100,
    "out_bytes": 110,
    "max_payload": 8388608,
    "jetstream": {"config": {"max_memory": 1}, "stats": {}},
}
CONNZ = {
    "connections": [
        {
            "cid": 4,
            "name": "api",
            "ip": "10.0.0.2",
            "port": 5100,
            "lang": "python3",
            "version": "2.16.0",
            "uptime": "1h",
            "rtt": "1ms",
            "subscriptions": 12,
            "pending_bytes": 0,
            "in_msgs": 5,
            "out_msgs": 6,
            "in_bytes": 50,
            "out_bytes": 60,
        },
        {
            "cid": 5,
            "ip": "10.0.0.3",
            "port": 5101,
            "lang": "python3",
            "version": "2.16.0",
            "uptime": "5m",
            "rtt": "2ms",
            "subscriptions": 3,
            "pending_bytes": 0,
            "in_msgs": 1,
            "out_msgs": 1,
            "in_bytes": 10,
            "out_bytes": 10,
        },
    ]
}
JSZ = {
    "memory": 0,
    "storage": 1200,
    "api": {"total": 30, "errors": 0},
    "account_details": [
        {
            "name": "$G",
            "stream_detail": [
                {
                    "name": "KV_ABI_DISCOVERY_zen",
                    "config": {"subjects": ["$KV.ABI_DISCOVERY_zen.>"]},
                    "state": {
                        "messages": 1,
                        "bytes": 300,
                        "first_seq": 1,
                        "last_seq": 1,
                        "consumer_count": 0,
                    },
                },
                {
                    "name": "ABI_JOBS_zen",
                    "config": {"subjects": ["abi.jobs.zen.>"]},
                    "state": {
                        "messages": 4,
                        "bytes": 900,
                        "first_seq": 1,
                        "last_seq": 4,
                        "consumer_count": 1,
                    },
                    "consumer_detail": [
                        {
                            "name": "job-a-b",
                            "config": {"filter_subject": "abi.jobs.zen.trigger.a.b"},
                            "num_pending": 1,
                            "num_ack_pending": 0,
                            "num_redelivered": 0,
                            "num_waiting": 0,
                        }
                    ],
                },
            ],
        }
    ],
}


def _client(requests):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = {"/varz": VARZ, "/connz": CONNZ, "/jsz": JSZ}.get(request.url.path)
        return httpx.Response(200, json=body) if body is not None else httpx.Response(404)

    def factory(base_url, timeout):
        return httpx.AsyncClient(
            base_url=base_url, transport=httpx.MockTransport(handler), timeout=timeout
        )

    return factory


@pytest.fixture
def monitor():
    return NatsHttpMonitor("http://nats:8222/", client_factory=_client([]))


class TestNatsHttpMonitor(NatsServerMonitorContract):
    pass


def test_asks_jsz_for_streams_and_consumers():
    requests = []
    asyncio.run(NatsHttpMonitor("http://nats:8222", client_factory=_client(requests)).jetstream())

    (request,) = requests
    assert request.url.params["consumers"] == "true" and request.url.params["streams"] == "true"


def test_unreachable_monitor_is_unavailable():
    def refuse(request):
        raise httpx.ConnectError("refused")

    def factory(base_url, timeout):
        return httpx.AsyncClient(base_url=base_url, transport=httpx.MockTransport(refuse))

    with pytest.raises(SourceUnavailable) as raised:
        asyncio.run(NatsHttpMonitor("http://nats:8222", client_factory=factory).server())
    assert raised.value.source == "nats_monitor"
