"""Workflows and pipelines as jobs: their descriptors and their job handlers.

A process class that declares ``job = JobSettings(...)`` (``naas_abi_sdk.jobs``) gets a
job named ``<kind>.<name>`` (``process_job_name``) in its module, hosted by the
module's job host like any other (``BaseModule.get_jobs`` adds it,
``BaseModule.build_processes`` binds its handler). A run validates its payload into
the process's parameters model, awaits ``run`` and records the encoded result on the
run record: the JSON value of a workflow, the graph of a pipeline as N-Triples text.
The record holds at most ``job_host.MAX_RESULT_BYTES`` of it: above that, it keeps a
``{"truncated": true, "preview": ...}`` of the first 2,000 characters.

Needs the ``workflows`` extra (``naas_abi_sdk.processes``) and ``nats``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from naas_abi_sdk.jobs import (
    JobContext,
    JobDescriptor,
    JobHandler,
    JobSettings,
    process_job_name,
)
from naas_abi_sdk.process_host import encode_result, parse_parameters

# The job's description is the first line of the class docstring, as `@job`'s is.
DESCRIPTION_CHARS = 512


def job_settings(cls: type) -> JobSettings | None:
    """The settings ``cls`` declares in ``job``, or None: it is no job."""
    settings = getattr(cls, "job", None)
    if settings is not None and not isinstance(settings, JobSettings):
        raise TypeError(
            f"{cls.__name__}.job must be a JobSettings (or None), not "
            f"{type(settings).__name__}"
        )
    return settings


def process_job_descriptors(
    classes_by_kind: Mapping[str, Mapping[str, type]],
) -> tuple[JobDescriptor, ...]:
    """The jobs of the declared process classes (``{"workflow": {name: class}}``),
    in kind then name order. A schedule on a process whose parameters need values
    is refused: a scheduled run has the payload ``{}``."""
    descriptors = []
    for kind in sorted(classes_by_kind):
        for name, cls in sorted(classes_by_kind[kind].items()):
            settings = job_settings(cls)
            if settings is None:
                continue
            first_line = cls.description().splitlines()[0]
            descriptor = settings.descriptor(
                process_job_name(kind, name), first_line[:DESCRIPTION_CHARS]
            )
            if descriptor.schedules:
                _check_empty_parameters(kind, name, cls)
            descriptors.append(descriptor)
    return tuple(descriptors)


def _check_empty_parameters(kind: str, name: str, cls: Any) -> None:
    try:
        cls.parameters_type().model_validate({})
    except ValidationError as exc:
        fields = ", ".join(
            ".".join(str(part) for part in error["loc"]) or "parameters"
            for error in exc.errors()
        )
        raise ValueError(
            f"The {kind} {name!r} has a Cron or Every trigger but its parameters "
            f"({cls.parameters_type().__name__}) need values ({fields}): a scheduled "
            "run has the payload {}. Give them defaults, or trigger it with OnEvent "
            "or by hand."
        ) from None


def process_job_handler(kind: str, instance: Any) -> JobHandler:
    """The job handler of a built workflow or pipeline.

    The payload is the parameters, as ``proxy.trigger`` sent them; for a run an
    event started it is the event's ``data`` (a JSON object, or none for ``{}``).
    A run asked to cancel (``JobRun.cancel``) cancels ``run`` and ends CANCELLED.
    """

    async def handle(ctx: JobContext) -> Any:
        payload: Any = ctx.payload
        if ctx.trigger.get("kind") == "event":
            payload = payload.get("data")
            if payload is None:
                payload = {}
        parameters = parse_parameters(type(instance), payload)
        run = asyncio.ensure_future(instance.run(parameters))
        cancelled = asyncio.ensure_future(ctx.cancelled.wait())
        try:
            await asyncio.wait({run, cancelled}, return_when=asyncio.FIRST_COMPLETED)
            if not run.done():
                # Cancelled by the caller: the host records CANCELLED.
                run.cancel()
                await asyncio.gather(run, return_exceptions=True)
                return None
            result = run.result()
        finally:
            for task in (run, cancelled):
                if not task.done():
                    task.cancel()
            await asyncio.gather(run, cancelled, return_exceptions=True)
        encoded = await asyncio.to_thread(encode_result, kind, result)
        if kind == "pipeline":
            return encoded.decode("utf-8")
        return json.loads(encoded)

    return handle
