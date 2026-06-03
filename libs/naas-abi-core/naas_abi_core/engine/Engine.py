from typing import Dict, List

from naas_abi_core import logger
from naas_abi_core.engine.context import (
    set_default_event_service,
    set_default_model_registry,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration import \
    EngineConfiguration
from naas_abi_core.engine.engine_loaders.EngineModuleLoader import \
    EngineModuleLoader
from naas_abi_core.engine.engine_loaders.EngineOntologyLoader import \
    EngineOntologyLoader
from naas_abi_core.engine.engine_loaders.EngineServiceLoader import \
    EngineServiceLoader
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import BaseModule


class Engine(IEngine):
    __configuration: EngineConfiguration
    __engine_module_loader: EngineModuleLoader
    __engine_service_loader: EngineServiceLoader

    __modules: Dict[
        str, BaseModule
    ]  # Must not set a default value to prevent modules to try to access modules inside constructors.

    __services: IEngine.Services

    @property
    def configuration(self) -> EngineConfiguration:
        return self.__configuration

    @property
    def modules(self) -> Dict[str, BaseModule]:
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

    def load(self, module_names: List[str] = []):
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


if __name__ == "__main__":
    engine = Engine()
    engine.load(module_names=["chatgpt"])
    print("Engine loaded successfully")
