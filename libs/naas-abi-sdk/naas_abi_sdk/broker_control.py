"""Streams and consumers a module uses, created by the engine on its behalf.

Behind the broker's auth callout a module may not create or change a stream
or a consumer: their subjects and delivery subjects travel in the request
body, which the broker never reads, so a module could capture or redirect any
subject (docs/adr/20261013_engine-tokens-service-accounts-broker.md). It asks
the engine instead, at ``abi.broker.v1.<operation>``, with its token; the
engine checks the request against the module's approved policy and creates
what is missing:

* ``ensure_topic`` ``{topic}``: a bus topic's queue stream;
* ``ensure_queue`` ``{topic, routing_key}``: the stream and the durable pull
  consumer ``BusClient.dequeue`` reads;
* ``ensure_job`` ``{project, job, max_concurrency, ack_wait_seconds,
  update}``: the jobs stream and one of the module's job consumers;
* ``set_schedules`` ``{project, job, schedules}``: a job's schedules (their
  ``Nats-Schedule``, ``-Time-Zone`` and ``-TTL`` headers), the rest removed;
* ``trigger`` ``{project, module_id, job, body, headers}``: store a trigger,
  answered with its stream ``seq``;
* ``cancel`` ``{project, module_id, job, run_id}``: ask a job's host to cancel
  a run;
* ``ensure_claim_checks`` ``{}``: the ``ABI_CLAIM_CHECKS`` stream;
* ``read_claim_check`` ``{reference, index}``: one chunk of a claim check, raw
  (``read``): a module reads none by direct get, which JetStream answers on
  the reply subject the requester chose;
* ``verify_trigger`` ``{fields, seal}``: whether the engine sealed a trigger,
  schedule or cancel (``jobs.seal_fields``).

A module writes nothing into the jobs stream itself: its schedules make the
server allow rollups there, and one ``Nats-Rollup: all`` would purge every
module's triggers and schedules.

Requests and replies are JSON. Without an engine answering (a broker without
the auth callout), ``request`` returns None and the caller does it itself,
as it always did.
"""

from __future__ import annotations

import json
import time
import weakref
from typing import Any

SUBJECT_PREFIX = "abi.broker.v1"
OPERATIONS = (
    "ensure_topic",
    "ensure_queue",
    "ensure_job",
    "set_schedules",
    "trigger",
    "cancel",
    "ensure_claim_checks",
    "read_claim_check",
    "verify_trigger",
)
AUTH_HEADER = "Nats-Auth-Token"
STATUS_HEADER = "Abi-Broker-Status"
ERROR_HEADER = "Abi-Broker-Error"
# After no engine answered, how long to assume there is none.
ABSENT_SECONDS = 60.0


_controls: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def for_transport(transport: Any) -> BrokerControl:
    """The one ``BrokerControl`` of ``transport`` (it remembers an absent engine)."""
    control = _controls.get(transport)
    if control is None:
        control = _controls[transport] = BrokerControl(transport)
    return control


class BrokerControlError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class BrokerControl:
    """Asks the engine over ``transport`` (a ``Transport``: its connection and
    its token)."""

    def __init__(self, transport: Any) -> None:
        self.transport = transport
        self._absent_until = 0.0

    async def request(
        self,
        operation: str,
        *,
        credentials: dict[str, str] | None = None,
        **fields: Any,
    ) -> dict[str, Any] | None:
        """The engine's answer once it did it; None when no engine answers.

        ``credentials``: the request's headers instead of this transport's
        token alone (``Transport.auth_headers``: its token and the user it acts
        for); the engine stores them with the trigger or cancel it writes."""
        reply = await self._ask(operation, fields, credentials)
        if reply is None:
            return None
        try:
            answer = json.loads(reply.data or b"{}")
        except ValueError:
            raise BrokerControlError("INTERNAL", "unreadable answer") from None
        if not isinstance(answer, dict):
            raise BrokerControlError("INTERNAL", "unreadable answer")
        error = answer.get("error")
        if error:
            raise BrokerControlError(
                str(error.get("code", "INTERNAL")), str(error.get("message", ""))
            )
        return answer

    async def read(self, operation: str, **fields: Any) -> bytes | None:
        """A raw answer (``read_claim_check``); None when no engine answers."""
        reply = await self._ask(operation, fields, None)
        if reply is None:
            return None
        headers = reply.headers or {}
        if headers.get(STATUS_HEADER) == "ok":
            return reply.data or b""
        try:
            error = json.loads(headers.get(ERROR_HEADER) or "{}")
        except ValueError:
            error = {}
        raise BrokerControlError(
            str(error.get("code", "INTERNAL")), str(error.get("message", ""))
        )

    async def _ask(
        self,
        operation: str,
        fields: dict[str, Any],
        credentials: dict[str, str] | None,
    ) -> Any:
        from nats.errors import NoRespondersError

        if operation not in OPERATIONS:
            raise ValueError(f"Unknown broker operation {operation!r}")
        if time.monotonic() < self._absent_until:
            return None  # no engine answered a moment ago
        nc = await self.transport.connect()
        headers = credentials or {AUTH_HEADER: await self.transport.access_token()}
        try:
            # Bounded by construction: names and numbers, and a trigger's body
            # claim-checked first (jobs.trigger_reserve).
            return await nc.request(
                f"{SUBJECT_PREFIX}.{operation}",
                json.dumps(fields).encode(),
                headers=headers,
                timeout=self.transport.timeout,
            )
        except NoRespondersError:
            self._absent_until = time.monotonic() + ABSENT_SECONDS
            return None
