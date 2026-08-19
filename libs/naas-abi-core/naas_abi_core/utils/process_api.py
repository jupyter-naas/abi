"""Mount module workflows, pipelines, and tools on FastAPI routers.

The kernel calls ``as_api`` first. If that adds no routes, a default
``POST /{slug}`` is registered only when ``run(parameters)`` is a real
override with a Pydantic parameters model. Stubs without a live ``run``
stay unpublished. LangChain-only tools are not given a REST path.
"""

from __future__ import annotations

import ast
import inspect
import re
import sys
import textwrap
from collections.abc import Iterable
from enum import Enum
from typing import Any, TypeVar, get_type_hints

from fastapi import APIRouter
from pydantic import BaseModel

from naas_abi_core.utils.Logger import logger

T = TypeVar("T")

_CAMEL_ACRONYM = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")


def process_route_slug(instance: Any) -> str:
    name = instance.__class__.__name__
    stepped = _CAMEL_ACRONYM.sub(r"\1_\2", name)
    stepped = _CAMEL_BOUNDARY.sub(r"\1_\2", stepped)
    return stepped.replace(" ", "_").replace("-", "_").lower()


def _configuration_class(process_cls: type) -> type | None:
    module = sys.modules.get(process_cls.__module__)
    expected = f"{process_cls.__name__}Configuration"
    if module is not None:
        candidate = getattr(module, expected, None)
        if isinstance(candidate, type):
            return candidate
    nested = getattr(process_cls, "Configuration", None)
    if isinstance(nested, type):
        return nested
    return None


def instantiate_process(process_cls: type[T]) -> T | None:
    """Build a process with ``New()`` or an empty Configuration.

    Returns None when the constructor needs arguments we do not have. The
    kernel logs that and skips the process rather than crashing boot.
    """
    new = getattr(process_cls, "New", None)
    if callable(new):
        try:
            instance = new()
            if instance is not None:
                return instance
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "instantiate_process: %s.New() failed: %s. Trying Configuration.",
                process_cls.__name__,
                exc,
            )

    config_cls = _configuration_class(process_cls)
    if config_cls is not None:
        try:
            return process_cls(config_cls())  # type: ignore[call-arg]
        except TypeError as exc:
            logger.debug(
                "instantiate_process: %s needs constructor config we cannot "
                "supply (%s). Skipping.",
                process_cls.__name__,
                exc,
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "instantiate_process: %s(%s()) failed: %s. Skipping.",
                process_cls.__name__,
                config_cls.__name__,
                exc,
            )
            return None

    try:
        return process_cls()  # type: ignore[call-arg]
    except TypeError as exc:
        logger.debug(
            "instantiate_process: %s() failed: %s. Skipping.",
            process_cls.__name__,
            exc,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "instantiate_process: %s() failed: %s. Skipping.",
            process_cls.__name__,
            exc,
        )
        return None


def instantiate_all(classes: list[type[T]]) -> list[T]:
    instances: list[T] = []
    for process_cls in classes:
        instance = instantiate_process(process_cls)
        if instance is not None:
            instances.append(instance)
    return instances


def _run_body_is_trivial(run: Any) -> bool:
    """True when run() is only ``pass`` or ``raise NotImplementedError``.

    Scaffold overrides must not become HTTP. If the source cannot be read,
    treat the method as live so a real implementation is not dropped.
    """
    try:
        source = inspect.getsource(run)
    except (OSError, TypeError):
        return False
    try:
        tree = ast.parse(textwrap.dedent(source))
    except (SyntaxError, IndentationError):
        return False
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = [
            stmt
            for stmt in node.body
            if not (
                isinstance(stmt, ast.Expr)
                and isinstance(getattr(stmt, "value", None), ast.Constant)
                and isinstance(stmt.value.value, str)
            )
        ]
        if not body:
            return True
        if len(body) == 1 and isinstance(body[0], ast.Pass):
            return True
        if len(body) == 1 and isinstance(body[0], ast.Raise):
            exc = body[0].exc
            if isinstance(exc, ast.Call) and getattr(exc.func, "id", None) == (
                "NotImplementedError"
            ):
                return True
            if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                return True
        return False
    return False


def _run_is_live(instance: Any) -> bool:
    run = getattr(type(instance), "run", None)
    if run is None or not callable(run):
        return False

    from naas_abi_core.pipeline.pipeline import Pipeline
    from naas_abi_core.workflow.workflow import Workflow

    if isinstance(instance, Workflow) and type(instance).run is Workflow.run:
        return False
    if isinstance(instance, Pipeline) and type(instance).run is Pipeline.run:
        return False
    return not _run_body_is_trivial(run)


def _run_parameters_type(instance: Any) -> type[BaseModel] | None:
    run = getattr(type(instance), "run", None)
    if run is None:
        return None

    try:
        hints = get_type_hints(run)
    except Exception:  # noqa: BLE001
        hints = {}

    for key in ("parameters", "params"):
        annotated = hints.get(key)
        if isinstance(annotated, type) and issubclass(annotated, BaseModel):
            return annotated

    try:
        signature = inspect.signature(run)
    except (TypeError, ValueError):
        signature = None

    if signature is not None:
        for param_name, param in signature.parameters.items():
            if param_name == "self":
                continue
            annotation = hints.get(param_name, param.annotation)
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                return annotation

    expected = f"{instance.__class__.__name__}Parameters"
    module = sys.modules.get(instance.__class__.__module__)
    if module is not None:
        candidate = getattr(module, expected, None)
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return candidate
    return None


def serialize_process_result(result: Any) -> Any:
    try:
        from rdflib import Graph
    except ImportError:  # pragma: no cover
        Graph = None  # type: ignore[assignment, misc]

    if Graph is not None and isinstance(result, Graph):
        return {"format": "turtle", "data": result.serialize(format="turtle")}
    if isinstance(result, BaseModel):
        return result.model_dump()
    if isinstance(result, (bytes, bytearray)):
        return {"data": result.decode("utf-8", errors="replace")}
    return result


def register_run_route(
    instance: Any,
    router: APIRouter,
    route_name: str = "",
    name: str = "",
    description: str = "",
    tags: list[str | Enum] | None = None,
) -> bool:
    """Register ``POST /{slug}`` that calls ``run()``. Returns True if mounted."""
    if not _run_is_live(instance):
        return False
    parameters_type = _run_parameters_type(instance)
    if parameters_type is None:
        logger.debug(
            "No Pydantic parameters type for %s.run. Not inventing a body.",
            instance.__class__.__name__,
        )
        return False

    slug = route_name or process_route_slug(instance)
    display = name or instance.__class__.__name__
    doc = (instance.__class__.__doc__ or "").strip()
    desc = description or doc or display
    prefix = (getattr(router, "prefix", None) or "").strip("/")
    operation_id = f"{prefix}_{slug}" if prefix else slug

    def run_process(parameters):
        return serialize_process_result(instance.run(parameters))

    # ``from __future__ import annotations`` would leave a ForwardRef here.
    # FastAPI needs the real model class to build the JSON body.
    run_process.__annotations__ = {
        "parameters": parameters_type,
        "return": object,
    }
    router.add_api_route(
        f"/{slug}",
        run_process,
        methods=["POST"],
        name=display,
        description=desc,
        tags=tags,
        operation_id=operation_id,
    )

    return True


def mount_expose_process(
    instance: Any,
    router: APIRouter,
    route_name: str = "",
    name: str = "",
    description: str = "",
    tags: list[str | Enum] | None = None,
) -> bool:
    """Call ``as_api``. If it added no routes, try the default ``run()`` POST."""
    before = len(router.routes)
    as_api = getattr(instance, "as_api", None)
    if callable(as_api):
        try:
            as_api(
                router,
                route_name=route_name,
                name=name,
                description=description,
                tags=tags,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "as_api failed for %s: %s",
                instance.__class__.__name__,
                exc,
            )
    if len(router.routes) > before:
        return True
    return register_run_route(
        instance,
        router,
        route_name=route_name,
        name=name,
        description=description,
        tags=tags,
    )


def _sort_key(obj: Any) -> str:
    name = getattr(obj, "name", None)
    if isinstance(name, str) and name:
        return name.lower()
    return obj.__class__.__name__.lower()


def mount_module_processes(
    modules: Iterable[Any],
    *,
    workflows_router: APIRouter,
    pipelines_router: APIRouter,
    tools_router: APIRouter,
) -> None:
    workflows: list[Any] = []
    pipelines: list[Any] = []
    tools: list[Any] = []

    for module in modules:
        for workflow in getattr(module, "workflows", None) or []:
            if workflow is not None:
                workflows.append(workflow)
        for pipeline in getattr(module, "pipelines", None) or []:
            if pipeline is not None:
                pipelines.append(pipeline)
        for tool in getattr(module, "tools", None) or []:
            if tool is not None:
                tools.append(tool)

    for workflow in sorted(workflows, key=_sort_key):
        logger.debug("Adding workflow to API: %s", workflow.__class__.__name__)
        mount_expose_process(workflow, workflows_router)

    for pipeline in sorted(pipelines, key=_sort_key):
        logger.debug("Adding pipeline to API: %s", pipeline.__class__.__name__)
        mount_expose_process(pipeline, pipelines_router)

    for tool in sorted(tools, key=_sort_key):
        if not callable(getattr(tool, "as_api", None)):
            logger.debug(
                "Skipping LangChain-only tool %s. No REST path invented.",
                getattr(tool, "name", tool.__class__.__name__),
            )
            continue
        logger.debug("Adding tool to API: %s", tool.__class__.__name__)
        mount_expose_process(tool, tools_router)
