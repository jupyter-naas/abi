"""Throughput benchmark for the EventService.

Single-process, single-thread microbench. Measures each operation in
isolation so we can see where the cost lives.

Run:
    uv run python -m naas_abi_core.services.event.benchmark
"""

from __future__ import annotations

import os
import platform
import statistics
import sys
import tempfile
import time
from contextlib import contextmanager
from typing import ClassVar, Optional

import threading

from naas_abi_core.services.bus.BusPorts import IBusAdapter
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import (
    PythonQueueAdapter,
)
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.event_ontology import LogProcess
from naas_abi_core.services.event.EventService import EventService


class _InMemoryBusAdapter(IBusAdapter):
    """Synchronous in-memory bus. Isolates EventService overhead from bus
    implementation cost. Production deployments use RabbitMQ; PythonQueueAdapter
    is itself SQLite-backed and contends with our DB under high publish load."""

    def __init__(self):
        self._subscribers: dict[str, list] = {}

    def topic_publish(self, topic, routing_key, payload):
        for cb in self._subscribers.get(topic, []):
            cb(payload)

    def topic_consume(self, topic, routing_key, callback):
        self._subscribers.setdefault(topic, []).append(callback)
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        return t


# A realistic event shape: a few string/datetime fields, one of each common type.
class BenchEvent(LogProcess):
    _class_uri: ClassVar[str] = "http://example.org/BenchEvent"
    _property_uris: ClassVar[dict] = {
        **LogProcess._property_uris,
        "user_id": "http://example.org/userId",
        "method": "http://example.org/method",
        "ip": "http://example.org/ip",
        "session_id": "http://example.org/sessionId",
    }
    user_id: Optional[str] = None
    method: Optional[str] = None
    ip: Optional[str] = None
    session_id: Optional[str] = None


# ---------------------------------------------------------------------------


@contextmanager
def timer():
    t = [0.0]
    start = time.perf_counter()
    try:
        yield t
    finally:
        t[0] = time.perf_counter() - start


def fmt_rate(n: int, seconds: float) -> str:
    rate = n / seconds if seconds > 0 else float("inf")
    return f"{rate:>10,.0f} /sec  ({seconds*1000/n:.3f} ms/op)"


def make_event(i: int) -> BenchEvent:
    return BenchEvent(
        user_id=f"user-{i:06d}",
        method="oauth_google",
        ip="192.168.1.1",
        session_id=f"sess-{i:08x}",
    )


# ---------------------------------------------------------------------------


def bench_publish_no_bus(n: int, db_path: str) -> float:
    adapter = EventSQLiteAdapter(db_path)
    service = EventService(adapter=adapter, bus=None)
    events = [make_event(i) for i in range(n)]
    with timer() as t:
        for e in events:
            service.publish(e)
    adapter.close()
    return t[0]


def bench_publish_with_bus_in_memory(n: int, db_path: str) -> float:
    """In-memory bus — measures EventService overhead with no bus persistence."""
    adapter = EventSQLiteAdapter(db_path)
    bus = BusService(_InMemoryBusAdapter())
    service = EventService(adapter=adapter, bus=bus)
    events = [make_event(i) for i in range(n)]
    with timer() as t:
        for e in events:
            service.publish(e)
    adapter.close()
    return t[0]


def bench_publish_with_bus_python_queue(n: int, db_path: str) -> float:
    """PythonQueueAdapter — itself SQLite-backed. Realistic local-dev cost."""
    adapter = EventSQLiteAdapter(db_path)
    bus = BusService(PythonQueueAdapter())
    service = EventService(adapter=adapter, bus=bus)
    events = [make_event(i) for i in range(n)]
    with timer() as t:
        for e in events:
            service.publish(e)
    adapter.close()
    return t[0]


def bench_publish_with_live_subscriber(n: int, db_path: str) -> float:
    """Live subscriber on the SYNCHRONOUS in-memory bus.

    Important: with the synchronous in-memory bus, the subscriber callback
    (including RDF reconstruction) runs inline on the publisher thread, so
    this benchmark measures publish + reconstruction per event. With a real
    async bus (RabbitMQ), reconstruction happens in a consumer process and
    does not slow down publish.
    """
    adapter = EventSQLiteAdapter(db_path)
    bus = BusService(_InMemoryBusAdapter())
    service = EventService(adapter=adapter, bus=bus)
    received = [0]

    def cb(_evt):
        received[0] += 1

    service.subscribe(BenchEvent, cb)
    events = [make_event(i) for i in range(n)]
    with timer() as t:
        for e in events:
            service.publish(e)
    adapter.close()
    return t[0]


def bench_query_eager(n: int, db_path: str) -> float:
    adapter = EventSQLiteAdapter(db_path)
    service = EventService(adapter=adapter, bus=None)
    for i in range(n):
        service.publish(make_event(i))
    with timer() as t:
        rows = service.query(event_class=BenchEvent)
    assert len(rows) == n
    adapter.close()
    return t[0]


def bench_iter_query(n: int, db_path: str, batch_size: int = 500) -> float:
    adapter = EventSQLiteAdapter(db_path)
    service = EventService(adapter=adapter, bus=None)
    for i in range(n):
        service.publish(make_event(i))
    with timer() as t:
        count = 0
        for _ in service.iter_query(event_class=BenchEvent, batch_size=batch_size):
            count += 1
    assert count == n
    adapter.close()
    return t[0]


def bench_query_for_consumer(n: int, db_path: str) -> float:
    adapter = EventSQLiteAdapter(db_path)
    service = EventService(adapter=adapter, bus=None)
    for i in range(n):
        service.publish(make_event(i))
    with timer() as t:
        count = 0
        for _ in service.iter_query_for_consumer(
            "bench-consumer", BenchEvent, batch_size=500
        ):
            count += 1
    assert count == n
    adapter.close()
    return t[0]


def bench_adapter_append_only(n: int, db_path: str) -> float:
    """Skip RDF serialization entirely: measure pure adapter cost."""
    adapter = EventSQLiteAdapter(db_path)
    payload = b"x" * 200  # representative size
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    with timer() as t:
        for i in range(n):
            adapter.append(f"urn:e{i}", "urn:Type:Bench", ts, payload)
    adapter.close()
    return t[0]


def bench_adapter_query_only(n: int, db_path: str) -> float:
    """Skip RDF reconstruction: measure pure adapter read cost."""
    adapter = EventSQLiteAdapter(db_path)
    payload = b"x" * 200
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    for i in range(n):
        adapter.append(f"urn:e{i}", "urn:Type:Bench", ts, payload)
    with timer() as t:
        rows = adapter.query(event_type="urn:Type:Bench")
    assert len(rows) == n
    adapter.close()
    return t[0]


# ---------------------------------------------------------------------------


def run_bench(name: str, fn, n: int, repeats: int = 3) -> float:
    """Run `fn(n, tmp_db)` `repeats` times, return median time."""
    times = []
    for _ in range(repeats):
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "events.sqlite")
            times.append(fn(n, db))
    median = statistics.median(times)
    print(f"  {name:48s} n={n:>6,}   {fmt_rate(n, median)}")
    return median


def main():
    print("\nEventService benchmark")
    print(f"  Python   : {sys.version.split()[0]}")
    print(f"  Platform : {platform.platform()}")
    print(f"  Machine  : {platform.machine()}\n")

    print("--- Publish (service.publish, persists + optional bus) ---")
    run_bench("publish (no bus)", bench_publish_no_bus, 5_000)
    run_bench("publish (in-memory bus)", bench_publish_with_bus_in_memory, 5_000)
    run_bench("publish (PythonQueueAdapter bus)", bench_publish_with_bus_python_queue, 5_000)
    run_bench("publish (in-memory bus, 1 live subscriber)", bench_publish_with_live_subscriber, 5_000)

    print("\n--- Read (full reconstruction into Pydantic instances) ---")
    run_bench("query (eager, returns list)", bench_query_eager, 5_000)
    run_bench("iter_query (batch_size=500)", bench_iter_query, 5_000)
    run_bench("iter_query_for_consumer", bench_query_for_consumer, 5_000)

    print("\n--- Adapter only (no RDF serialize / reconstruct) ---")
    run_bench("adapter.append", bench_adapter_append_only, 10_000)
    run_bench("adapter.query", bench_adapter_query_only, 10_000)
    print()


if __name__ == "__main__":
    main()
