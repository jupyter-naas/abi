"""What workflows and pipelines share: parameters, construction and LangChain tools.

Needs pydantic (``pip install 'naas-abi-sdk[workflows]'``). LangChain is imported
only by ``as_tools`` (extras ``[agents]`` or ``[agent]``).
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import typing
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from naas_abi_sdk.components import component_slug, configuration_class

try:
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - exercised without the extra
    raise ImportError(
        "naas_abi_sdk workflows and pipelines need pydantic: "
        "pip install 'naas-abi-sdk[workflows]'"
    ) from exc

if TYPE_CHECKING:
    from langchain_core.tools import StructuredTool


@dataclass
class ProcessConfiguration:
    pass


class ProcessParameters(BaseModel):
    pass


def serialize_result(result: Any) -> Any:
    """A JSON-serializable value: a model is dumped, an rdflib graph is turtle."""
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if callable(getattr(result, "serialize", None)) and hasattr(result, "triples"):
        return {"format": "turtle", "data": result.serialize(format="turtle")}
    return result


def _parameters_model(annotation: Any, base: type[BaseModel]) -> type[BaseModel] | None:
    if (
        isinstance(annotation, type)
        and issubclass(annotation, BaseModel)
        and annotation is not base
    ):
        return annotation
    return None


class Process:
    """A callable unit of a module: ``await run(parameters)``.

    Base of ``Workflow`` and ``Pipeline``. ``run`` is async and takes a pydantic
    parameters model.
    """

    kind: ClassVar[str] = "process"
    _configuration_base: ClassVar[type] = ProcessConfiguration
    _parameters_base: ClassVar[type[BaseModel]] = ProcessParameters

    def __init__(self, configuration: Any):
        self._configuration = configuration

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        run = cls.__dict__.get("run")
        if run is not None and not inspect.iscoroutinefunction(run):
            raise TypeError(
                f"{cls.__name__}.run must be `async def`: a remote module runs "
                f"its {cls.kind}s on its event loop"
            )

    async def run(self, parameters: Any) -> Any:
        raise NotImplementedError(f"{type(self).__name__}.run is not implemented")

    @classmethod
    def slug(cls) -> str:
        """The component's name: its tool name, and its NATS subject token."""
        return component_slug(cls.__name__)

    @classmethod
    def parameters_type(cls) -> type[BaseModel]:
        """The model ``run`` takes: its annotation, else the generic argument
        the class was given, else ``<Name>Parameters`` beside the class."""
        base = cls._parameters_base
        try:
            hints = typing.get_type_hints(cls.run)
        except Exception:  # noqa: BLE001 - an unresolved forward reference
            hints = {}
        names = [n for n in inspect.signature(cls.run).parameters if n != "self"]
        if names and (found := _parameters_model(hints.get(names[0]), base)):
            return found
        for klass in cls.__mro__:
            for generic in getattr(klass, "__orig_bases__", ()):
                for argument in typing.get_args(generic):
                    if found := _parameters_model(argument, base):
                        return found
        module = sys.modules.get(cls.__module__)
        found = _parameters_model(
            getattr(module, f"{cls.__name__}Parameters", None), base
        )
        return found or base

    def as_tools(self) -> list[StructuredTool]:
        """One LangChain tool: named after the class slug, described by its
        docstring, taking the parameters model, running ``run`` on the module's
        event loop. Call it from the module's loop (``on_initialized``)."""
        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:
            raise ImportError(
                f"{type(self).__name__}.as_tools needs LangChain: "
                "pip install 'naas-abi-sdk[agents]'"
            ) from exc

        parameters_type = self.parameters_type()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        async def call(**arguments: Any) -> Any:
            return serialize_result(await self.run(parameters_type(**arguments)))

        def call_from_thread(**arguments: Any) -> Any:
            if loop is None or not loop.is_running():
                raise RuntimeError(
                    "Create module tools inside the running module; use ainvoke "
                    "for async callers"
                )
            try:
                current = asyncio.get_running_loop()
            except RuntimeError:
                current = None
            if current is loop:
                raise RuntimeError("Use tool.ainvoke on the module event loop")
            return asyncio.run_coroutine_threadsafe(call(**arguments), loop).result()

        # Not inherited: a class without a docstring is not described by its base's.
        doc = type(self).__doc__
        return [
            StructuredTool.from_function(
                func=call_from_thread,
                coroutine=call,
                name=self.slug(),
                description=inspect.cleandoc(doc) if doc else self.slug(),
                args_schema=parameters_type,
            )
        ]

    @classmethod
    async def build(cls, module: Any) -> tuple[Any, str | None]:
        """An instance for ``module``, or None and why it cannot be built.

        ``New(module)`` (sync or async) when the class defines one, else the
        class with an empty ``<Name>Configuration``. An error raised inside
        either propagates.
        """
        new = getattr(cls, "New", None)
        if callable(new):
            instance = new(module)
            if isinstance(instance, Awaitable):
                instance = await instance
            if instance is None:
                return None, f"{cls.__name__}.New(module) returned None"
            return instance, None
        config_cls = configuration_class(cls)
        if config_cls is None:
            # The base constructor takes the base configuration, which is empty.
            if cls.__init__ is not Process.__init__:
                return None, f"it has no {cls.__name__}Configuration to build it with"
            config_cls = cls._configuration_base
        try:
            configuration = config_cls()
        except TypeError as exc:
            return None, f"{config_cls.__name__}() needs arguments ({exc})"
        return cls(configuration), None
