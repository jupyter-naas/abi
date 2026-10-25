"""Publish ``Workflow`` and ``Pipeline`` instances as one-step durable workflows.

In NATS mode (``nats.workflows.bridge``, on by default) every instance in an engine
module's ``workflows`` and ``pipelines`` with a live typed ``run()``, the ones that
get a ``POST /workflows|/pipelines/<slug>`` route (``process_api.process_parameters_type``),
is declared at runtime as a workflow named ``workflow.<slug>`` or ``pipeline.<slug>``.
It then rides the jobs runtime: launched by name, awaited, listed in
``Engine.job_owners`` with its input schema, and visible in the Jobs tab.

The classes are unchanged: agent tools and REST routes still call ``run()`` in-process.
The workflow runs one step, ``run``, in the worker thread; ``max_concurrency=1`` and
``max_attempts=1``, because pipelines write to the triple store and a retry would
write twice. See docs/adr/20261025_durable-workflows-on-nats.md.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
from typing import Any, get_type_hints

from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.utils.process_api import (
    process_parameters_type,
    process_route_slug,
)
from pydantic import BaseModel

# A run record keeps at most 64 KiB of output (the job host's cap, with a marker
# beyond it): the Turtle of a graph must fit with its envelope.
MAX_RESULT_BYTES = 60 * 1024
MAX_DESCRIPTION_CHARS = 2000
GRAPH_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "format": {"type": "string", "const": "text/turtle"},
        "triples": {"type": "integer"},
        "data": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["format", "triples"],
}
STEP_KEY = "run"
# (workflow name prefix, module attribute holding the instances)
PROCESS_KINDS = (("workflow", "workflows"), ("pipeline", "pipelines"))


def process_workflow_name(kind: str, instance: Any) -> str:
    """``workflow.<slug>`` or ``pipeline.<slug>``: the slug of its REST route."""
    return f"{kind}.{process_route_slug(instance)}"


def encode_process_result(result: Any, max_bytes: int = MAX_RESULT_BYTES) -> Any:
    """A ``run()`` result as the JSON a step journals.

    A pydantic model is dumped; ``dict``, ``list`` and ``str`` stay as they are; an
    rdflib ``Graph`` becomes ``{"format": "text/turtle", "triples": n, "data":
    "<turtle>"}``, with ``data`` left out and a ``note`` saying why when the Turtle
    is over ``max_bytes`` (most pipelines write their triples to the store themselves,
    so the graph is a courtesy, not the result).
    """
    from rdflib import Graph

    if isinstance(result, Graph):
        data = result.serialize(format="turtle")
        encoded: dict[str, Any] = {"format": "text/turtle", "triples": len(result)}
        size = len(data.encode())
        if size <= max_bytes:
            encoded["data"] = data
        else:
            encoded["note"] = (
                f"Turtle omitted: {size} bytes, over the {max_bytes} bytes a run "
                "record keeps of an output"
            )
        return encoded
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, (bytes, bytearray)):
        return {"data": result.decode("utf-8", errors="replace")}
    return result


def _output_schema(instance: Any) -> dict[str, Any] | None:
    """The JSON Schema of what ``run()`` returns, when its annotation says."""
    from rdflib import Graph

    try:
        returned = get_type_hints(type(instance).run).get("return")
    except Exception:  # noqa: BLE001 - an unresolvable annotation just has no schema
        return None
    if isinstance(returned, type):
        if issubclass(returned, Graph):
            return GRAPH_OUTPUT_SCHEMA
        if issubclass(returned, BaseModel):
            return returned.model_json_schema()
        if issubclass(returned, dict):
            return {"type": "object"}
    return None


def _description(instance: Any) -> str:
    # The class's own docstring: getdoc would hand a subclass without one the base's.
    doc = inspect.cleandoc(type(instance).__doc__ or "")
    if len(doc) > MAX_DESCRIPTION_CHARS:
        doc = doc[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"
    return doc or type(instance).__name__


def process_handler(instance: Any) -> Callable[[Any, Any], Any]:
    """The sync workflow handler of ``instance``: its ``run`` as the one step.

    The input is already the parameters model (the runtime validates it first, and an
    invalid one fails the run without a retry).
    """

    def handler(ctx: Any, inp: Any) -> Any:
        return ctx.step(STEP_KEY, lambda: encode_process_result(instance.run(inp)))

    handler.__name__ = process_route_slug(instance)
    return handler


def declare_process_workflow(module: Any, kind: str, instance: Any) -> str | None:
    """Declare ``instance`` on ``module`` as a workflow. Returns its name, or None
    when it does not qualify or could not be declared."""
    label = f"{type(instance).__name__} of {type(module).__name__}"
    parameters = process_parameters_type(instance)
    if parameters is None:
        logger.debug(f"Workflow bridge: {label} has no live typed run(); skipped")
        return None
    if inspect.iscoroutinefunction(getattr(type(instance), "run", None)):
        logger.debug(f"Workflow bridge: {label} has an async run(); skipped")
        return None
    name = process_workflow_name(kind, instance)
    if any(j.name == name for j in module.jobs):
        logger.warning(
            f"Workflow bridge: {label}: a job named {name!r} exists; skipped"
        )
        return None
    try:
        module.declare_workflow(
            name,
            process_handler(instance),
            input_type=parameters,
            output_schema=_output_schema(instance),
            description=_description(instance),
            max_concurrency=1,
            max_attempts=1,
        )
    except Exception as exc:  # noqa: BLE001 - one class must not stop the engine
        logger.warning(f"Workflow bridge: {label} not published as {name!r}: {exc}")
        return None
    return name


def bridge_processes(
    modules: Mapping[str, Any] | Iterable[tuple[str, Any]],
    configuration: NATSConfiguration | None,
) -> list[str]:
    """Declare the workflows of every module's qualifying ``Workflow`` and
    ``Pipeline`` instances: a no-op without NATS or with ``nats.workflows.bridge``
    off. Call it once the modules are initialized and before their jobs go to a host.
    Returns ``<module id>:<workflow name>`` of what it declared."""
    if configuration is None:
        return []
    if not configuration.workflows.bridge:
        logger.info("Workflow bridge disabled (nats.workflows.bridge: false)")
        return []
    try:
        import naas_abi_sdk.workflows  # noqa: F401
    except ImportError:
        logger.warning("Workflow bridge needs naas-abi-sdk (naas-abi-core[nats])")
        return []
    items = modules.items() if isinstance(modules, Mapping) else modules
    declared: list[str] = []
    for module_id, module in items:
        if not callable(getattr(module, "declare_workflow", None)):
            continue
        for kind, attribute in PROCESS_KINDS:
            for instance in getattr(module, attribute, None) or []:
                name = declare_process_workflow(module, kind, instance)
                if name is not None:
                    declared.append(f"{module_id}:{name}")
    if declared:
        logger.info(
            f"Workflow bridge: {len(declared)} workflow(s) from Workflow/Pipeline "
            f"classes: {sorted(declared)}"
        )
    return declared
