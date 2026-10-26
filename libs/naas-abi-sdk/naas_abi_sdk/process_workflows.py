"""``Workflow`` and ``Pipeline`` classes as one-step durable workflows.

Every class a remote module declares or finds under ``workflows/`` and ``pipelines/``
is declared on the module as a workflow (``naas_abi_sdk.workflows``) named
``workflow.<slug>`` or ``pipeline.<slug>`` (``process_workflow_name``), as core's
bridge publishes an engine module's classes (``EngineProcessBridge``): same names,
same input schema (the parameters model), same result encoding. Other modules, Nexus
and scripts start it by name; it has a run record and appears in the Jobs tab.

The workflow's one step, ``run``, awaits the built instance's ``run`` and journals the
encoded result, so a retried run does not run a finished ``run`` again. ``job =
JobSettings(...)`` on the class gives the workflow triggers and limits; without it the
workflow has no trigger, one attempt and one run at a time. See
docs/adr/20261025_remote-module-workflows-pipelines-ontologies.md.

Needs the ``workflows`` extra (``naas_abi_sdk.processes``).
"""

from __future__ import annotations

import asyncio
import json
import typing
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ValidationError
from pydantic_core import to_jsonable_python

from naas_abi_sdk.jobs import JobSettings, process_workflow_name
from naas_abi_sdk.processes import _graph_to_json, _is_graph
from naas_abi_sdk.workflows import InvalidWorkflowInput

# A run record keeps at most 64 KiB of output (the job host's cap, replaced by a
# truncation marker beyond it): any result must fit with its envelope. Core's bridge
# uses the same limit.
MAX_RESULT_BYTES = 60 * 1024
# What the descriptor keeps of the class docstring, in UTF-8 bytes: a module's whole
# descriptor is capped at 64 KiB, schemas included.
MAX_DESCRIPTION_BYTES = 512
STEP_KEY = "run"
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
OMITTED_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "omitted": {"type": "boolean", "const": True},
        "bytes": {"type": "integer"},
        "limit": {"type": "integer"},
        "note": {"type": "string"},
    },
    "required": ["omitted", "bytes", "limit"],
}
ANY_OUTPUT_SCHEMA: dict[str, Any] = {
    "description": (
        "Whatever run() returns, as JSON (a list, a string, a number, an object...), "
        "or the marker of a result too large to keep"
    )
}


def job_settings(cls: type) -> JobSettings:
    """What ``cls`` declares in ``job``, else the defaults (no trigger)."""
    settings = getattr(cls, "job", None)
    if settings is None:
        return JobSettings()
    if not isinstance(settings, JobSettings):
        raise TypeError(
            f"{cls.__name__}.job must be a JobSettings (or None), not "
            f"{type(settings).__name__}"
        )
    return settings


def _cut(text: str, limit: int) -> str:
    """``text`` within ``limit`` UTF-8 bytes, cut on a character boundary and
    ending in an ellipsis when something was left out."""
    if len(text.encode("utf-8")) <= limit:
        return text
    ellipsis = "…"
    room = limit - len(ellipsis.encode("utf-8"))
    kept = text.encode("utf-8")[:room].decode("utf-8", errors="ignore")
    return kept.rstrip() + ellipsis


def encode_process_result(result: Any, max_bytes: int = MAX_RESULT_BYTES) -> Any:
    """A ``run()`` result as the JSON its step journals, at most ``max_bytes`` of it.

    An rdflib ``Graph`` becomes ``{"format": "text/turtle", "triples": n, "data":
    "<turtle>"}``, ``data`` left out (with a ``note``) above ``max_bytes``. Anything
    else is dumped as pydantic does (``serialize_result``), and a value over
    ``max_bytes`` becomes ``{"omitted": true, "bytes": n, "limit": max_bytes, ...}``:
    ``run`` has done its work, so failing the run would only make a re-launch repeat it.
    """
    if _is_graph(result):
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
    value = to_jsonable_python(result, fallback=_graph_to_json)
    size = len(json.dumps(value).encode())
    if size > max_bytes:
        return {
            "omitted": True,
            "bytes": size,
            "limit": max_bytes,
            "note": (
                f"The result is {size} bytes of JSON, over the {max_bytes} bytes a "
                "run record keeps of an output; it is left out. Whatever run() "
                "wrote elsewhere (the triple store, object storage) is unchanged."
            ),
        }
    return value


def output_schema(cls: type) -> dict[str, Any]:
    """The JSON Schema of what ``cls.run`` returns, when its annotation says;
    else a permissive one."""
    try:
        returned = typing.get_type_hints(cls.run).get("return")
    except Exception:  # noqa: BLE001 - an unresolvable annotation has no schema
        return ANY_OUTPUT_SCHEMA
    if isinstance(returned, type):
        if returned.__name__ == "Graph" and returned.__module__.startswith("rdflib"):
            return GRAPH_OUTPUT_SCHEMA  # its own note covers a large graph
        if issubclass(returned, BaseModel):
            return {"anyOf": [returned.model_json_schema(), OMITTED_OUTPUT_SCHEMA]}
        if issubclass(returned, dict):
            return {"type": "object"}  # the marker is an object too
    return ANY_OUTPUT_SCHEMA


def parameters(cls: type, payload: Any) -> BaseModel:
    """``payload`` as ``cls``'s parameters model; ``InvalidWorkflowInput`` (no
    retry) naming the fields when it does not fit."""
    model = cls.parameters_type()
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        fields = ", ".join(
            ".".join(str(part) for part in error["loc"]) or "parameters"
            for error in exc.errors()
        )
        raise InvalidWorkflowInput(
            f"Invalid parameters for {model.__name__}: {fields}"
        ) from None


def check_classes(
    classes_by_kind: Mapping[str, Mapping[str, type]], taken: Iterable[str] = ()
) -> None:
    """Refuse, before the module connects, a workflow name in ``taken`` (the
    module's own jobs and workflows), a ``job`` that is not a ``JobSettings``,
    and a ``Cron`` or ``Every`` trigger whose input does not validate against
    the parameters model (a scheduled run has that input)."""
    taken = set(taken)
    for kind, classes in classes_by_kind.items():
        for name, cls in classes.items():
            if process_workflow_name(kind, name) in taken:
                raise ValueError(
                    f"The job {process_workflow_name(kind, name)!r} is declared "
                    f"explicitly, and the {kind} {cls.__name__} is published under "
                    "that name: rename the explicit job or workflow"
                )
            for trigger in job_settings(cls).triggers:
                if trigger.kind not in ("cron", "every"):
                    continue
                try:
                    parameters(cls, trigger.input or {})
                except InvalidWorkflowInput as exc:
                    raise ValueError(
                        f"The {kind} {name!r} has a {type(trigger).__name__} trigger "
                        f"whose input does not fit its parameters ({exc}). Give the "
                        "trigger an input=..., or the fields defaults."
                    ) from None


def process_handler(
    cls: type, instance: Callable[[], Any]
) -> Callable[[Any, Any], Any]:
    """The workflow handler of a class: ``run`` of the built instance as the one
    step. ``instance()`` returns it; a run only starts once it is built. An
    ``OnEvent`` run takes the event's ``data`` as its parameters."""

    async def handler(ctx: Any, inp: dict[str, Any]) -> Any:
        payload: Any = inp
        if ctx.trigger.get("kind") == "event":
            payload = inp.get("data")
            if payload is None:
                payload = {}
        params = parameters(cls, payload)

        async def run() -> Any:
            result = await instance().run(params)
            return await asyncio.to_thread(encode_process_result, result)

        return await ctx.step(STEP_KEY, run)

    handler.__name__ = cls.slug()
    return handler


def declare_process_workflows(
    module: Any,
    classes_by_kind: Mapping[str, Mapping[str, type]],
    bound_by_kind: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Declare each class (``{"workflow": {name: class}}``) on ``module`` as a
    workflow whose handler runs the instance ``bound_by_kind[kind][name]``.
    Returns the workflow names, in kind then name order. Raises when a name is
    already a job's: rename the explicit ``@job`` or ``@workflow``."""
    declared = []
    for kind in sorted(classes_by_kind):
        for name, cls in sorted(classes_by_kind[kind].items()):
            settings = job_settings(cls)
            workflow_name = process_workflow_name(kind, name)
            if any(j.name == workflow_name for j in module.jobs):
                raise ValueError(
                    f"{type(module).__name__} declares the job {workflow_name!r} "
                    f"itself, and its {kind} {cls.__name__} is published under that "
                    "name: rename the explicit job or workflow"
                )
            bound = bound_by_kind[kind]
            module.declare_workflow(
                workflow_name,
                process_handler(cls, lambda bound=bound, name=name: bound[name]),
                input_schema=cls.parameters_type().model_json_schema(),
                output_schema=output_schema(cls),
                description=_cut(cls.description(), MAX_DESCRIPTION_BYTES),
                triggers=settings.triggers,
                max_concurrency=settings.max_concurrency,
                timeout=settings.timeout,
                max_attempts=settings.max_attempts,
            )
            declared.append(workflow_name)
    return declared
