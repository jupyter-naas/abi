import importlib
from typing import Any, Dict

from pydantic import BaseModel


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
    custom_config: Dict[str, Any] | None = None

    def load(self) -> Any:
        assert self.python_module is not None, "python_module is required"
        assert self.module_callable is not None, "module_callable is required"
        assert self.custom_config is not None, "custom_config is required"

        module = importlib.import_module(self.python_module)
        callable_obj = getattr(module, self.module_callable)
        return callable_obj(**self.custom_config)
