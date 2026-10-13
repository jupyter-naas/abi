import importlib
from typing import Any, TypeVar

from pydantic import BaseModel

ConfigModel = TypeVar("ConfigModel", bound=BaseModel)


def config_model(model: type[ConfigModel], config: Any) -> ConfigModel:
    """An adapter's ``config`` as ``model``: configs are typed models or plain dicts."""
    if isinstance(config, model):
        return config
    if isinstance(config, BaseModel):
        config = config.model_dump()
    return model.model_validate(config or {})


class GenericLoader(BaseModel):
    """
    Generic loader for dynamically importing and instantiating Python callables.

    This class enables dynamic loading of Python classes or functions by specifying
    the module path and callable name. The callable is invoked with the provided
    configuration dictionary unpacked as keyword arguments.

    Usage:
        1. Use importlib.import_module(python_module) to import the target module
        2. Use getattr(module, module_callable) to retrieve the callable
        3. Invoke the callable with the custom_config as **custom_config

    Example:
        loader = GenericLoader(
            python_module="my.package.module",
            module_callable="MyClass",
            custom_config={"param1": "value1", "param2": 42}
        )
        # This would effectively do:
        # import importlib
        # module = importlib.import_module("my.package.module")
        # callable_obj = getattr(module, "MyClass")
        # instance = callable_obj(param1="value1", param2=42)

    Attributes:
        python_module: The fully qualified Python module path (e.g., "package.subpackage.module")
        module_callable: The name of the callable (class or function) to retrieve from the module
        custom_config: Dictionary of configuration parameters to pass as keyword arguments to the callable
    """

    python_module: str | None = None
    module_callable: str | None = None
    custom_config: dict[str, Any] | None = None
    # Custom adapters only: true when the adapter keeps its data in a backend every
    # engine reaches (a database or store server), so deploys may hand over without
    # downtime (docs/adr/20261006_single-serving-engine.md).
    shared_storage: bool = False

    def local_storage(self) -> str | None:
        """Why this adapter's data stays on this host, or None when every engine
        reaches it. Each adapter configuration declares its own."""
        raise NotImplementedError(
            f"{type(self).__name__} does not declare where its data lives"
        )

    def custom_local_storage(self) -> str | None:
        if self.shared_storage:
            return None
        return "a custom adapter that does not declare shared_storage: true"

    def load(self) -> Any:
        assert self.python_module is not None, "python_module is required"
        assert self.module_callable is not None, "module_callable is required"
        assert self.custom_config is not None, "custom_config is required"

        module = importlib.import_module(self.python_module)
        callable_obj = getattr(module, self.module_callable)
        return callable_obj(**self.custom_config)
