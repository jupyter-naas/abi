"""Publish ``Workflow`` and ``Pipeline`` instances as one-step durable workflows.

In NATS mode (``nats.workflows.bridge``, on by default) every instance in an engine
module's ``workflows`` and ``pipelines`` with a live typed ``run()``, the ones that
get a ``POST /workflows|/pipelines/<slug>`` route (``process_api.process_parameters_type``),
is declared at runtime as a workflow named ``workflow.<slug>`` or ``pipeline.<slug>``.
It then rides the jobs runtime: launched by name, awaited, listed in
``Engine.job_owners`` with its input schema, and visible in the Jobs tab.

The classes are unchanged: agent tools and REST routes still call ``run()`` in-process.
The workflow runs one step, ``run``, in the worker thread; ``max_attempts=1``, because
pipelines write to the triple store and a retry would write twice, and
``max_concurrency=1``, so two durable runs of one class never overlap (a REST call or
an agent tool still runs ``run()`` at the same time). See
naas_abi_core/module/AGENTS.md (Decision: durable workflows).
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.utils.process_api import (
    process_parameters_type,
    process_route_slug,
)

MAX_DESCRIPTION_CHARS = 2000
STEP_KEY = "run"
# (workflow name prefix, module attribute holding the instances)
PROCESS_KINDS = (("workflow", "workflows"), ("pipeline", "pipelines"))
# The result encoding and the output schemas are the SDK's
# (naas_abi_sdk.process_workflows: encode_process_result, output_schema), shared with
# remote modules' Workflow and Pipeline classes. Imported where they are used:
# naas-abi-sdk comes with the nats extra, and this module loads without it.


def process_workflow_name(kind: str, instance: Any) -> str:
    """``workflow.<slug>`` or ``pipeline.<slug>``: the slug of its REST route."""
    return f"{kind}.{process_route_slug(instance)}"


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

    from naas_abi_sdk.process_workflows import encode_process_result

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
    bridged = module.__dict__.setdefault("_abi_bridged_processes", {})
    if bridged.get(name) is instance:
        logger.debug(f"Workflow bridge: {label} is already published as {name!r}")
        return None
    if any(j.name == name for j in module.jobs):
        logger.warning(
            f"Workflow bridge: {label}: a job named {name!r} exists; skipped"
        )
        return None
    from naas_abi_sdk.process_workflows import output_schema

    try:
        # Same descriptor as the SDK's declare_workflow (naas_abi_sdk.workflows).
        module.declare_workflow(
            name,
            process_handler(instance),
            input_type=parameters,
            output_schema=output_schema(type(instance)),
            description=_description(instance),
            max_concurrency=1,
            max_attempts=1,
        )
    except Exception as exc:  # noqa: BLE001 - one class must not stop the engine
        logger.warning(f"Workflow bridge: {label} not published as {name!r}: {exc}")
        return None
    bridged[name] = instance
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
