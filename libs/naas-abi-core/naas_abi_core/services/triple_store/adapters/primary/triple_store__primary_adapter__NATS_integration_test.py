"""A remote module's ontologies reach the engine's schema graph, over a real broker.

An SDK module (``run_module``, logged in as the broker's ``module`` user, signing as its own
module id) sends the ``.ttl`` files of its ``ontologies/`` folder once discovery reports it
READY; the engine's triple store primary adapter stores them under
``module/<module_id>/<path>``. Run with ``--import-mode=importlib``; needs ``nats-server``.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import textwrap
import uuid
from pathlib import Path

import nats
import pytest
from naas_abi_core.engine import nats_overflow
from naas_abi_core.engine.nats_auth import module_key
from naas_abi_core.engine.nats_test_server import (
    login,
    native_nats_server,
    nats_server_binary,
)
from naas_abi_core.services.discovery.discovery_factory import start_discovery
from naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS import (
    TripleStorePrimaryAdapterNATS,
)
from naas_abi_core.services.triple_store.TripleStoreFactory import TripleStoreFactory
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import RDF, Graph, URIRef

SECRET = "triple-store-schema-integration-secret-32"
PASSWORDS = {"abi": "nats-abi-schema", "module": "nats-module-schema"}
SCHEMA_GRAPH = URIRef("http://ontology.naas.ai/graph/schema")
EX = "http://example.org/"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        nats_server_binary() is None, reason="nats-server not installed"
    ),
]

MODULE = textwrap.dedent(
    """
    import asyncio

    from naas_abi_sdk import BaseModule, ModuleDependencies


    class ABIModule(BaseModule):
        module_id = {module_id!r}
        dependencies = ModuleDependencies(services=("triple_store",))

        async def run(self):
            await asyncio.Event().wait()
    """
)


async def _start_engine(nc, service):
    """What the engine runs for these calls: the primary, the RPC overflow host that
    takes uploads above the broker limit, and discovery (a module is READY through it)."""
    overflow = nats_overflow.OverflowHost(SECRET)
    await overflow.start(nc)
    nats_overflow.install(overflow)
    primary = TripleStorePrimaryAdapterNATS(service, SECRET)
    await primary.start(nc)
    return overflow, primary, await start_discovery(nc, SECRET)


async def _stop_engine(nc, overflow, primary, discovery):
    await discovery.stop()
    await primary.stop()
    nats_overflow.uninstall(overflow)
    await overflow.stop()
    await nc.close()


def _ttl(*classes: str) -> str:
    return "@prefix ex: <http://example.org/> .\n" + "".join(
        f"ex:{name} a ex:Class .\n" for name in classes
    )


def _package(root: Path, name: str, module_id: str, files: dict[str, str]):
    """An SDK module package on disk, with its ``ontologies/`` folder."""
    name = f"{name}_{uuid.uuid4().hex[:8]}"  # a package is imported once per process
    package = root / name
    (package / "ontologies").mkdir(parents=True)
    (package / "__init__.py").write_text(MODULE.format(module_id=module_id))
    for relative, text in files.items():
        path = package / "ontologies" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    sys.path.insert(0, str(root))
    try:
        return importlib.import_module(name).ABIModule
    finally:
        sys.path.remove(str(root))


class _Spy:
    """Records every schema load the engine's service takes, and what it wrote."""

    def __init__(self, service: TripleStoreService) -> None:
        self.loads: list[tuple[str, bool]] = []
        original = service.load_schema_content

        def load(source, content, *args, **kwargs):
            changed = original(source, content, *args, **kwargs)
            self.loads.append((source, changed))
            return changed

        service.load_schema_content = load  # type: ignore[method-assign]

    async def wait_for(self, count: int) -> None:
        for _ in range(600):
            if len(self.loads) >= count:
                return
            await asyncio.sleep(0.05)
        raise AssertionError(f"expected {count} schema loads, saw {self.loads}")


def _schema_files(service: TripleStoreService) -> dict[str, str]:
    return {
        str(path): str(hash_)
        for path, hash_ in service.query(
            f"""PREFIX internal: <http://triple-store.internal#>
SELECT ?path ?hash WHERE {{ GRAPH <{SCHEMA_GRAPH}> {{
    ?s a internal:Schema ; internal:filePath ?path ; internal:hash ?hash }} }}"""
        )
    }


def _classes(service: TripleStoreService) -> set[str]:
    graph = Graph()
    for triple in service.query(
        f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{SCHEMA_GRAPH}> {{ ?s ?p ?o }} }}"
    ):
        graph.add(triple)  # type: ignore[arg-type]
    return {
        str(s).removeprefix(EX) for s in graph.subjects(RDF.type, URIRef(EX + "Class"))
    }


@pytest.fixture(params=[8 * 1024 * 1024, 4096], ids=["8MiB", "small-server-cap"])
def broker(request, tmp_path):
    with native_nats_server(
        tmp_path / "broker" if (tmp_path / "broker").mkdir() is None else tmp_path,
        jetstream=True,
        users=PASSWORDS,
        max_payload=request.param,
    ) as url:
        yield (
            login(url, "abi", PASSWORDS["abi"]),
            login(url, "module", PASSWORDS["module"]),
            request.param,
        )


def test_a_remote_modules_ontologies_load_once_ready_and_follow_the_file(
    broker, tmp_path
):
    from naas_abi_sdk import DiscoveryConfiguration, run_module
    from naas_abi_sdk.service_token import ModuleToken

    engine_url, module_url, max_payload = broker
    # Above the broker's limit when it is small: the file travels through RPC overflow.
    padding = "".join(f"ex:Pad{i} a ex:Class .\n" for i in range(600))
    big = max_payload == 4096
    module_id = "acme.ontologous"
    source = f"module/{module_id}/modules/FooOntology.ttl"
    foo = tmp_path / "packages"
    Module = _package(
        foo,
        "ontologous_pkg",
        module_id,
        {
            "modules/FooOntology.ttl": _ttl("Thing") + (padding if big else ""),
            "sandbox/Draft.ttl": _ttl("Draft"),
        },
    )
    ontology_file = (
        Path(str(sys.modules[Module.__module__].__file__)).parent
        / "ontologies/modules/FooOntology.ttl"
    )
    if big:
        assert ontology_file.stat().st_size > max_payload

    def run(module_type=Module, mid=module_id) -> asyncio.Task:
        return asyncio.create_task(
            run_module(
                module_type,
                url=module_url,
                token=ModuleToken(mid, module_key(SECRET, mid)),
                discovery=DiscoveryConfiguration(refresh_seconds=0.1),
            )
        )

    async def stop(task: asyncio.Task) -> None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def scenario():
        nc = await nats.connect(engine_url)
        service = TripleStoreFactory.TripleStoreServiceOxigraphEmbedded(
            str(tmp_path / "store")
        )
        spy = _Spy(service)
        overflow, primary, discovery = await _start_engine(nc, service)
        try:
            # First start: the file is in the schema graph, the sandbox draft is not.
            first = run()
            await spy.wait_for(1)
            assert spy.loads == [(source, True)]
            files = _schema_files(service)
            assert list(files) == [source]
            assert "Thing" in _classes(service)
            assert "Draft" not in _classes(service)
            await stop(first)

            # A restart with the same file writes nothing.
            second = run()
            await spy.wait_for(2)
            assert spy.loads[1] == (source, False)
            assert _schema_files(service) == files
            await stop(second)

            # A changed file applies the diff.
            ontology_file.write_text(_ttl("Other") + (padding if big else ""))
            third = run()
            await spy.wait_for(3)
            assert spy.loads[2] == (source, True)
            assert _schema_files(service)[source] != files[source]
            classes = _classes(service)
            assert "Other" in classes and "Thing" not in classes
            await stop(third)
        finally:
            await _stop_engine(nc, overflow, primary, discovery)

    asyncio.run(asyncio.wait_for(scenario(), 90))


def test_a_module_cannot_load_under_another_modules_id_or_invalid_turtle(
    broker, tmp_path
):
    from naas_abi_sdk import DiscoveryConfiguration, run_module
    from naas_abi_sdk.service_token import ModuleToken
    from naas_abi_sdk.services.errors import ServiceError

    engine_url, module_url, _ = broker
    outcomes: dict[str, object] = {}

    async def scenario():
        from naas_abi_sdk import BaseModule, ModuleDependencies

        class A(BaseModule):
            module_id = "a"
            dependencies = ModuleDependencies(services=("triple_store",))

            async def run(self):
                store = self.engine.services.triple_store
                for label, source, text in (
                    ("other", "module/b/Stolen.ttl", _ttl("Stolen")),
                    ("invalid", "module/a/Broken.ttl", "this is not turtle"),
                    ("malformed", "module/a/../b/Stolen.ttl", _ttl("Stolen")),
                    ("internal", "module/a/Forged.ttl", _forged()),
                ):
                    try:
                        outcomes[label] = await store.load_schema(source, text)
                    except ServiceError as exc:
                        outcomes[label] = exc.code
                outcomes["own"] = await store.load_schema(
                    "module/a/Own.ttl", _ttl("Own")
                )
                return outcomes

        nc = await nats.connect(engine_url)
        service = TripleStoreFactory.TripleStoreServiceOxigraphEmbedded(
            str(tmp_path / "store")
        )
        overflow, primary, discovery = await _start_engine(nc, service)
        try:
            await run_module(
                A,
                url=module_url,
                token=ModuleToken("a", module_key(SECRET, "a")),
                discovery=DiscoveryConfiguration(refresh_seconds=0.1),
            )
            assert outcomes == {
                "other": "PERMISSION_DENIED",
                "invalid": "INVALID_ARGUMENT",
                "malformed": "INVALID_ARGUMENT",
                "internal": "INVALID_ARGUMENT",
                "own": True,
            }
            assert list(_schema_files(service)) == ["module/a/Own.ttl"]
            assert _classes(service) == {"Own"}
        finally:
            await _stop_engine(nc, overflow, primary, discovery)

    asyncio.run(asyncio.wait_for(scenario(), 60))


def _forged() -> str:
    return (
        "@prefix internal: <http://triple-store.internal#> .\n"
        '<http://example.org/x> a internal:Schema ; internal:filePath "module/b/X.ttl" .\n'
    )
