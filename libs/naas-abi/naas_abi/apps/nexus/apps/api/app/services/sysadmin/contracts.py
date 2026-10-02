"""Generic adapter contracts, one per port.

An adapter's test subclasses the contract as ``Test...`` and provides the fixture
the contract names, describing the deployment written in its docstring. A new
adapter is validated by doing the same.
"""

from __future__ import annotations

import asyncio
import functools
import inspect

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import RunNotFound
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AuditRecord,
    AuditUnavailable,
    InvalidResource,
    ResourceNotFound,
    ResourceTooLarge,
    UnsupportedOperation,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import (
    ServiceCount,
    SpanEvent,
    TraceQuery,
    TraceRoot,
)


class ServiceConfigurationSourceContract:
    """fixture ``source``: document on postgresql, secrets from dotenv then naas,
    cache with a hot redis tier and a cold fs tier."""

    def test_lists_each_service_once_with_its_adapter_kinds(self, source):
        services = {s.name: s for s in asyncio.run(source.list_configured())}

        assert len(services) == len(asyncio.run(source.list_configured()))
        assert services["document"].adapters == ("postgresql",)
        assert services["secret"].adapters == ("dotenv", "naas")
        assert services["cache"].adapters == ("redis:hot", "fs:cold")

    def test_adapter_kinds_are_plain_strings(self, source):
        for service in asyncio.run(source.list_configured()):
            assert all(isinstance(a, str) and a for a in service.adapters), service


class EngineModuleSourceContract:
    """fixture ``source``: one module ``acme.jobs`` ("Acme jobs") with one agent and a
    ``nightly`` job running every 1h, plus ``acme.quiet`` with nothing."""

    def test_lists_loaded_modules_with_their_contents(self, source):
        modules = {m.module_id: m for m in asyncio.run(source.list_modules())}

        assert set(modules) == {"acme.jobs", "acme.quiet"}
        acme = modules["acme.jobs"]
        assert acme.name == "Acme jobs"
        assert acme.agents == 1
        assert [(j.name, j.triggers) for j in acme.jobs] == [("nightly", ("every 1h",))]
        assert modules["acme.quiet"].jobs == ()


class MicroServiceMonitorContract:
    """fixture ``monitor``: two ``document`` instances (``get`` answered 3 and 2
    requests) and one ``keyvalue`` instance with no requests."""

    def test_lists_every_instance_with_endpoint_stats(self, monitor):
        instances = asyncio.run(monitor.list_instances())

        assert sorted(i.name for i in instances) == ["document", "document", "keyvalue"]
        documents = [i for i in instances if i.name == "document"]
        assert len({i.instance_id for i in documents}) == 2
        assert sorted(i.requests for i in documents) == [2, 3]
        assert all(
            e.subject.startswith("abi.svc.document.v1.") for i in documents for e in i.endpoints
        )


class UnavailableMicroServiceMonitorContract:
    """fixture ``monitor``: one that cannot reach NATS."""

    def test_raises_source_unavailable(self, monitor):
        try:
            asyncio.run(monitor.list_instances())
        except SourceUnavailable as exc:
            assert exc.reason
        else:
            raise AssertionError("expected SourceUnavailable")


class ModuleRegistryContract:
    """fixture ``registry``: ``ops.researcher`` READY (agent ``Researcher``, job
    ``digest`` every 10m) and ``ops.orchestrator`` STARTING (agent ``Orchestrator``)."""

    def test_lists_every_registered_instance(self, registry):
        instances = {i.module_id: i for i in asyncio.run(registry.list_instances())}

        assert set(instances) == {"ops.researcher", "ops.orchestrator"}
        researcher = instances["ops.researcher"]
        assert researcher.status == "READY"
        assert researcher.agents == ("Researcher",)
        assert [(j.name, j.triggers) for j in researcher.jobs] == [("digest", ("every 10m",))]
        assert instances["ops.orchestrator"].status == "STARTING"
        assert researcher.expires_at > 0


class NatsServerMonitorContract:
    """fixture ``monitor``: a JetStream server with exactly two client connections,
    ``api`` and an unnamed one, and streams ``KV_ABI_DISCOVERY_zen`` (1 message) and
    ``ABI_JOBS_zen`` (4 messages, consumer ``job-a-b`` with 1 pending)."""

    def test_server_summary(self, monitor):
        server = asyncio.run(monitor.server())

        assert server.version.count(".") == 2 and server.server_id
        assert server.jetstream is True
        assert server.connections == 2
        assert server.max_payload > 0

    def test_connections(self, monitor):
        connections = asyncio.run(monitor.connections())

        assert sorted(c.name for c in connections) == ["", "api"]
        assert all(c.cid > 0 for c in connections)

    def test_jetstream_streams_and_consumers(self, monitor):
        summary = asyncio.run(monitor.jetstream())
        streams = {s.name: s for s in summary.streams}

        assert streams["KV_ABI_DISCOVERY_zen"].kind == "kv"
        assert streams["ABI_JOBS_zen"].kind == "jobs"
        assert summary.messages == 5
        (consumer,) = streams["ABI_JOBS_zen"].consumers
        assert (consumer.name, consumer.pending) == ("job-a-b", 1)
        assert summary.consumers == 1


# --- service data (resources.py) -------------------------------------------------------


def _all_entries(resources, parent=""):
    return asyncio.run(resources.list(parent)).entries


def _by_name(resources, name, parent=""):
    (entry,) = [e for e in _all_entries(resources, parent) if e.name == name]
    return entry


def _shown(resources, resource_id):
    detail = asyncio.run(resources.read(resource_id, reveal=True))
    assert detail.content is not None
    return detail.content.text


def _expect(exc_type, make):
    """Run ``make()`` (a zero-argument callable returning an awaitable or, for
    eager loop wrappers, the result) and return the ``exc_type`` it raises."""
    try:
        result = make()
        if inspect.isawaitable(result):
            asyncio.run(result)
    except exc_type as exc:
        return exc
    raise AssertionError(f"expected {exc_type.__name__}")


class ServiceResourcesContract:
    """fixture ``resources``: a browsable service seeded with ``fixtures.SEED_ITEMS``
    directly under ``base`` (``""``: the root) and, when ``containers = True``,
    ``SEED_CONTAINER`` under ``base`` holding ``SEED_NESTED``. Seed values are
    stored with ``encode``.

    Knobs for structured services: ``child`` builds an id under a container,
    ``encode`` turns a seed text into what the service stores (JSON, Turtle...),
    ``assert_shown`` / ``assert_downloaded`` compare a preview or a download with
    the seed text, ``sized = False`` when ``size`` is not the stored byte count,
    ``masked = True`` when values are hidden until revealed. Writing and deleting
    are tested when the capabilities and entry actions offer them."""

    base = ""
    containers = False
    masked = False
    sized = True
    actions = {"read", "download", "write", "delete", "reveal"}
    # Entries the service always lists beside the seed (e.g. a built-in schema graph).
    extra_names: frozenset[str] = frozenset()

    def child(self, name: str) -> str:
        return f"{self.base}/{name}" if self.base else name

    def encode(self, text: str) -> bytes:
        return text.encode()

    def assert_shown(self, shown: str | None, text: str) -> None:
        assert shown == text

    def assert_downloaded(self, data: bytes, text: str) -> None:
        assert data == self.encode(text)

    def _names(self):
        from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures

        names = set(fixtures.SEED_ITEMS) | set(self.extra_names)
        if self.containers:
            names.add(fixtures.SEED_CONTAINER)
        return names

    def _alpha(self, resources):
        return _by_name(resources, "alpha", self.base)

    def test_lists_the_seed_in_a_stable_order(self, resources):
        from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures

        page = asyncio.run(resources.list(self.base))
        items = [e for e in page.entries if e.name in fixtures.SEED_ITEMS]

        assert resources.capabilities.browse
        assert page.parent == self.base and page.listable
        assert {e.name for e in page.entries} == self._names()
        assert [e.id for e in page.entries] == [e.id for e in _all_entries(resources, self.base)]
        assert all(e.kind == "item" and "read" in e.actions for e in items)
        assert all(set(e.actions) <= self.actions for e in page.entries)

    def test_pages_with_a_cursor_without_gaps_or_repeats(self, resources):
        ids, cursor = [], None
        for _ in range(10):
            page = asyncio.run(resources.list(self.base, cursor=cursor, limit=1))
            assert len(page.entries) <= 1
            ids += [e.id for e in page.entries]
            cursor = page.next_cursor
            if cursor is None:
                break

        assert ids == [e.id for e in _all_entries(resources, self.base)]

    def test_stat_and_read_an_item(self, resources):
        alpha = self._alpha(resources)
        stat = asyncio.run(resources.stat(alpha.id))
        detail = asyncio.run(resources.read(alpha.id))

        assert (stat.id, stat.kind) == (alpha.id, "item")
        if self.masked:
            # A masked value's size is not disclosed either.
            assert stat.size is None
        elif self.sized:
            assert stat.size == len(self.encode("first value"))
        assert detail.entry.id == alpha.id
        assert detail.content is not None
        if self.masked:
            assert (detail.content.encoding, detail.content.text) == ("masked", None)
            assert "first value" not in repr(detail)
        else:
            assert detail.content.encoding == "text"
            self.assert_shown(detail.content.text, "first value")

    def test_reveal_matches_the_capability(self, resources):
        alpha = self._alpha(resources)

        assert resources.capabilities.reveal is self.masked
        assert ("reveal" in alpha.actions) is self.masked
        self.assert_shown(_shown(resources, alpha.id), "first value")

    def test_unknown_ids_are_not_found(self, resources):
        missing = self.child("no-such-entry")
        for call in (resources.stat, resources.read):
            exc = _expect(ResourceNotFound, functools.partial(call, missing))
            assert exc.resource_id == missing

    def test_write_creates_then_replaces(self, resources):
        if not resources.capabilities.create:
            return
        created = asyncio.run(resources.write(self.child("epsilon"), self.encode("new value")))
        assert (created.name, created.kind) == ("epsilon", "item")
        assert "write" in created.actions
        self.assert_shown(_shown(resources, created.id), "new value")

        asyncio.run(resources.write(created.id, self.encode("newer value")))

        self.assert_shown(_shown(resources, created.id), "newer value")
        assert "epsilon" in {e.name for e in _all_entries(resources, self.base)}

    def test_delete_removes_an_item(self, resources):
        beta = _by_name(resources, "beta", self.base)
        if "delete" not in beta.actions:
            _expect(UnsupportedOperation, lambda: resources.delete(beta.id))
            return

        asyncio.run(resources.delete(beta.id))

        assert "beta" not in {e.name for e in _all_entries(resources, self.base)}
        _expect(ResourceNotFound, lambda: resources.stat(beta.id))
        _expect(ResourceNotFound, lambda: resources.delete(beta.id))

    def test_download_is_bounded(self, resources):
        alpha = self._alpha(resources)
        if "download" not in alpha.actions:
            return

        self.assert_downloaded(
            asyncio.run(resources.download(alpha.id, max_bytes=1 << 20)), "first value"
        )
        exc = _expect(ResourceTooLarge, lambda: resources.download(alpha.id, max_bytes=3))
        assert exc.limit == 3

    def test_an_item_is_not_a_container(self, resources):
        alpha = self._alpha(resources)
        _expect(InvalidResource, lambda: resources.list(alpha.id))

    def test_containers_hold_entries(self, resources):
        from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures

        if not self.containers:
            return
        nested = _by_name(resources, fixtures.SEED_CONTAINER, self.base)
        assert nested.kind == "container"
        assert asyncio.run(resources.stat(nested.id)).kind == "container"

        (delta,) = _all_entries(resources, nested.id)

        assert delta.name == "delta"
        self.assert_shown(_shown(resources, delta.id), "fourth value")
        _expect(InvalidResource, lambda: resources.read(nested.id))


class ReadOnlyResourcesContract:
    """fixture ``resources``: a read-only service (logs, registries) with at least
    three entries under ``base``, which may be containers or items."""

    base = ""

    def _items(self, resources):
        """Items under ``base``, descending one container level when needed."""
        entries = _all_entries(resources, self.base)
        items = [e for e in entries if e.kind == "item"]
        if not items:
            containers = [e for e in entries if e.kind == "container"]
            assert containers, "nothing listed"
            items = [e for e in _all_entries(resources, containers[0].id) if e.kind == "item"]
        assert items, "no items to read"
        return items

    def test_lists_and_pages_without_gaps_or_repeats(self, resources):
        full = [e.id for e in _all_entries(resources, self.base)]
        ids, cursor = [], None
        for _ in range(len(full) + 2):
            page = asyncio.run(resources.list(self.base, cursor=cursor, limit=1))
            ids += [e.id for e in page.entries]
            cursor = page.next_cursor
            if cursor is None:
                break

        assert len(full) >= 3
        assert ids == full

    def test_items_can_be_stat_and_read(self, resources):
        for item in self._items(resources)[:3]:
            assert asyncio.run(resources.stat(item.id)).id == item.id
            detail = asyncio.run(resources.read(item.id))
            assert detail.content is not None and detail.content.encoding in ("text", "binary")
            assert "read" in item.actions

    def test_changes_are_unsupported(self, resources):
        item = self._items(resources)[0]

        assert resources.capabilities.create is False
        assert not {"write", "delete", "reveal"} & set(item.actions)
        _expect(UnsupportedOperation, lambda: resources.write(item.id, b"x"))
        _expect(UnsupportedOperation, lambda: resources.delete(item.id))

    def test_unknown_ids_are_not_found(self, resources):
        missing = f"{self.base}/no-such-entry" if self.base else "no-such-entry"
        _expect(ResourceNotFound, lambda: resources.stat(missing))


class AdminAuditLogContract:
    """fixtures ``audit`` (working), ``recorded`` (reads back what ``audit`` stored,
    oldest first, as AuditRecord) and ``broken_audit`` (cannot persist)."""

    def test_records_are_persisted_in_order(self, audit, recorded):
        action = AdminAction("u1", "secret", "reveal", "OPENAI_API_KEY")

        asyncio.run(audit.record(AuditRecord(action, "requested")))
        asyncio.run(audit.record(AuditRecord(action, "failed", error="boom")))

        assert recorded() == [
            AuditRecord(action, "requested"),
            AuditRecord(action, "failed", error="boom"),
        ]

    def test_history_is_newest_first_and_filters(self, audit):
        reveal = AdminAction("u1", "secret", "reveal", "OPENAI_API_KEY")
        delete = AdminAction("u1", "object_storage", "delete", "a/b.txt")
        for record in (
            AuditRecord(reveal, "requested"),
            AuditRecord(reveal, "succeeded"),
            AuditRecord(delete, "requested"),
            AuditRecord(delete, "failed", error="RuntimeError"),
        ):
            asyncio.run(audit.record(record))

        everything = asyncio.run(audit.history())
        secrets = asyncio.run(audit.history(service="secret"))
        one = asyncio.run(audit.history(service="object_storage", resource_id="a/b.txt", limit=1))

        assert [(e.operation, e.phase) for e in everything] == [
            ("delete", "failed"),
            ("delete", "requested"),
            ("reveal", "succeeded"),
            ("reveal", "requested"),
        ]
        assert all(e.at and e.actor for e in everything)
        assert [e.phase for e in secrets] == ["succeeded", "requested"]
        assert [(e.resource_id, e.error) for e in one] == [("a/b.txt", "RuntimeError")]

    def test_a_record_that_cannot_be_written_raises(self, broken_audit):
        action = AdminAction("u1", "object_storage", "delete", "a/b.txt")
        try:
            asyncio.run(broken_audit.record(AuditRecord(action, "requested")))
        except AuditUnavailable as exc:
            assert exc.reason
        else:
            raise AssertionError("expected AuditUnavailable")


# --- jobs (jobs.py) --------------------------------------------------------------------


class JobCatalogContract:
    """fixtures ``catalog`` and ``expected`` (the JobDefinitions it must list)."""

    def test_lists_its_definitions_with_structured_triggers(self, catalog, expected):
        jobs = sorted(asyncio.run(catalog.list_jobs()), key=lambda j: j.key)

        assert catalog.source
        assert jobs == sorted(expected, key=lambda j: j.key)
        assert len({j.key for j in jobs}) == len(jobs)
        assert all(t.kind in ("cron", "every", "event") for j in jobs for t in j.triggers)


class JobRunStoreContract:
    """fixture ``store``: seeded with ``fixtures.job_runs()``."""

    MODULES = ["acme.jobs", "acme.other"]

    @staticmethod
    def _ids(runs):
        return [r.run_id for r in runs]

    def test_lists_runs_newest_first_across_modules(self, store):
        runs = asyncio.run(store.list_runs(self.MODULES))

        assert self._ids(runs) == ["sync:9", "report:1", "nightly:3", "nightly:2"]
        assert asyncio.run(store.list_runs(self.MODULES, limit=2))[-1].run_id == "report:1"

    def test_filters_by_job_status_trigger_and_time(self, store):
        def ids(**kwargs):
            return self._ids(asyncio.run(store.list_runs(self.MODULES, **kwargs)))

        assert ids(job="nightly") == ["nightly:3", "nightly:2"]
        assert ids(statuses=["FAILED", "TIMED_OUT"]) == ["report:1", "nightly:2"]
        assert ids(trigger_kind="schedule") == ["nightly:3", "nightly:2"]
        assert ids(before="2026-10-02T06:00:01+00:00") == ["nightly:2"]
        assert self._ids(asyncio.run(store.list_runs(["acme.other"]))) == ["report:1"]
        assert asyncio.run(store.list_runs(["no.such.module"])) == []

    def test_recent_and_running(self, store):
        assert self._ids(asyncio.run(store.recent("acme.jobs", "nightly", 1))) == ["nightly:3"]
        assert self._ids(asyncio.run(store.running("acme.jobs"))) == ["sync:9"]
        assert asyncio.run(store.running("acme.other")) == []
        assert asyncio.run(store.recent("no.such.module", "nightly")) == []

    def test_gets_a_run_with_its_details(self, store):
        run = asyncio.run(store.get_run("acme.jobs", "nightly:3"))

        assert (run.job, run.status, run.attempt, run.max_attempts) == (
            "nightly",
            "SUCCEEDED",
            1,
            3,
        )
        assert (run.trigger.kind, run.trigger.scheduler) == (
            "schedule",
            "abi.jobs.zen.schedule.m.j.0",
        )
        assert run.result == {"rows": 3} and run.logs == ("synced 3 rows",)
        assert run.fired_at == "2026-10-02T06:00:00+00:00"
        assert run.trace_id == "b" * 32 and run.duration_ms == 30500
        assert asyncio.run(store.get_run("acme.jobs", "sync:9")).payload == {"since": "2026-10-01"}

    def test_unknown_runs_are_not_found(self, store):
        for module, run_id in (("acme.jobs", "nightly:99"), ("no.such.module", "x:1")):
            exc = _expect(RunNotFound, lambda m=module, r=run_id: store.get_run(m, r))
            assert exc.run_id == run_id


# --- traces (traces.py) ----------------------------------------------------------------


class TraceStoreContract:
    """fixtures ``store``: a backend holding ``fixtures.traces(now)`` (traces A, B
    and C), and ``trace_ids``: their ids as ``{"a": ..., "b": ..., "c": ...}``."""

    @staticmethod
    def _search(store, **query):
        return asyncio.run(store.search(TraceQuery(**query).validated()))

    def _ids(self, store, trace_ids, **query):
        names = {v: k for k, v in trace_ids.items()}
        return [names.get(t.trace_id, t.trace_id) for t in self._search(store, **query)]

    def test_lists_services_and_their_operations(self, store):
        assert asyncio.run(store.services()) == ["nexus-api", "ops-researcher", "zen-engine"]
        assert asyncio.run(store.operations("nexus-api")) == [
            ("GET /api/search", "server"),
            ("GET /health", "server"),
        ]
        assert asyncio.run(store.operations("ops-researcher")) == [
            ("digest", "consumer"),
            ("fetch", "internal"),
        ]
        assert asyncio.run(store.operations("no-such-service")) == []

    def test_searches_every_service_newest_first(self, store, trace_ids):
        a, b = (s for s in self._search(store, lookback="15m"))

        assert (a.trace_id, b.trace_id) == (trace_ids["b"], trace_ids["a"])
        assert (a.root, a.spans, a.errors, a.duration_ms) == (
            TraceRoot("ops-researcher", "digest"),
            2,
            1,
            1500.0,
        )
        assert a.services == (ServiceCount("ops-researcher", 2, 1),)
        assert (b.root, b.spans, b.errors, b.duration_ms) == (
            TraceRoot("nexus-api", "GET /api/search"),
            2,
            0,
            250.0,
        )
        assert b.services == (ServiceCount("nexus-api", 1, 0), ServiceCount("zen-engine", 1, 0))
        assert a.start > b.start

    def test_the_lookback_bounds_the_search(self, store, trace_ids):
        assert self._ids(store, trace_ids) == ["b", "a"]  # 1h by default
        assert self._ids(store, trace_ids, lookback="6h") == ["b", "a", "c"]

    def test_filters(self, store, trace_ids):
        def ids(**query):
            return self._ids(store, trace_ids, **query)

        assert ids(service="zen-engine") == ["a"]
        assert ids(service="ops-researcher") == ["b"]
        assert ids(operation="document/get") == ["a"]
        assert ids(service="ops-researcher", operation="fetch") == ["b"]
        assert ids(service="nexus-api", operation="document/get") == []
        assert ids(service="no-such-service") == []
        assert ids(errors=True) == ["b"]
        assert ids(min_duration_ms=1000) == ["b"]
        assert ids(max_duration_ms=1000) == ["a"]
        assert ids(min_duration_ms=100, max_duration_ms=300) == ["a"]
        assert ids(limit=1) == ["b"]

    def test_gets_a_whole_trace(self, store, trace_ids):
        trace = asyncio.run(store.get(trace_ids["b"]))

        assert trace is not None and trace.trace_id == trace_ids["b"]
        digest, fetch = trace.spans
        assert (trace.duration_ms, trace.truncated) == (1500.0, False)
        assert trace.services == (ServiceCount("ops-researcher", 2, 1),)
        assert (digest.name, digest.kind, digest.parent_id, digest.start_ms) == (
            "digest",
            "consumer",
            None,
            0.0,
        )
        assert (fetch.parent_id, fetch.kind, fetch.start_ms, fetch.duration_ms) == (
            digest.span_id,
            "internal",
            100.0,
            400.0,
        )
        assert (fetch.status, fetch.status_message) == ("error", "boom")
        assert fetch.events == (SpanEvent("retry", 50.0, {"attempt": 2}),)
        assert fetch.resource["service.name"] == "ops-researcher"
        assert all(len(s.span_id) == 16 and s.span_id == s.span_id.lower() for s in trace.spans)

    def test_a_trace_spans_its_services(self, store, trace_ids):
        trace = asyncio.run(store.get(trace_ids["a"]))

        assert trace is not None
        search, get = trace.spans
        assert (search.service, search.kind, search.status) == ("nexus-api", "server", "unset")
        assert (get.service, get.kind, get.status, get.parent_id) == (
            "zen-engine",
            "client",
            "ok",
            search.span_id,
        )
        assert (get.start_ms, get.duration_ms) == (10.0, 200.0)
        assert get.attributes["rpc.service"] == "document"
        summary = next(s for s in self._search(store) if s.trace_id == trace_ids["a"])
        assert trace.start == summary.start

    def test_unknown_traces_are_none(self, store):
        assert asyncio.run(store.get("0" * 31 + "1")) is None


class UnavailableTraceStoreContract:
    """fixture ``store``: one that cannot reach its backend."""

    def test_every_call_raises_source_unavailable(self, store):
        calls = (
            store.services,
            lambda: store.operations("nexus-api"),
            lambda: store.search(TraceQuery()),
            lambda: store.get("0" * 32),
        )
        for call in calls:
            exc = _expect(SourceUnavailable, call)
            assert exc.source == "tracing" and exc.reason
