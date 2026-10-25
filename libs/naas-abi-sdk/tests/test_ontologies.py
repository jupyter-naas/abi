import asyncio
import logging
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from naas_abi_sdk.discovery import DiscoveryConfiguration
from naas_abi_sdk.module import BaseModule, ModuleDependencies, run_module
from naas_abi_sdk.ontologies import (
    MAX_SOURCE_LENGTH,
    OntologyFile,
    OntologyLoader,
    declared_ontologies,
    discover_ontologies,
    schema_source,
)
from naas_abi_sdk.services.errors import ServiceError
from naas_abi_sdk.transport import RPCError

TTL = "@prefix ex: <http://example.org/> .\nex:Thing a ex:Class .\n"


def _package(monkeypatch, tmp_path, files: dict[str, str], name="pkg_under_test"):
    """A module package on disk with an ontologies/ folder; returns a module class
    defined in it (the SDK finds ontologies/ next to the class's package)."""
    package = tmp_path / name
    for relative, text in files.items():
        path = package / "ontologies" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    module = types.ModuleType(name)
    module.__file__ = str(package / "__init__.py")
    monkeypatch.setitem(sys.modules, name, module)

    class Module(BaseModule):
        module_id = "acme.foo"
        dependencies = ModuleDependencies(services=("triple_store",))

    Module.__module__ = name
    return Module


def _in_package(module):
    """A subclass is found in the package of its base: set ``__module__`` as a module
    defined in ``__init__.py`` has it."""

    def decorate(cls):
        cls.__module__ = module.__module__
        return cls

    return decorate


def test_discovery_finds_every_ttl_except_sandbox(monkeypatch, tmp_path):
    module = _package(
        monkeypatch,
        tmp_path,
        {
            "modules/FooOntology.ttl": TTL,
            "queries/deep/Bar.ttl": TTL,
            "Top.ttl": TTL,
            "sandbox/Draft.ttl": TTL,
            "modules/Sandbox_Wip.ttl": TTL,
            "README.md": "not an ontology",
            "modules/data.json": "{}",
        },
    )

    files = module.get_ontologies()

    assert [f.name for f in files] == [
        "Top.ttl",
        "modules/FooOntology.ttl",
        "queries/deep/Bar.ttl",
    ]
    assert [f.source("acme.foo") for f in files] == [
        "module/acme.foo/Top.ttl",
        "module/acme.foo/modules/FooOntology.ttl",
        "module/acme.foo/queries/deep/Bar.ttl",
    ]
    assert all(f.path.is_file() for f in files)


def test_sandbox_is_judged_under_ontologies_not_in_the_install_path(
    monkeypatch, tmp_path
):
    module = _package(
        monkeypatch,
        tmp_path / "sandbox-checkout",
        {"modules/FooOntology.ttl": TTL},
    )

    assert [f.name for f in discover_ontologies(module)] == ["modules/FooOntology.ttl"]


def test_a_module_without_an_ontologies_folder_has_none(monkeypatch, tmp_path):
    module = _package(monkeypatch, tmp_path, {})
    (tmp_path / "pkg_under_test").mkdir(exist_ok=True)

    assert module.get_ontologies() == ()
    assert BaseModule.get_ontologies() == ()


def test_declared_ontologies_replace_discovery(monkeypatch, tmp_path):
    module = _package(
        monkeypatch,
        tmp_path,
        {"modules/FooOntology.ttl": TTL, "modules/Other.ttl": TTL},
    )
    module.ontologies = ("modules/Other.ttl",)
    assert [f.name for f in module.get_ontologies()] == ["modules/Other.ttl"]

    module.ontologies = ()
    del module._ontology_files
    assert module.get_ontologies() == ()

    module.ontologies = (Path("modules/Missing.ttl"),)
    del module._ontology_files
    with pytest.raises(ValueError, match="not a file of the module's ontologies"):
        module.get_ontologies()
    with pytest.raises(ValueError, match="not a file"):
        declared_ontologies(module, ("../outside.ttl",))


@pytest.mark.parametrize(
    "name",
    [
        "Foo.owl",
        "../Foo.ttl",
        "a/../Foo.ttl",
        "./Foo.ttl",
        "a//Foo.ttl",
        "/Foo.ttl",
        "a b.ttl",
        'a"b.ttl',
        "a\\b.ttl",
        "é.ttl",
        "a" * MAX_SOURCE_LENGTH + ".ttl",
    ],
)
def test_names_the_engine_would_refuse_fail_before_sending(name):
    with pytest.raises(ValueError, match="Ontology"):
        schema_source("acme.foo", name)


def test_a_module_id_that_is_not_a_name_is_refused():
    with pytest.raises(ValueError, match="Not a module id"):
        schema_source("acme/foo", "Foo.ttl")
    assert (
        schema_source("acme.crm:v2", "a-b_c.1.ttl") == "module/acme.crm:v2/a-b_c.1.ttl"
    )


def _fake_client(monkeypatch, load=None):
    """A client whose triple store records the loads it is sent."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    sent: list[tuple[str, bytes]] = []

    async def load_schema(request):
        if load is not None:
            load(request)
        sent.append((request.source, request.content_ttl))
        return SimpleNamespace(changed=True)

    client.triple_store.load_schema = load_schema
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", lambda *a, **k: client)
    return sent


def _discovery(monkeypatch, events=None):
    """Discovery that stages a rollout's generation until the test cuts it over."""

    class Session:
        def __init__(self, client, descriptor, rollout_id="", rollout_modules=()):
            self.rollout_id, self.instance_id = rollout_id, "instance"
            self.initialized = self.draining = False
            self.status, self.task = "STARTING", None
            self.drain_requested = asyncio.Event()

        async def start(self):
            pass

        async def renew(self):
            if self.initialized and self.status == "STARTING":
                self.status = "STAGED" if self.rollout_id else "READY"

        async def close(self):
            pass

    monkeypatch.setattr("naas_abi_sdk.module.DiscoverySession", Session)


async def _until(condition, seconds=3.0):
    for _ in range(int(seconds / 0.01)):
        if condition():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not met")


def test_a_ready_instance_sends_each_file_under_its_module_id(monkeypatch, tmp_path):
    module = _package(
        monkeypatch,
        tmp_path,
        {"modules/FooOntology.ttl": TTL, "sandbox/Draft.ttl": "draft"},
    )
    sent = _fake_client(monkeypatch)
    _discovery(monkeypatch)

    @_in_package(module)
    class Ready(module):
        async def run(self):
            await _until(lambda: sent)
            return list(sent)

    seen = asyncio.run(
        run_module(
            Ready,
            url="nats://unused",
            token="t",
            discovery=DiscoveryConfiguration(refresh_seconds=0.01),
        )
    )

    assert seen == [("module/acme.foo/modules/FooOntology.ttl", TTL.encode())]


def test_a_staged_generation_sends_its_ontologies_only_after_the_cutover(
    monkeypatch, tmp_path
):
    module = _package(monkeypatch, tmp_path, {"Foo.ttl": TTL})
    sent = _fake_client(monkeypatch)
    _discovery(monkeypatch)

    @_in_package(module)
    class Staged(module):
        async def run(self):
            session = self._discovery_session
            assert session.status == "STAGED"
            await asyncio.sleep(0.1)
            assert sent == []  # the live generation's ontologies stay until cutover
            session.status = "READY"
            await _until(lambda: sent)
            return list(sent)

    seen = asyncio.run(
        run_module(
            Staged,
            url="nats://unused",
            token="t",
            discovery=DiscoveryConfiguration(
                rollout_id="release-2", refresh_seconds=0.01
            ),
        )
    )

    assert seen == [("module/acme.foo/Foo.ttl", TTL.encode())]


def test_a_degraded_instance_sends_too(monkeypatch, tmp_path):
    module = _package(monkeypatch, tmp_path, {"Foo.ttl": TTL})
    sent = _fake_client(monkeypatch)
    _discovery(monkeypatch)

    @_in_package(module)
    class Degraded(module):
        async def run(self):
            self._discovery_session.status = "DEGRADED"
            await _until(lambda: sent)
            return len(sent)

    assert (
        asyncio.run(
            run_module(
                Degraded,
                url="nats://unused",
                token="t",
                discovery=DiscoveryConfiguration(
                    rollout_id="release-2", refresh_seconds=0.01
                ),
            )
        )
        == 1
    )


def test_a_staged_generation_that_drains_never_sends(monkeypatch, tmp_path):
    module = _package(monkeypatch, tmp_path, {"Foo.ttl": TTL})
    sent = _fake_client(monkeypatch)
    _discovery(monkeypatch)

    @_in_package(module)
    class Abandoned(module):
        async def run(self):
            await asyncio.sleep(0.05)
            self._discovery_session.drain_requested.set()  # SIGTERM while staged
            await asyncio.Event().wait()

    assert (
        asyncio.run(
            run_module(
                Abandoned,
                url="nats://unused",
                token="t",
                discovery=DiscoveryConfiguration(
                    rollout_id="release-2", refresh_seconds=0.01
                ),
            )
        )
        is None
    )
    assert sent == []


def test_without_discovery_there_is_nothing_to_wait_for(monkeypatch, tmp_path):
    module = _package(monkeypatch, tmp_path, {"Foo.ttl": TTL})
    sent = _fake_client(monkeypatch)

    @_in_package(module)
    class Plain(module):
        async def run(self):
            await _until(lambda: sent)
            return list(sent)

    assert asyncio.run(run_module(Plain, url="nats://unused", token="t")) == [
        ("module/acme.foo/Foo.ttl", TTL.encode())
    ]


def test_a_module_with_ontologies_must_declare_triple_store(monkeypatch, tmp_path):
    module = _package(monkeypatch, tmp_path, {"modules/Foo.ttl": TTL})
    module.dependencies = ModuleDependencies(services=("document",))
    connected = []
    monkeypatch.setattr(
        "naas_abi_sdk.module.ABIClient", lambda *a, **k: connected.append(1)
    )

    with pytest.raises(ValueError, match="does not declare the triple_store service"):
        asyncio.run(run_module(module, url="nats://unused", token="t"))
    assert connected == []  # it stops before it connects


def test_a_file_the_engine_would_refuse_stops_the_module_before_it_connects(
    monkeypatch, tmp_path
):
    module = _package(monkeypatch, tmp_path, {"with space.ttl": TTL})
    connected = []
    monkeypatch.setattr(
        "naas_abi_sdk.module.ABIClient", lambda *a, **k: connected.append(1)
    )

    with pytest.raises(ValueError, match="with space.ttl"):
        asyncio.run(run_module(module, url="nats://unused", token="t"))
    assert connected == []


def test_a_module_without_ontologies_needs_no_triple_store(monkeypatch, tmp_path):
    module = _package(monkeypatch, tmp_path, {})
    module.dependencies = ModuleDependencies()
    (tmp_path / "pkg_under_test").mkdir(exist_ok=True)
    _fake_client(monkeypatch)

    @_in_package(module)
    class Plain(module):
        async def run(self):
            return "ran"

    assert asyncio.run(run_module(Plain, url="nats://unused", token="t")) == "ran"


def test_a_failed_load_is_logged_retried_and_does_not_change_readiness(
    monkeypatch, tmp_path, caplog
):
    module = _package(monkeypatch, tmp_path, {"Foo.ttl": TTL})
    attempts = []

    def load(request):
        attempts.append(request.source)
        if len(attempts) < 3:
            raise RPCError("UNAVAILABLE", "engine busy")

    sent = _fake_client(monkeypatch, load)
    _discovery(monkeypatch)
    monkeypatch.setattr("naas_abi_sdk.ontologies.RETRY_FIRST_SECONDS", 0.01)
    monkeypatch.setattr("naas_abi_sdk.ontologies.RETRY_MAX_SECONDS", 0.02)

    @_in_package(module)
    class Failing(module):
        async def run(self):
            await _until(lambda: sent)
            return self._discovery_session.status, len(attempts)

    with caplog.at_level(logging.ERROR, logger="naas_abi_sdk.ontologies"):
        status, count = asyncio.run(
            run_module(
                Failing,
                url="nats://unused",
                token="t",
                discovery=DiscoveryConfiguration(refresh_seconds=0.01),
            )
        )

    assert (status, count) == ("READY", 3)
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 2
    assert "module/acme.foo/Foo.ttl" in errors[0].getMessage()
    assert "engine busy" in errors[0].getMessage()


def test_the_loader_retries_with_a_doubling_delay_up_to_a_cap(monkeypatch, tmp_path):
    path = tmp_path / "Foo.ttl"
    path.write_text(TTL)
    delays: list[float] = []
    calls = []
    real_sleep = asyncio.sleep

    class Store:
        async def load_schema(self, source, content):
            calls.append(source)
            if len(calls) < 6:
                raise ServiceError("PERMISSION_DENIED", "no")
            return False

    async def sleep(delay):
        delays.append(delay)
        await real_sleep(0)

    async def scenario():
        loader = OntologyLoader(
            Store(),  # type: ignore[arg-type]
            "acme.foo",
            (OntologyFile(path, "Foo.ttl"),),
            retry_first_seconds=1.0,
            retry_max_seconds=4.0,
        )
        monkeypatch.setattr(asyncio, "sleep", sleep)
        await loader.run()
        assert loader.pending == {}

    asyncio.run(scenario())

    assert delays == [1.0, 2.0, 4.0, 4.0, 4.0]


def test_the_loader_reads_the_file_again_for_each_attempt(tmp_path):
    path = tmp_path / "Foo.ttl"
    path.write_text(TTL)
    seen: list[bytes] = []

    class Store:
        async def load_schema(self, source, content):
            seen.append(content)
            if len(seen) == 1:
                path.write_text(TTL + "ex:Other a ex:Class .\n")
                raise ServiceError("UNAVAILABLE", "again")
            return True

    async def scenario():
        await OntologyLoader(
            Store(),  # type: ignore[arg-type]
            "acme.foo",
            (OntologyFile(path, "Foo.ttl"),),
            retry_first_seconds=0.001,
        ).run()

    asyncio.run(scenario())

    assert seen == [TTL.encode(), (TTL + "ex:Other a ex:Class .\n").encode()]
