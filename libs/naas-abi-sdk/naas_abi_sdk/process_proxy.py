"""Calls another module's workflows and pipelines over NATS.

``engine.modules["a"].get_workflow("x")`` and ``get_pipeline("x")`` return a
``ProcessProxy``. Each call goes to a ready instance of the module that declares
the process, with a token bound to that instance (``naas_abi_sdk.process_host``
serves it). A run is one attempt with a deadline: it is never retried, since the
process may have run, and a timeout can hide one that completed.

Needs no extra beyond the ``Graph`` a pipeline returns (``naas-abi-sdk[rdf]``)
and ``as_tools()`` (``naas-abi-sdk[agents]``).
"""

from __future__ import annotations

import asyncio
import json
import math
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from naas_abi_proto.process.v1 import process_pb2 as pb
from nats.errors import NoRespondersError

from naas_abi_sdk.app_streams import BodySource, ReaderGone, chunk_bytes, pull_body
from naas_abi_sdk.jobs import JobRun, process_job_name
from naas_abi_sdk.process_host import (
    DEFAULT_DEADLINE_SECONDS,
    MAX_BODY_BYTES,
    MAX_DEADLINE_SECONDS,
    fits_inline,
    process_subject,
    valid_inbox,
)
from naas_abi_sdk.transport import RPCError

if TYPE_CHECKING:
    from langchain_core.tools import StructuredTool

    from naas_abi_sdk.discovery import ModuleInstance, ModuleProxy

# Time the module has to answer after the caller's deadline passes (its own
# DEADLINE_EXCEEDED reply should arrive before the caller gives up waiting).
REPLY_MARGIN_SECONDS = 5.0
# Waiting for `describe`, which runs nothing.
DESCRIBE_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class ProcessDescription:
    """What a module says about one of its processes."""

    name: str
    kind: str
    description: str
    # JSON schema of the parameters model.
    parameters_schema: dict[str, Any]


class ProcessProxy:
    """A workflow or pipeline of another module.

    ``await proxy`` checks that it exists and loads its parameter schema, which
    ``as_tools()`` needs; ``run`` and ``describe`` work without it::

        result = await engine.modules["a"].get_workflow("greet").run({"name": "Ada"})
        pipeline = await engine.modules["a"].get_pipeline("ingest")
        tools = pipeline.as_tools()
    """

    def __init__(self, module: ModuleProxy, kind: str, name: str) -> None:
        self.module, self.kind, self.name = module, kind, name
        self._description: ProcessDescription | None = None

    def __repr__(self) -> str:
        return f"<{self.kind} {self.name!r} of {self.module.module_id!r}>"

    def __await__(self):
        return self._load().__await__()

    async def _load(self) -> ProcessProxy:
        await self.describe()
        return self

    async def _target(self) -> ModuleInstance:
        """A ready instance that declares this process, chosen at random."""
        ready = await self.module.ready_instances()  # MODULE_UNAVAILABLE
        eligible = [
            instance
            for instance in ready
            if any(
                p.name == self.name and p.kind == self.kind for p in instance.processes
            )
        ]
        if not eligible:
            raise RPCError(
                "PROCESS_NOT_FOUND",
                f"{self.module.module_id} declares no {self.kind} {self.name!r}",
            )
        instance = random.choice(eligible)
        descriptor = next(
            p for p in instance.processes if p.name == self.name and p.kind == self.kind
        )
        if descriptor.contract_major != 1:
            raise RPCError(
                "PROCESS_NOT_INVOKABLE",
                f"{self.kind} {self.name!r} has an unsupported contract",
            )
        return instance

    async def _call(
        self,
        operation: str,
        request: Any,
        response_type: Any,
        timeout: float,
        instance: ModuleInstance | None = None,
    ) -> Any:
        if instance is None:
            instance = await self._target()
        client = self.module.client
        try:
            return await client.transport.call(
                process_subject(
                    client.project,
                    instance.instance_id,
                    self.kind,
                    self.name,
                    operation,
                ),
                request,
                response_type,
                instance_id=instance.instance_id,
                timeout=timeout,
            )
        except NoRespondersError:
            raise RPCError(
                "MODULE_UNAVAILABLE",
                f"{self.module.module_id} stopped before the {self.kind} was called",
            ) from None
        except asyncio.TimeoutError:
            raise RPCError(
                "DEADLINE_EXCEEDED",
                f"{self.module.module_id} did not answer in {timeout:g} s; the "
                f"{self.kind} may still have run",
            ) from None

    async def describe(self) -> ProcessDescription:
        """The process's description and parameter schema, asked of the module."""
        response = await self._call(
            "describe",
            pb.DescribeRequest(name=self.name),
            pb.DescribeResponse,
            DESCRIBE_TIMEOUT_SECONDS,
        )
        try:
            schema = json.loads(response.parameters_schema_json or b"{}")
        except ValueError:
            raise RPCError("INTERNAL", "The parameter schema is not JSON") from None
        self._description = ProcessDescription(
            self.name, response.kind or self.kind, response.description, schema
        )
        return self._description

    async def run(
        self, params: Mapping[str, Any] | Any, *, timeout: float | None = None
    ) -> Any:
        """Run it with ``params`` (a dict, or a pydantic model) and return its result:
        the workflow's JSON value, or the pipeline's rdflib ``Graph``.

        ``timeout`` is the deadline in seconds (300 by default, at most 3600): the module
        cancels the run when it passes. One attempt, never retried; raises
        ``RPCError`` (``PROCESS_NOT_FOUND``, ``MODULE_UNAVAILABLE``,
        ``INVALID_ARGUMENT`` for parameters the process refuses,
        ``DEADLINE_EXCEEDED``, ``PROCESS_ERROR``, ``PERMISSION_DENIED``).
        """
        seconds = DEFAULT_DEADLINE_SECONDS if timeout is None else float(timeout)
        if not math.isfinite(seconds) or not 0 < seconds <= MAX_DEADLINE_SECONDS:
            raise ValueError(
                f"timeout must be above 0 and at most {MAX_DEADLINE_SECONDS:g} seconds"
            )
        raw = _encode_parameters(params)
        # Before any inbox or feeder exists: nothing to undo if discovery is slow
        # or says no.
        instance = await self._target()
        nc = await self.module.client.transport.connect()
        request = pb.RunRequest(name=self.name, deadline_seconds=seconds)
        source: BodySource | None = None
        feeder: asyncio.Task | None = None
        if fits_inline(nc.max_payload, len(raw)):
            request.parameters_json = raw
        else:
            if len(raw) > MAX_BODY_BYTES:
                raise RPCError(
                    "PAYLOAD_TOO_LARGE", f"Parameters exceed {MAX_BODY_BYTES} bytes"
                )
            source = BodySource(nc)
            await source.start()
            request.parameters_inbox, request.parameters_bytes = source.inbox, len(raw)
            feeder = asyncio.create_task(
                _feed(source, raw, chunk_bytes(nc.max_payload))
            )
        try:
            response = await self._call(
                "run",
                request,
                pb.RunResponse,
                seconds + REPLY_MARGIN_SECONDS,
                instance,
            )
            payload = await self._payload(nc, response)
        finally:
            if feeder is not None:
                feeder.cancel()
                await asyncio.gather(feeder, return_exceptions=True)
            if source is not None:
                await source.close()
        return await self._decode(payload)

    async def trigger(
        self, params: Mapping[str, Any] | Any, *, idempotency_key: str | None = None
    ) -> JobRun:
        """Start it as a durable job run and return the ``JobRun``, without waiting.

        Needs the process to be bound as a job (``job = JobSettings(...)`` on its
        class): ``RPCError`` ``PROCESS_NOT_A_JOB`` otherwise, ``MODULE_UNAVAILABLE``
        when the module has no ready instance to read that from. Any replica takes
        the run, and it waits in the stream until one does::

            run = await proxy.trigger({"since": "2026-01-01"})
            record = await run.wait(timeout=600)
            record["result"]  # a workflow's JSON; a pipeline's graph as N-Triples text

        The record keeps at most 64 KiB of result (``job_host.MAX_RESULT_BYTES``);
        above it, a ``{"truncated": true, "preview": ...}``. Parameters the process
        refuses end the run ``FAILED`` (the host validates them, not this call).
        A repeated ``idempotency_key`` within 2 minutes is the same run
        (``JobRun.duplicate``). Delivery is at least once: a run can start again
        after a host crashed, so the process must be safe to repeat.
        """
        data = _parameters(params)
        job_name = process_job_name(self.kind, self.name)
        try:
            job = await self.module.get_job(job_name)
        except RPCError as exc:
            if exc.code != "JOB_NOT_FOUND":
                raise
            raise RPCError(
                "PROCESS_NOT_A_JOB",
                f"{self.module.module_id} has no job for the {self.kind} "
                f"{self.name!r}: declare `job = JobSettings(...)` on its class",
            ) from None
        return await job.trigger(data, idempotency_key=idempotency_key)

    async def _payload(self, nc: Any, response: pb.RunResponse) -> bytes:
        if not response.body_inbox:
            return (
                response.graph_nt if self.kind == "pipeline" else response.result_json
            )
        size = response.body_bytes
        if not valid_inbox(response.body_inbox) or not 0 < size <= MAX_BODY_BYTES:
            raise RPCError("INTERNAL", "The module answered with an invalid body")
        data = bytearray()
        async for chunk in pull_body(nc, response.body_inbox, max_bytes=size):
            data.extend(chunk)
        if len(data) != size:
            raise RPCError("INTERNAL", "The result is shorter than announced")
        return bytes(data)

    async def _decode(self, payload: bytes) -> Any:
        if self.kind == "pipeline":
            return await asyncio.to_thread(_parse_graph, payload)
        if not payload:
            raise RPCError("INTERNAL", "The module answered without a result")
        try:
            return json.loads(payload)
        except ValueError:
            raise RPCError("INTERNAL", "The result is not JSON") from None

    def as_tools(self) -> list[StructuredTool]:
        """One LangChain tool that runs this process: named after it, described by
        the module's description, its arguments the parameter schema. Await the
        proxy first (it loads the schema), and create the tool inside the running
        module, as ``agent_tools`` does: the call runs on the module's loop. A
        pipeline's graph comes back as turtle."""
        description = self._description
        if description is None:
            raise RuntimeError(
                f"The schema of {self!r} is not loaded: "
                f"`proxy = await module.get_{self.kind}({self.name!r})` first"
            )
        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:
            raise ImportError(
                "ProcessProxy.as_tools needs LangChain: pip install 'naas-abi-sdk[agents]'"
            ) from exc
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        async def call(**arguments: Any) -> Any:
            result = await self.run(arguments)
            if self.kind == "pipeline":
                return {"format": "turtle", "data": result.serialize(format="turtle")}
            return result

        def call_from_thread(**arguments: Any) -> Any:
            if loop is None or not loop.is_running():
                raise RuntimeError(
                    "Create remote tools inside the running module; use ainvoke "
                    "for async callers"
                )
            try:
                current = asyncio.get_running_loop()
            except RuntimeError:
                current = None
            if current is loop:
                raise RuntimeError("Use tool.ainvoke on the module event loop")
            return asyncio.run_coroutine_threadsafe(call(**arguments), loop).result()

        return [
            StructuredTool.from_function(
                func=call_from_thread,
                coroutine=call,
                name=self.name,
                description=description.description or self.name,
                args_schema=description.parameters_schema,
            )
        ]


def _parameters(params: Any) -> dict[str, Any]:
    """``params`` as a JSON-checked dict."""
    if callable(getattr(params, "model_dump", None)):
        data = params.model_dump(mode="json")
    elif isinstance(params, Mapping):
        data = dict(params)
    else:
        raise TypeError("A run takes a dict or a pydantic model of parameters")
    try:
        json.dumps(data, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f"Parameters must be JSON-serializable: {exc}") from exc
    return data


def _encode_parameters(params: Any) -> bytes:
    return json.dumps(
        _parameters(params), allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


async def _feed(source: BodySource, data: bytes, size: int) -> None:
    """Hold ``data`` for the module to pull, one chunk per pull."""
    view = memoryview(data)
    try:
        for offset in range(0, len(data), size):
            await source.put(bytes(view[offset : offset + size]))
        await source.finish()
    except ReaderGone:
        pass


def _parse_graph(payload: bytes) -> Any:
    try:
        from rdflib import Graph
    except ImportError as exc:
        raise ImportError(
            "A pipeline returns an rdflib Graph: pip install 'naas-abi-sdk[rdf]'"
        ) from exc
    graph = Graph()
    try:
        graph.parse(data=payload.decode("utf-8"), format="nt")
    except Exception:  # noqa: BLE001 - rdflib raises many parser errors
        raise RPCError("INTERNAL", "The pipeline's graph is not N-Triples") from None
    return graph
