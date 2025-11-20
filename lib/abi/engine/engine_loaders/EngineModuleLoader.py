import importlib
from typing import Dict, List

import pydantic_core
from abi import logger
from abi.engine.engine_configuration.EngineConfiguration import EngineConfiguration
from abi.engine.EngineProxy import EngineProxy
from abi.engine.IEngine import IEngine
from abi.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies


class EngineModuleLoader:
    __configuration: EngineConfiguration

    __module_load_order: List[str] = []

    __modules: Dict[str, BaseModule] = {}

    __module_dependencies: Dict[str, ModuleDependencies] | None = None

    def __init__(self, configuration: EngineConfiguration):
        self.__configuration = configuration

    @property
    def modules(self) -> Dict[str, BaseModule]:
        return self.__modules

    @property
    def module_load_order(self) -> List[str]:
        return self.__module_load_order

    @property
    def ordered_modules(self) -> List[BaseModule]:
        return [self.__modules[module_name] for module_name in self.__module_load_order]

    def __topological_sort(self, dependencies: Dict[str, List[str]]) -> List[str]:
        """
        Perform topological sort on modules based on dependencies.
        Returns a list of module names in load order.
        Raises ValueError if circular dependency is detected.
        """
        # Build adjacency list and in-degree count
        in_degree = {node: 0 for node in dependencies}
        adj_list: Dict[str, List[str]] = {node: [] for node in dependencies}

        for node, deps in dependencies.items():
            for dep in deps:
                if dep not in dependencies:
                    logger.error(
                        f"Module '{node}' depends on '{dep}' which is not enabled. "
                        "Aborting."
                    )
                    raise ValueError(
                        f"Module '{node}' depends on '{dep}' which is not enabled. "
                        "Aborting."
                    )
                    continue
                adj_list[dep].append(node)
                in_degree[node] += 1

        # Kahn's algorithm
        queue = [node for node in in_degree if in_degree[node] == 0]
        sorted_list = []

        while queue:
            # Sort queue for deterministic order when multiple nodes have in-degree 0
            queue.sort()
            node = queue.pop(0)
            sorted_list.append(node)

            for neighbor in adj_list[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for circular dependencies
        if len(sorted_list) != len(dependencies):
            unprocessed = [node for node in dependencies if node not in sorted_list]
            raise ValueError(
                f"Circular dependency detected among modules: {unprocessed}. "
                "Cannot determine load order."
            )

        logger.debug(f"Module load order: {sorted_list}")
        return sorted_list

    def module_dependencies_recursive(
        self, module_name: str, module_dependencies: Dict[str, ModuleDependencies]
    ) -> List[str]:
        required_modules: List[str] = [module_name]
        # This is not protected against circular dependencies.
        # This is why it must be ran after the topological sort.
        for dependency in module_dependencies[module_name].modules:
            required_modules.append(dependency)
            required_modules.extend(
                self.module_dependencies_recursive(dependency, module_dependencies)
            )
        return list(set(required_modules))

    def modules_dependencies_recursive(
        self,
        module_names: List[str],
        module_dependencies: Dict[str, ModuleDependencies],
    ) -> List[str]:
        dependencies: List[str] = []
        for module_name in module_names:
            dependencies.extend(
                self.module_dependencies_recursive(module_name, module_dependencies)
            )
        return list(set(dependencies))

    def get_module_dependencies(
        self, module_name: str, scanned_modules: List[str] = []
    ) -> Dict[str, ModuleDependencies]:
        dependencies: Dict[str, ModuleDependencies] = {}
        logger.debug(f"Getting module dependencies for {module_name}")
        if module_name in scanned_modules:
            raise ValueError(
                f"Circular dependency detected: {scanned_modules + [module_name]}"
            )

        module_config = next(
            (m for m in self.__configuration.modules if m.module == module_name),
            None,
        )

        if module_config is None:
            raise ValueError(f"Module {module_name} not found in configuration")

        module = importlib.import_module(module_config.module)
        assert hasattr(module, "ABIModule"), (
            f"Module {module_config.module} does not have a ABIModule class"
        )
        assert hasattr(module.ABIModule, "get_dependencies"), (
            f"Module {module_config.module} does not have a get_dependencies method"
        )
        dependencies[module_name] = module.ABIModule.get_dependencies()
        assert isinstance(dependencies[module_name], ModuleDependencies), (
            f"Module {module_config.module} get_dependencies method must return a ModuleDependencies object"
        )

        # We recursively get the dependencies of the module.
        for module_dependency in dependencies[module_name].modules:
            submodule_dependencies = self.get_module_dependencies(
                module_dependency, scanned_modules + [module_name]
            )
            dependencies.update(submodule_dependencies)

            # dependencies.modules.extend(submodule_dependencies.modules)
            # dependencies.services.extend(submodule_dependencies.services)

        # # Make sure we have unique modules and services.
        # dependencies.modules = list(set(dependencies.modules))
        # dependencies.services = list(set(dependencies.services))

        logger.debug(f"Module dependencies for {module_name}: {dependencies}")

        return dependencies

    def get_modules_dependencies(
        self, module_names: List[str] = []
    ) -> Dict[str, ModuleDependencies]:
        module_dependencies: Dict[str, ModuleDependencies] = {}
        for module_config in self.__configuration.modules:
            # We check if the module is required by the configuration.
            if (
                len(module_names) > 0
                and module_config.module in module_names
                and not module_config.enabled
            ):
                raise ValueError(
                    f"Module {module_config.module} is not enabled but is required by the configuration"
                )

            if len(module_names) > 0 and module_config.module not in module_names:
                continue

            if module_config.enabled:
                module_dependencies.update(
                    self.get_module_dependencies(module_config.module)
                )
        self.__module_dependencies = module_dependencies
        return self.__module_dependencies

    def load_modules(
        self,
        engine: IEngine,
        module_names: List[str] = [],
    ) -> Dict[str, BaseModule]:
        self.__modules: Dict[str, BaseModule] = {}

        if self.__module_dependencies is None:
            # Call this to hydrate the __module_dependencies attribute.
            self.get_modules_dependencies(module_names)

        logger.debug(f"Module dependencies: {self.__module_dependencies}")

        module_load_order = self.__topological_sort(
            {
                module_name: dependencies.modules
                for module_name, dependencies in self.__module_dependencies.items()
            }
        )

        self.__module_load_order = module_load_order

        # We load the modules in the order of the topological sort
        for module_name in self.__module_load_order:
            module_config = next(
                (m for m in self.__configuration.modules if m.module == module_name),
                None,
            )
            if module_config is None:
                raise ValueError(f"Module {module_name} not found in configuration")

            if module_config.enabled:
                if module_config.module:
                    module = importlib.import_module(module_config.module)
                    if not hasattr(module, "ABIModule"):
                        raise ValueError(
                            f"Module {module_config.module} does not have a Module class"
                        )

                    if not hasattr(module.ABIModule, "Configuration"):
                        raise ValueError(
                            f"Module {module_config.module} does not have a Configuration class"
                        )

                    assert type(module.ABIModule.Configuration) is type(
                        ModuleConfiguration
                    ), (
                        f"Module {module_config.module} Configuration must be a subclass of ModuleConfiguration"
                    )

                    try:
                        cfg = module.ABIModule.Configuration(
                            global_config=self.__configuration.global_config,
                            **module_config.config,
                        )
                    except pydantic_core._pydantic_core.ValidationError as e:
                        raise ValueError(
                            f"Error loading configuration for module {module_config.module}: {e}"
                        ) from e

                    # This effectively creates a new instance of the module.
                    # It will call the constructor of the ABIModule class inside the module.
                    module = module.ABIModule(
                        EngineProxy(
                            engine, module_name, self.__module_dependencies[module_name]
                        ),
                        cfg,
                    )
                    assert isinstance(module, BaseModule), (
                        f"Module {module_config.module} is not a subclass of BaseModule"
                    )
                    self.__modules[module_name] = module
                    module.on_load()
                else:
                    raise ValueError("module must be provided for a module")

        return self.__modules
