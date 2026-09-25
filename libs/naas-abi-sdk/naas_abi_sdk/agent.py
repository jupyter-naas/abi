"""Async proxy for an agent owned by a discovered module process."""

from __future__ import annotations

import asyncio
import hashlib
import math
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from naas_abi_proto.agent.v1 import agent_pb2 as pb
from nats.errors import Error as NATSError

from naas_abi_sdk.transport import RPCError

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}


def agent_subject(project: str, instance_id: str, name: str, operation: str) -> str:
    digest = hashlib.sha256(name.encode()).hexdigest()
    return f"abi.agent.{project}.{instance_id}.{digest}.v1.{operation}"


@dataclass
class AgentState:
    thread_id: str = field(default_factory=lambda: str(uuid4()))

    def set_thread_id(self, thread_id: str) -> None:
        if not thread_id:
            raise ValueError("thread_id must be nonempty")
        self.thread_id = thread_id


@dataclass(frozen=True)
class InvocationStatus:
    invocation_id: str
    thread_id: str
    status: str
    result: str
    error_code: str
    error_message: str
    owner_instance_id: str
    owner_available: bool
    events: tuple[dict[str, Any], ...]
    last_sequence: int


def _status(value: pb.Invocation) -> InvocationStatus:
    return InvocationStatus(
        value.invocation_id,
        value.thread_id,
        value.status,
        value.result,
        value.error_code,
        value.error_message,
        value.owner_instance_id,
        value.owner_available,
        tuple(
            {"sequence": e.sequence, "event": e.event, "data": e.data}
            for e in value.events
        ),
        value.last_sequence,
    )


class SubmissionUncertain(RuntimeError):
    def __init__(self, handle: InvocationHandle):
        self.handle = handle
        super().__init__(
            f"Invocation {handle.invocation_id}: submission outcome is unknown; query handle.status() before retrying"
        )


class InvocationHandle:
    def __init__(self, agent: AgentProxy, invocation_id: str):
        self.agent, self.invocation_id = agent, invocation_id
        self.owner_instance_id = ""
        self._last_status: InvocationStatus | None = None
        self._result_cache: str | None = None

    async def _output(self, sequence: int, parts: int) -> str:
        content = bytearray()
        for part in range(parts):
            response = await self.agent._rpc(
                "event",
                pb.EventRequest(
                    invocation_id=self.invocation_id, sequence=sequence, part=part
                ),
                pb.EventResponse,
                self.owner_instance_id,
            )
            content.extend(response.data)
        return content.decode()

    async def _decode(self, value: pb.Invocation) -> InvocationStatus:
        self.owner_instance_id = value.owner_instance_id
        for event in value.events:
            if event.parts:
                event.data = await self._output(event.sequence, event.parts)
        if value.result_parts:
            if self._result_cache is None:
                self._result_cache = await self._output(0, value.result_parts)
            value.result = self._result_cache
        return _status(value)

    async def status(self, *, after_sequence: int = 0) -> InvocationStatus:
        response = await self.agent._rpc(
            "status",
            pb.StatusRequest(
                invocation_id=self.invocation_id,
                after_sequence=after_sequence,
                output_format=2,
            ),
            pb.StatusResponse,
            self.owner_instance_id,
        )
        status = await self._decode(response.invocation)
        self.owner_instance_id = status.owner_instance_id
        self._last_status = status
        return status

    async def cancel(self) -> InvocationStatus:
        response = await self.agent._rpc(
            "cancel",
            pb.CancelRequest(invocation_id=self.invocation_id, output_format=2),
            pb.CancelResponse,
            self.owner_instance_id,
        )
        return await self._decode(response.invocation)

    async def events(
        self, *, after_sequence: int = 0, timeout: float | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("timeout must be finite and positive")
        deadline = (
            asyncio.get_running_loop().time() + timeout
            if timeout is not None
            else float("inf")
        )
        cursor = after_sequence
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise RPCError(
                    "WAIT_TIMEOUT",
                    f"Invocation {self.invocation_id} may still be running; use status() or cancel()",
                )
            try:
                status = await asyncio.wait_for(
                    self.status(after_sequence=cursor), remaining
                )
            except asyncio.TimeoutError as exc:
                raise RPCError(
                    "WAIT_TIMEOUT",
                    f"Invocation {self.invocation_id}: status request timed out",
                ) from exc
            for event in status.events:
                cursor = event["sequence"]
                yield event
            if status.status in TERMINAL:
                if cursor < status.last_sequence:
                    continue
                if status.status != "SUCCEEDED":
                    raise RPCError(
                        status.error_code or status.status,
                        status.error_message or status.status,
                    )
                return
            if not status.owner_available:
                raise RPCError(
                    "OWNER_UNAVAILABLE",
                    f"Invocation {self.invocation_id} has no registered owner; execution outcome is unknown and is not replayed",
                )
            await asyncio.sleep(
                min(0.1, max(0, deadline - asyncio.get_running_loop().time()))
            )

    async def result(self, *, timeout: float | None = None) -> str:
        async for _ in self.events(timeout=timeout):
            pass
        assert self._last_status is not None
        return self._last_status.result


class AgentProxy:
    def __init__(self, module, descriptor, *, state: AgentState | None = None):
        self.module, self.descriptor = module, descriptor
        self.name, self.description = descriptor.name, descriptor.description
        self.state = state or AgentState()
        self._instances = (0.0, ())

    async def _rpc(self, operation: str, request, response_type, owner: str = ""):
        now = asyncio.get_running_loop().time()
        if operation == "submit":
            instances = await self.module.ready_instances()
        elif now < self._instances[0]:
            instances = self._instances[1]
        else:
            instances = await self.module.instances()
            self._instances = (now + 1.0, instances)
        eligible = [
            i
            for i in instances
            if any(
                a.name == self.name
                and a.contract_major == self.descriptor.contract_major
                and "agent.invoke.v1" in a.capabilities
                for a in i.agents
            )
        ]
        if not eligible:
            raise RPCError("AGENT_UNAVAILABLE", self.name)
        target = next((i for i in eligible if i.instance_id == owner), eligible[0])
        try:
            return await self.module.client.transport.call(
                agent_subject(
                    self.module.client.project, target.instance_id, self.name, operation
                ),
                request,
                response_type,
            )
        except (NATSError, asyncio.TimeoutError, OSError, RPCError):
            self._instances = (0.0, ())
            raise

    def invocation(self, invocation_id: str) -> InvocationHandle:
        return InvocationHandle(self, invocation_id)

    async def submit(
        self,
        prompt: str,
        *,
        invocation_id: str | None = None,
        stream: bool = False,
        deadline_seconds: int | None = None,
    ) -> InvocationHandle:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be text")
        handle = self.invocation(invocation_id or str(uuid4()))
        try:
            response = await self._rpc(
                "submit",
                pb.SubmitRequest(
                    invocation_id=handle.invocation_id,
                    thread_id=self.state.thread_id,
                    prompt=prompt,
                    mode="stream" if stream else "invoke",
                    deadline_seconds=deadline_seconds or 0,
                    output_format=2,
                ),
                pb.SubmitResponse,
            )
        except (NATSError, asyncio.TimeoutError, OSError) as exc:
            raise SubmissionUncertain(handle) from exc
        except RPCError as exc:
            if exc.code in ("UNAVAILABLE", "INTERNAL", "PAYLOAD_TOO_LARGE"):
                raise SubmissionUncertain(handle) from exc
            raise
        handle.owner_instance_id = response.invocation.owner_instance_id
        return handle

    async def invoke(
        self,
        prompt: str,
        *,
        invocation_id: str | None = None,
        timeout: float | None = None,
    ) -> str:
        if timeout is not None and (
            not math.isfinite(timeout) or not 1 <= timeout <= 3600
        ):
            raise ValueError("timeout must be 1..3600 seconds")
        handle = await self.submit(
            prompt,
            invocation_id=invocation_id,
            deadline_seconds=math.ceil(timeout) if timeout is not None else None,
        )
        return await handle.result(timeout=timeout)

    async def stream_invoke(
        self,
        prompt: str,
        *,
        invocation_id: str | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[dict[str, str]]:
        if timeout is not None and (
            not math.isfinite(timeout) or not 1 <= timeout <= 3600
        ):
            raise ValueError("timeout must be 1..3600 seconds")
        handle = await self.submit(
            prompt,
            invocation_id=invocation_id,
            stream=True,
            deadline_seconds=math.ceil(timeout) if timeout is not None else None,
        )
        async for event in handle.events(timeout=timeout):
            yield {"event": event["event"], "data": event["data"]}

    def duplicate(
        self, queue=None, agent_shared_state: AgentState | None = None
    ) -> AgentProxy:
        if queue is not None:
            raise NotImplementedError(
                "Use stream_invoke instead of a process-local event queue"
            )
        return AgentProxy(
            self.module, self.descriptor, state=agent_shared_state or AgentState()
        )

    def as_tools(self, parent_graph: bool = False) -> list:
        if parent_graph:
            raise NotImplementedError("Remote agents do not share a parent graph state")
        try:
            from naas_abi_sdk.agent_tools import agent_tools
        except ImportError as exc:
            raise ImportError(
                "Install naas-abi-sdk[agents] for LangChain tools"
            ) from exc
        return agent_tools(self)

    def stream(self, prompt: str):
        raise NotImplementedError(
            "Raw LangGraph objects stay in the owner process; use stream_invoke"
        )
