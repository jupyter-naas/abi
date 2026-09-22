
from naas_abi_core import logger
from naas_abi_core.engine.context import (
    set_default_event_service,
    set_default_model_registry,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineModuleLoader import EngineModuleLoader
from naas_abi_core.engine.engine_loaders.EngineOntologyLoader import (
    EngineOntologyLoader,
)
from naas_abi_core.engine.engine_loaders.EngineServiceLoader import EngineServiceLoader
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import BaseModule


class Engine(IEngine):
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
        return self.__services

    def __init__(self, configuration: str | None = None):
        # Load configuration
        self.__configuration = EngineConfiguration.load_configuration(configuration)
        self.__engine_module_loader = EngineModuleLoader(self.__configuration)
        self.__engine_service_loader = EngineServiceLoader(self.__configuration)
        # Set here, not only inside load(), so shutdown() is safe to call
        # even if load() was never (or not yet) invoked.
        self.__nats_primary_adapters = []
        self.__nats_runtime_started = False

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
            model_providers = (
                self.__engine_module_loader.get_model_providing_modules()
            )
            extra = [m for m in model_providers if m not in module_names]
            if extra:
                logger.debug(
                    f"Engine.load: expanding module_names with model "
                    f"providers {extra} so the model registry's configured "
                    f"defaults are resolvable."
                )
                module_names = [*module_names, *extra]

        module_dependencies = self.__engine_module_loader.get_modules_dependencies(
            module_names
        )

        logger.debug("Loading engine services")
        self.__services = self.__engine_service_loader.load_services(
            module_dependencies
        )
        logger.debug("Engine services loaded")

        # Config-gated: a no-op unless config.yaml has a top-level `nats:`
        # block. See EngineNATSLoader / EngineConfiguration.NATSConfiguration.
        if self.__configuration.nats is not None:
            # The NATS extra must not be imported by existing non-NATS installs.
            from naas_abi_core.engine.engine_loaders.EngineNATSLoader import (
                EngineNATSLoader,
            )

            self.__nats_runtime_started = True
            self.__nats_primary_adapters = EngineNATSLoader(
                self.__configuration
            ).expose_services(self.__services)

        logger.debug("Loading engine modules")
        self.__modules = self.__engine_module_loader.load_modules(self, module_names)
        logger.debug("Engine modules loaded")

        if self.__services.model_registry_available():
            # Modules registered their models during on_load; now hard-fail if
            # any configured default cannot be resolved against the registry.
            self.__services.model_registry.validate_defaults()

        if self.__services.triple_store_available():
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
            set_default_event_service(self.__services.events)
        else:
            set_default_event_service(None)

        if self.__services.model_registry_available():
            set_default_model_registry(self.__services.model_registry)
        else:
            set_default_model_registry(None)

        logger.debug("Initializing engine")
        self.on_initialized()
        logger.debug("Engine initialized")

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
        if not self.__nats_runtime_started:
            return
        self.__nats_runtime_started = False
        from naas_abi_core.engine import nats_runtime

        primaries, self.__nats_primary_adapters = self.__nats_primary_adapters, []
        for primary in primaries:
            try:
                # __nats_primary_adapters is list[object] (it holds whichever
                # of the 11 *PrimaryAdapterNATS classes EngineNATSLoader
                # started, deliberately untyped there -- see its own return
                # type) -- every one of them has an async stop(), just not
                # one mypy can see through `object`.
                nats_runtime.run_coro(primary.stop())  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                # Best-effort: a slow/unresponsive primary must never block
                # the rest of shutdown or crash the process on the way out.
                logger.warning(
                    f"Engine.shutdown: error stopping a NATS primary adapter "
                    f"({type(primary).__name__}): {exc}"
                )
        nats_runtime.close()


if __name__ == "__main__":
    engine = Engine()
    engine.load(module_names=["chatgpt"])
    print("Engine loaded successfully")
