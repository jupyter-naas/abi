from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from naas_abi_core.engine.engine_loaders.EngineNATSDependencies import (
        EngineNATSDependencies,
    )
    from naas_abi_core.engine.engine_loaders.EngineOwnershipLoader import (
        EngineOwnershipLoader,
    )

from naas_abi_core import logger
from naas_abi_core.engine.context import (
    get_default_agent_checkpointer,
    set_default_agent_checkpointer,
    set_default_event_service,
    set_default_model_registry,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.engine_loaders import EngineTelemetryLoader
from naas_abi_core.engine.engine_loaders.EngineJobLoader import EngineJobLoader
from naas_abi_core.engine.engine_loaders.EngineModuleLoader import EngineModuleLoader
from naas_abi_core.engine.engine_loaders.EngineOntologyLoader import (
    EngineOntologyLoader,
)
from naas_abi_core.engine.engine_loaders.EngineServiceLoader import EngineServiceLoader
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.engine.ownership.ownership_service import Claim
from naas_abi_core.module.Module import BaseModule, ModuleDependencies


class Engine(IEngine):
    __nats_dependencies: EngineNATSDependencies | None
    __configuration: EngineConfiguration
    __engine_module_loader: EngineModuleLoader
    __engine_service_loader: EngineServiceLoader

    __modules: dict[
        str, BaseModule
    ]  # Must not set a default value to prevent modules to try to access modules inside constructors.

    __services: IEngine.Services

    # Started NATS primary adapters, if config.yaml has a top-level `nats:`
    # block -- otherwise always []. Consumed by shutdown() below.
    __nats_primary_adapters: list[object]
    __nats_runtime_started: bool
    # Hosts the modules' jobs (NATS mode only); stopped first in shutdown().
    __job_loader: EngineJobLoader | None
    # NATS mode: the lease that lets this engine serve (single-serving-engine ADR).
    __ownership: EngineOwnershipLoader | None
    # Serving starts and stops from the lease's callbacks as well as load/shutdown.
    __serving_lock: threading.RLock
    # Memory of agents built with memory=None, bound by load() (see context.py).
    __agent_checkpointer: BaseCheckpointSaver | None = None

    @property
    def configuration(self) -> EngineConfiguration:
        return self.__configuration

    @property
    def modules(self) -> dict[str, BaseModule]:
        try:
            return self.__modules
        except AttributeError:
            error_message = "You are trying to access the engine's modules before the engine is loaded. Modules are accessible when on_initialized is called. If you are in your module constructor or in the on_load method, you should not try to access self.engine yet."
            logger.error(error_message)
            raise RuntimeError(error_message)

    @property
    def services(self) -> IEngine.Services:
        if self.__nats_dependencies is not None:
            return self.__nats_dependencies.module_services
        return self.__services

    @property
    def instance_id(self) -> str:
        """This engine: its lease holder id, and the owner id in the subjects of
        the sessions it serves (transfers, model streams, overflow replies)."""
        return self.__instance_id

    def __init__(self, configuration: str | None = None):
        self.__instance_id = uuid4().hex
        # Load configuration
        self.__configuration = EngineConfiguration.load_configuration(configuration)
        self.__engine_module_loader = EngineModuleLoader(self.__configuration)
        self.__engine_service_loader = EngineServiceLoader(self.__configuration)
        # Set here, not only inside load(), so shutdown() is safe to call
        # even if load() was never (or not yet) invoked.
        self.__nats_dependencies = None
        self.__nats_primary_adapters = []
        self.__nats_runtime_started = False
        self.__job_loader = None
        self.__ownership = None
        self.__serving_lock = threading.RLock()

    def load(self, module_names: list[str] | None = None):
        # Per-module CLI invocations (e.g. ``abi chat <module> <agent>``)
        # pass a narrow ``module_names`` to skip the cost of loading every
        # enabled module. The in-memory ModelRegistry only sees models from
        # modules whose ``on_load`` actually ran, so a narrow load that
        # excludes the AI provider modules leaves the configured defaults
        # (``services.model_registry.default_chat_model`` /
        # ``default_embedding_model``) unregistered — and ``validate_defaults``
        # below would then hard-fail boot. Expand the load set with every
        # enabled module that ships ``ModelDefinition`` subclasses so the
        # registry's configured defaults are always present, regardless of
        # which entry point asked the engine to load.
        if module_names is None:
            module_names = []
        if module_names:
            model_providers = self.__engine_module_loader.get_model_providing_modules()
            extra = [m for m in model_providers if m not in module_names]
            if extra:
                logger.debug(
                    f"Engine.load: expanding module_names with model "
                    f"providers {extra} so the model registry's configured "
                    f"defaults are resolvable."
                )
                module_names = [*module_names, *extra]

        # First, so every span from here on is exported (no-op unless enabled).
        EngineTelemetryLoader.configure(self.__configuration.telemetry)

        module_dependencies = self.__engine_module_loader.get_modules_dependencies(
            module_names
        )

        # Before any backend opens: a second serving engine fails here, and so
        # does a deploy that would hand over with data on this host.
        claim = self.__claim_ownership(module_dependencies)
        # In NATS mode, an engine that neither serves nor stands by is a client.
        client = self.__configuration.nats is not None and claim is None

        logger.debug("Loading engine services")
        if client:
            self.__services = self.__nats_clients()
        else:
            self.__services = self.__engine_service_loader.load_services(
                module_dependencies
            )
        logger.debug("Engine services loaded")

        # Before modules load: their factories build agents with memory=None.
        self.__bind_agent_memory()

        # Config-gated: a no-op unless config.yaml has a top-level `nats:`
        # block. See EngineNATSLoader / EngineConfiguration.NATSConfiguration.
        if self.__configuration.nats is not None and not client:
            # The NATS extra must not be imported by existing non-NATS installs.
            from naas_abi_core.engine.engine_loaders.EngineNATSDependencies import (
                EngineNATSDependencies,
            )

            self.__nats_dependencies = EngineNATSDependencies(self.__configuration.nats)
            dependencies = self.__nats_dependencies.build(self.__services)
            self.__services.wire_services(dependencies)
            self.__nats_runtime_started = True
            if claim is Claim.SERVING:
                self.__serve()

        logger.debug("Loading engine modules")
        self.__modules = self.__engine_module_loader.load_modules(self, module_names)
        logger.debug("Engine modules loaded")

        if self.__services.model_registry_available():
            # Modules registered their models during on_load; now hard-fail if
            # any configured default cannot be resolved against the registry.
            self.__services.model_registry.validate_defaults()

        if client:
            # Schema state belongs to the triple store's owner: the serving engine.
            logger.debug("Client engine: the serving engine loads the ontologies")
        elif self.__services.triple_store_available():
            if not self.__configuration.global_config.skip_ontology_loading:
                logger.debug("Loading engine ontologies")
                EngineOntologyLoader.load_ontologies(
                    self.__services.triple_store,
                    self.__engine_module_loader.ordered_modules,
                )
                logger.debug("Engine ontologies loaded")
            else:
                logger.debug("Skipping ontology loading")
        else:
            logger.debug("No triple store available, skipping ontology loading")

        # Publish the EventService + ModelRegistry as process-wide accessors
        # for cross-cutting consumers (agents, background threads, library
        # code without an engine handle). All other services stay behind
        # EngineProxy and the module dependency-declaration system; see
        # ``engine/context.py`` for the rationale.
        if self.__services.events_available():
            set_default_event_service(self.services.events)
        else:
            set_default_event_service(None)

        if self.__services.model_registry_available():
            set_default_model_registry(self.services.model_registry)
        else:
            set_default_model_registry(None)

        logger.debug("Initializing engine")
        self.on_initialized()
        logger.debug("Engine initialized")

        # Module jobs start last: their handlers may use anything initialized above.
        # A standby or client engine hosts none: the serving engine does.
        if self.__configuration.nats is None or claim is Claim.SERVING:
            self.__start_jobs()
        if self.__ownership is not None and claim is Claim.SERVING:
            self.__ownership.keep(
                on_fenced=self.__stop_serving, on_restored=self.__serve
            )
        elif self.__ownership is not None and claim is Claim.STANDBY:
            self.__ownership.take_over_in_background(
                self.__serve_after_handover,
                on_fenced=self.__stop_serving,
                on_restored=self.__serve,
            )

    def __claim_ownership(
        self, module_dependencies: dict[str, ModuleDependencies]
    ) -> Claim | None:
        """NATS mode: whether this engine serves now, stands by, or (None) is a client.

        Raises ``EngineAlreadyServing`` when another engine serves and this one
        may not take over (docs/adr/20261006_single-serving-engine.md).
        """
        if self.__configuration.nats is None:
            return None
        from naas_abi_core.engine.engine_loaders.EngineOwnershipLoader import (
            EngineOwnershipLoader,
        )

        ownership = EngineOwnershipLoader(
            self.__configuration.nats,
            local_backends=self.__engine_service_loader.local_backends(
                module_dependencies
            ),
            instance_id=self.__instance_id,
        )
        try:
            claim = ownership.claim()
        except BaseException:
            ownership.close()
            raise
        self.__ownership = ownership
        return claim

    def __nats_clients(self) -> IEngine.Services:
        """A client engine's services: the serving engine's, through NATS.

        No owner, no local adapter, no subscription: nothing opens a backend on
        this host. The model registry stays in this process, in memory, for the
        modules to register their models with.
        """
        from naas_abi_core.engine.engine_loaders.EngineNATSDependencies import (
            EngineNATSDependencies,
        )

        assert self.__configuration.nats is not None
        services = self.__configuration.services
        self.__nats_dependencies = EngineNATSDependencies(self.__configuration.nats)
        self.__nats_runtime_started = True
        return self.__nats_dependencies.build_clients(
            services.model_registry.load(),
            cache_tiers=[entry.tier for entry in services.cache.adapters],
            emit_message_events=services.bus.emit_message_events,
        )

    def __serve(self) -> None:
        """Expose the kernel services over NATS: this engine holds the lease."""
        from naas_abi_core.engine.engine_loaders.EngineNATSLoader import (
            EngineNATSLoader,
        )
        from naas_abi_core.engine.nats_sessions import owned_by

        with self.__serving_lock:
            if self.__nats_primary_adapters or not self.__nats_runtime_started:
                return
            nats_loader = EngineNATSLoader(self.__configuration)
            # The sessions they serve carry this engine's id, as its lease does.
            with owned_by(self.__instance_id):
                primaries = nats_loader.expose_services(self.__services)
                primaries += nats_loader.expose_overflow(primaries)
            self.__nats_primary_adapters = primaries

    def __stop_serving(self, drain_seconds: float = 0) -> None:
        """Stop every started primary adapter.

        The shared (queue-grouped) subscriptions end first, so new requests go to
        the next engine. The sessions this engine owns (transfers, model streams,
        overflow replies) go on for up to ``drain_seconds``, then close. Without
        time to drain (fencing), everything stops at once.
        """
        from naas_abi_core.engine import nats_runtime
        from naas_abi_core.engine.nats_sessions import SessionHost, wait_for_sessions

        with self.__serving_lock:
            primaries, self.__nats_primary_adapters = self.__nats_primary_adapters, []
        hosts = [
            primary
            for primary in primaries
            if drain_seconds > 0 and isinstance(primary, SessionHost)
        ]
        for primary in primaries:
            # __nats_primary_adapters is list[object] (whichever *PrimaryAdapterNATS
            # classes EngineNATSLoader started, deliberately untyped there); every
            # one has an async stop(), just not one mypy can see through `object`.
            stopping: Any = primary
            self.__stop_quietly(
                primary,
                stopping.stop_accepting() if primary in hosts else stopping.stop(),
            )
        if hosts:
            try:
                finished = nats_runtime.run_coro(
                    wait_for_sessions(hosts, drain_seconds), timeout=drain_seconds + 5
                )
            except Exception as exc:  # noqa: BLE001 - close them below regardless
                logger.warning(f"Engine.shutdown: waiting for sessions failed: {exc}")
                finished = False
            if not finished:
                logger.warning(
                    f"Engine.shutdown: closing sessions still open after "
                    f"{drain_seconds:g}s"
                )
        for host in hosts:
            self.__stop_quietly(host, host.stop())

    @staticmethod
    def __stop_quietly(primary: object, stopping: Any) -> None:
        from naas_abi_core.engine import nats_runtime

        try:
            nats_runtime.run_coro(stopping)
        except Exception as exc:  # noqa: BLE001
            # Best-effort: a slow/unresponsive primary must never block
            # the rest of shutdown or crash the process on the way out.
            logger.warning(
                f"Engine.shutdown: error stopping a NATS primary adapter "
                f"({type(primary).__name__}): {exc}"
            )

    def __start_jobs(self) -> None:
        self.__job_loader = EngineJobLoader(self.__configuration.nats)
        self.__job_loader.start(
            self.job_owners(), document_available=self.__services.document_available()
        )

    def __serve_after_handover(self) -> None:
        """A standby took the lease: serve, then host the jobs."""
        self.__serve()
        self.__start_jobs()

    def __bind_agent_memory(self) -> None:
        """Agents built with memory=None checkpoint into the document service.

        The engine's own root (the local adapter when this process owns the
        service), never a NATS client view: checkpoints are full snapshots and
        must not be bounded by the broker's payload limit. A client engine owns
        no service: its root is the serving engine's, over NATS (RPC overflow
        carries the large snapshots). Without the service, agents keep the
        standalone fallback (POSTGRES_URL, else in memory).
        """
        self.__agent_checkpointer = None
        if self.__services.document_available():
            try:
                from naas_abi_core.services.agent.DocumentCheckpointSaver import (
                    DocumentCheckpointSaver,
                )
            except ModuleNotFoundError as exc:
                if (exc.name or "").split(".")[0] != "naas_abi_sdk":
                    raise
                logger.warning(
                    "Agent memory is not in the document service: it needs "
                    "naas-abi-sdk (naas-abi-core[nats])"
                )
            else:
                self.__agent_checkpointer = DocumentCheckpointSaver.for_engine(
                    self.__services.document
                )
        set_default_agent_checkpointer(self.__agent_checkpointer)

    @property
    def hosts_jobs(self) -> bool:
        """Whether this engine hosts jobs (NATS mode with ``nats.jobs.enabled``)."""
        nats = self.__configuration.nats
        return nats is not None and nats.jobs.enabled

    def job_owners(self) -> dict[str, object]:
        """Modules plus kernel job owners (NATS mode only), keyed by owner id.

        Dataset maintenance works on the dataset service's own data, so it gets
        this engine's service, like the endpoints do: no NATS hop, no RPC
        deadline. A job one domain runs against another (the event archive
        writing datasets) is a dependency and gets the facades
        (``NATSConfiguration``)."""
        owners: dict[str, object] = dict(self.__modules)
        if self.__configuration.nats is None:
            return owners
        if self.__services.dataset_available():
            from naas_abi_core.services.dataset.DatasetMaintenanceJobs import (
                DATASET_JOBS_OWNER,
                DatasetMaintenanceJobs,
            )

            owners[DATASET_JOBS_OWNER] = DatasetMaintenanceJobs(self.__services.dataset)
        if self.__agent_checkpointer is not None:
            # Set only to the Document Service saver (__bind_agent_memory).
            from naas_abi_core.services.agent.AgentMemoryJobs import (
                AGENT_MEMORY_JOBS_OWNER,
                AgentMemoryJobs,
            )

            owners[AGENT_MEMORY_JOBS_OWNER] = AgentMemoryJobs.for_engine(
                self.__agent_checkpointer,  # type: ignore[arg-type]
                self.__services,
            )
        # A service's adapter may host its own maintenance jobs (the PostgreSQL
        # event log archives itself into the Dataset Service).
        for service in self.__services.all:
            adapter = getattr(service, "adapter", None)
            offer = getattr(type(adapter), "job_owners", None)
            if offer is not None:
                owners.update(offer(adapter, self.services))
        return owners

    def on_initialized(self):
        for module in self.__modules.values():
            module.on_initialized()

    def shutdown(self) -> None:
        """Gracefully tear down everything ``load()`` started over NATS.

        A no-op without importing NATS if this engine never started its
        NATS runtime. Safe to call more than once, including before load().
        Stops every started primary adapter first (draining its
        subscriptions with the connection still up) before closing the
        shared connection those adapters were registered on, not the other
        order.

        Callers: ``apps/api/api.py``'s FastAPI lifespan shutdown phase,
        ``abi dev down``, and anywhere else that owns an ``Engine``'s
        lifecycle end to end. An ungracefully-killed process (e.g. SIGKILL,
        or a crash) still just drops the NATS connection, which the server
        reaps naturally -- this only makes the *clean* shutdown path
        actually clean, it's not required for correctness.
        """
        # Jobs first: running ones still save their run records over NATS.
        job_loader, self.__job_loader = self.__job_loader, None
        if job_loader is not None:
            job_loader.stop()
        # Agents built from now on must not reach storage this engine releases.
        memory, self.__agent_checkpointer = self.__agent_checkpointer, None
        if memory is not None and get_default_agent_checkpointer() is memory:
            set_default_agent_checkpointer(None)
        # Free the lease before draining: a standby takes over while this engine
        # finishes what it already received (shared backends make the overlap safe).
        ownership, self.__ownership = self.__ownership, None
        if ownership is not None:
            ownership.release()
        if not self.__nats_runtime_started:
            if ownership is not None:
                ownership.close()
            return
        self.__nats_runtime_started = False
        set_default_event_service(None)
        from naas_abi_core.engine import nats_runtime

        # Sessions this engine owns finish (or reach the deadline) after the release.
        self.__stop_serving(
            ownership.settings.drain_seconds if ownership is not None else 0
        )
        if ownership is not None:
            ownership.close()
        if self.__nats_dependencies is not None:
            self.__nats_dependencies.close()
            self.__nats_dependencies = None
        nats_runtime.close()


if __name__ == "__main__":
    engine = Engine()
    engine.load(module_names=["chatgpt"])
    print("Engine loaded successfully")
