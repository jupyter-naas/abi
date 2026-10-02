"""Generic adapter contracts, one per port.

An adapter's test subclasses the contract as ``Test...`` and provides the fixture
the contract names, describing the deployment written in its docstring. A new
adapter is validated by doing the same.
"""

from __future__ import annotations

import asyncio

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable


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
