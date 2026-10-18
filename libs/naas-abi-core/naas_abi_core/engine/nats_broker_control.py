"""The streams, consumers and job messages modules use, written by the engine (RFC §8.4).

Behind the broker's auth callout a module may not create or change a stream
or a consumer: their subjects, filters and delivery subjects travel in the
request body, which the broker never reads, so a module could capture any
subject into a stream or have a consumer deliver anywhere. Nor does it write
into the jobs stream, where its schedules make the server allow rollups (one
``Nats-Rollup: all`` would purge every module's triggers and schedules), or
read claim checks by direct get (JetStream answers on the reply subject the
requester chose, and a stream there would store a message of its choosing,
headers and all). It asks the engine at ``abi.broker.v1.<operation>``
(``naas_abi_sdk.broker_control``) with its token. The engine decides each
request with IAM on its concrete resource (Deny statements included), within
the subjects the module is granted (``IAMService.broker_grants``), and does it
over its own login:

* ``ensure_topic`` (``bus:Publish``), ``ensure_queue`` (``bus:Consume``): a bus
  topic's queue stream, and the pull consumer of one routing key;
* ``ensure_job`` (``discovery:ListJobs``), ``set_schedules``
  (``discovery:ScheduleJob``): one of the jobs the module hosts (named in its
  policy), the jobs stream, the job's pull consumer, its schedules (always
  aimed at its own trigger);
* ``trigger`` (``discovery:TriggerJob``), ``cancel``
  (``discovery:CancelJobRun``): a trigger or a cancel of a named module's job.
  The engine sets the trigger's kind (``event`` for the job's own module only,
  else ``manual``) and TTL, scopes its id (``Nats-Msg-Id``) to the caller and
  the job, and passes through the trace and claim-check headers only;
* ``ensure_claim_checks``, ``read_claim_check``: the ``ABI_CLAIM_CHECKS``
  stream, and one chunk of a claim check under a scope the caller may read
  (a topic it may consume, the triggers of a job it hosts), answered raw;
* ``verify_trigger``: whether a seal is the engine's.

Every trigger, schedule and cancel the engine writes carries a seal
(``naas_abi_sdk.jobs.SEAL_HEADER``, an HMAC with a key in ``IAMSecrets``); a
module's job host takes no other. ``engine`` and ``api`` are not checked (their
logins could do it all anyway). A request whose reply subject is not an inbox
is dropped before anything is done (``messages.reply_allowed``).
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import math
from typing import Any

import nats
from naas_abi_core import logger
from naas_abi_core.engine.call_context import (
    ON_BEHALF_OF_HEADER,
    CallContext,
    Principal,
    use_call_context,
)
from naas_abi_core.engine.nats_auth import InvalidServiceTokenError, TokenVerifier
from naas_abi_core.engine.nats_identity import AUTH_HEADER, caller_context
from naas_abi_core.engine.nats_naming import connection_name
from naas_abi_core.services.iam import broker
from naas_abi_core.services.iam.IAMPorts import IAMError
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.modules import parse_account
from naas_abi_core.services.iam.names import resource_name
from naas_abi_sdk.messages import message_size, reply_allowed

SUBJECT_PREFIX = "abi.broker.v1"
QUEUE = "abi-broker-control"
# Service accounts whose own logins may do all of it: nothing to check.
TRUSTED = frozenset({"engine", "api"})
MAX_ACK_WAIT_SECONDS = 3600.0
# A raw answer (read_claim_check) carries its outcome in these headers.
STATUS_HEADER = "Abi-Broker-Status"
ERROR_HEADER = "Abi-Broker-Error"
RAW_OPERATIONS = frozenset({"read_claim_check"})


class Refused(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class BrokerControl:
    def __init__(self, iam: IAMService, verifier: TokenVerifier, nats_url: str) -> None:
        """``nats_url``: the engine's own login (it does the work)."""
        self.iam = iam
        self.verifier = verifier
        self.nats_url = nats_url
        self._nc: Any = None
        self._tasks: set[asyncio.Task] = set()
        # principal id -> (store revision, its grants)
        self._grants: dict[str, tuple[int, broker.BrokerPermissions]] = {}

    async def start(self) -> None:
        self._nc = await nats.connect(
            self.nats_url, name=connection_name("abi-engine:broker-control")
        )
        await self._nc.subscribe(f"{SUBJECT_PREFIX}.*", queue=QUEUE, cb=self._handle)
        await self._nc.flush()

    async def stop(self) -> None:
        nc, self._nc = self._nc, None
        if nc is not None:
            await nc.drain()
        for task in list(self._tasks):
            task.cancel()

    async def _handle(self, msg: Any) -> None:
        if not reply_allowed(msg.reply):
            # Nothing done, nothing answered: the reply subject is the sender's.
            logger.warning(
                f"Broker control: dropped {msg.subject} asking for a reply on "
                f"{msg.reply!r}"
            )
            return
        # Each request on its own: a slow stream creation holds up no other.
        task = asyncio.create_task(self._serve(msg))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _serve(self, msg: Any) -> None:
        from naas_abi_sdk.messages import reply

        operation = msg.subject.rsplit(".", 1)[-1]
        raw = operation in RAW_OPERATIONS
        try:
            result = await self.handle(operation, msg.headers or {}, msg.data)
            error: dict[str, str] | None = None
        except Refused as exc:
            result, error = {}, {"code": exc.code, "message": str(exc)}
        except InvalidServiceTokenError as exc:
            result, error = {}, {"code": "UNAUTHENTICATED", "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 - answered, and logged
            logger.warning(f"Broker control {operation} failed: {exc!r}")
            result, error = {}, {"code": "INTERNAL", "message": "could not do it"}
        if raw:
            if error is None:
                # Bounded by construction: a chunk is stored at most the broker
                # limit less 1 KiB.
                await reply(msg, result["data"], headers={STATUS_HEADER: "ok"})
            else:
                await reply(msg, b"", headers={ERROR_HEADER: json.dumps(error)})
            return
        answer = {"error": error} if error is not None else {"ok": True, **result}
        # Bounded by construction: a code, a short message, a few numbers.
        await reply(msg, json.dumps(answer).encode())

    async def handle(self, operation: str, headers: Any, data: bytes) -> dict[str, Any]:
        """Do ``operation`` for the verified caller (what it answers, besides
        ``ok``); ``Refused`` otherwise."""
        context = caller_context(headers, self.verifier)
        caller = context.principal
        try:
            fields = json.loads(data or b"{}")
        except ValueError:
            raise Refused("INVALID_ARGUMENT", "the request is not JSON") from None
        if not isinstance(fields, dict):
            raise Refused("INVALID_ARGUMENT", "the request is not a JSON object")
        if operation == "verify_trigger":
            return await self._verify(fields)
        trusted = caller.kind == "service_account" and caller.name in TRUSTED
        request = _Request(
            self, caller, None if trusted else await self._grants_of(caller)
        )
        # The verified credentials the job's host authorizes a trigger or a
        # cancel with (discovery:TriggerJob, CancelJobRun), as of when stored.
        request.credentials = {AUTH_HEADER: headers.get(AUTH_HEADER, "")}
        if context.on_behalf_of is not None:
            request.credentials[ON_BEHALF_OF_HEADER] = headers.get(
                ON_BEHALF_OF_HEADER, ""
            )
        js = self._nc.jetstream()
        if operation in ("ensure_topic", "ensure_queue"):
            await self._queue(js, operation, fields, request)
        elif operation in ("ensure_job", "set_schedules"):
            await self._job(js, operation, fields, request)
        elif operation == "trigger":
            return await self._trigger(js, fields, request)
        elif operation == "cancel":
            await self._cancel(fields, request)
        elif operation == "ensure_claim_checks":
            from naas_abi_sdk import claim_check

            if request.grants is not None and not request.grants.claim_checks:
                raise Refused("PERMISSION_DENIED", "no claim checks are granted")
            await claim_check.ensure_stream(self._nc)
        elif operation == "read_claim_check":
            return await self._read_claim_check(js, fields, request)
        else:
            raise Refused("NOT_FOUND", f"unknown operation {operation!r}")
        return {}

    async def _grants_of(self, caller: Principal) -> broker.BrokerPermissions:
        """The caller's grants, computed again whenever the store changed."""
        revision = await asyncio.to_thread(self.iam.store.revision)
        cached = self._grants.get(caller.id)
        if cached is not None and cached[0] == revision:
            return cached[1]
        try:
            grants = await asyncio.to_thread(self.iam.broker_grants, caller.id)
        except IAMError as exc:
            raise Refused("PERMISSION_DENIED", str(exc)) from None
        if len(self._grants) > 4096:
            self._grants.clear()
        self._grants[caller.id] = (revision, grants)
        return grants

    async def allowed(self, caller: Principal, action: str, resource: str) -> bool:
        """IAM's decision for ``caller`` on one concrete resource."""

        def decide() -> bool:
            with use_call_context(CallContext(principal=caller)):
                return self.iam.authorize(action, resource).allowed

        return await asyncio.to_thread(decide)

    # --- jobs --------------------------------------------------------------------------

    def _seal(self, subject: str, kind: str, body: bytes, headers: dict) -> str:
        from naas_abi_sdk.jobs import seal_fields

        return self.iam.seal_trigger(seal_fields(subject, kind, body, headers))

    async def _verify(self, fields: dict) -> dict[str, Any]:
        sealed, seal = fields.get("fields"), fields.get("seal")
        if not isinstance(sealed, list) or not isinstance(seal, str):
            raise Refused("INVALID_ARGUMENT", "fields is a list and seal a string")
        valid = await asyncio.to_thread(self.iam.trigger_sealed, sealed, seal)
        return {"valid": valid}

    async def _trigger(
        self, js: Any, fields: dict, request: _Request
    ) -> dict[str, Any]:
        from naas_abi_sdk import claim_check
        from naas_abi_sdk.job_host import ensure_stream
        from naas_abi_sdk.jobs import (
            SEAL_HEADER,
            TRIGGER_HEADER,
            TRIGGER_SENDER_HEADERS,
            TRIGGER_TTLS,
            job_subjects,
            stream_name,
        )
        from nats.js.errors import NoStreamResponseError

        project, module_id, job = _job_names(fields)
        subjects = job_subjects(project, module_id, job)
        await request.require(
            "discovery:TriggerJob",
            _job_resource(project, module_id, job),
            granted=lambda g: g.may_trigger(subjects.trigger),
        )
        own = parse_account(request.caller.name or "") == (project, module_id)
        wanted = fields.get("kind")
        kind = "event" if wanted == "event" and (own or request.trusted) else "manual"
        try:
            body = base64.b64decode(str(fields.get("body", "")), validate=True)
        except (binascii.Error, ValueError):
            raise Refused("INVALID_ARGUMENT", "body is base64") from None
        headers = _sender_headers(fields.get("headers"), TRIGGER_SENDER_HEADERS)
        scope = (
            f"{claim_check.SUBJECT_PREFIX}."
            f"{claim_check.job_scope(project, subjects.module_hash)}."
        )
        reference = headers.get(claim_check.HEADER)
        if reference is not None and not reference.startswith(scope):
            raise Refused("INVALID_ARGUMENT", "the claim check is not this job's")
        if "Nats-Msg-Id" in headers:
            # JetStream dedups across the whole jobs stream: the id is the
            # caller's, for this job, so no one can make another's a duplicate.
            headers["Nats-Msg-Id"] = hashlib.sha256(
                json.dumps(
                    [request.caller.id, subjects.trigger, headers["Nats-Msg-Id"]]
                ).encode()
            ).hexdigest()
        headers.update(request.credentials)
        headers.update({TRIGGER_HEADER: kind, "Nats-TTL": TRIGGER_TTLS[kind]})
        headers[SEAL_HEADER] = self._seal(subjects.trigger, kind, body, headers)
        stream = stream_name(project)
        # Above the limit the server would close this connection: refused.
        reserve = claim_check.stream_header_reserve(stream)
        if message_size(body, headers) + reserve > self._nc.max_payload:
            raise Refused("PAYLOAD_TOO_LARGE", "send the body as a claim check")
        try:
            ack = await js.publish(
                subjects.trigger, body, headers=headers, stream=stream
            )
        except NoStreamResponseError:
            await ensure_stream(js, project)  # no host started yet
            ack = await js.publish(
                subjects.trigger, body, headers=headers, stream=stream
            )
        return {"seq": ack.seq, "duplicate": bool(ack.duplicate)}

    async def _cancel(self, fields: dict, request: _Request) -> None:
        from naas_abi_sdk.jobs import SEAL_HEADER, job_subjects

        project, module_id, job = _job_names(fields)
        run_id = _text(fields, "run_id")
        subject = job_subjects(project, module_id, job).cancel
        await request.require(
            "discovery:CancelJobRun",
            resource_name(
                "discovery", "job_run", [project, module_id, run_id], kind="path"
            ),
            granted=lambda g: g.may_cancel(subject),
        )
        body = run_id.encode()
        await self._nc.publish(
            subject,
            body,
            headers={
                **request.credentials,
                SEAL_HEADER: self._seal(subject, "cancel", body, {}),
            },
        )

    async def _job(
        self, js: Any, operation: str, fields: dict, request: _Request
    ) -> None:
        from naas_abi_sdk.job_host import (
            SCHEDULE_FIELDS,
            consumer_config,
            ensure_consumer,
            ensure_stream,
            set_schedules,
        )
        from naas_abi_sdk.jobs import MAX_TRIGGERS, job_subjects

        account = parse_account(request.caller.name or "")
        if request.grants is None or account is None:
            raise Refused("PERMISSION_DENIED", "only a module hosts jobs here")
        project, job = _text(fields, "project"), _text(fields, "job")
        module_id = account[1]
        await request.require(
            "discovery:ScheduleJob"
            if operation == "set_schedules"
            else "discovery:ListJobs",
            _job_resource(project, module_id, job),
            granted=lambda g: (project, job) in g.hosted_jobs,
        )
        if operation == "set_schedules":
            schedules = fields.get("schedules")
            if not isinstance(schedules, list) or len(schedules) > MAX_TRIGGERS:
                raise Refused(
                    "INVALID_ARGUMENT", f"schedules is a list of {MAX_TRIGGERS} at most"
                )
            for schedule in schedules:
                if (
                    not isinstance(schedule, dict)
                    or not schedule.get("Nats-Schedule")
                    or set(schedule) - set(SCHEDULE_FIELDS)
                    or any(
                        not isinstance(v, str)
                        or len(v) > 128
                        or any(c in v for c in "\r\n")
                        for v in schedule.values()
                    )
                ):
                    raise Refused(
                        "INVALID_ARGUMENT", f"a schedule has {SCHEDULE_FIELDS} only"
                    )
            # A fired schedule copies its headers onto the trigger: seal it so.
            trigger = job_subjects(project, module_id, job).trigger
            seal = self._seal(trigger, "schedule", b"{}", {})
            await ensure_stream(js, project)
            await set_schedules(js, project, module_id, job, schedules, seal=seal)
            return
        concurrency = fields.get("max_concurrency")
        ack_wait = fields.get("ack_wait_seconds")
        if not isinstance(concurrency, int) or not 0 < concurrency <= 64:
            raise Refused("INVALID_ARGUMENT", "max_concurrency is 1 to 64")
        if (
            not isinstance(ack_wait, int | float)
            or not math.isfinite(ack_wait)
            or not 0 < ack_wait <= MAX_ACK_WAIT_SECONDS
        ):
            raise Refused("INVALID_ARGUMENT", "ack_wait_seconds is 0 to 3600")
        await ensure_stream(js, project)
        config = consumer_config(
            project,
            module_id,
            job,
            max_concurrency=concurrency,
            ack_wait_seconds=float(ack_wait),
        )
        await ensure_consumer(js, config, project, update=bool(fields.get("update")))

    # --- bus and claim checks ------------------------------------------------------------

    async def _queue(
        self, js: Any, operation: str, fields: dict, request: _Request
    ) -> None:
        from naas_abi_sdk.bus import BusClient, ensure_queue, ensure_topic_stream

        topic = _text(fields, "topic")
        problem = broker.topic_problem(topic)
        if problem is not None:
            raise Refused("INVALID_ARGUMENT", problem)
        await request.require(
            "bus:Publish" if operation == "ensure_topic" else "bus:Consume",
            resource_name("bus", "topic", topic),
            granted=lambda g: (
                topic
                in (g.bus_publish if operation == "ensure_topic" else g.bus_consume)
            ),
        )
        if operation == "ensure_topic":
            await ensure_topic_stream(js, topic)
            return
        routing_key = _text(fields, "routing_key")
        try:
            BusClient.subject(topic, routing_key)
        except ValueError as exc:
            raise Refused("INVALID_ARGUMENT", str(exc)) from None
        await ensure_queue(js, topic, routing_key)

    async def _read_claim_check(
        self, js: Any, fields: dict, request: _Request
    ) -> dict[str, Any]:
        from naas_abi_sdk import claim_check
        from nats.errors import NoRespondersError
        from nats.js.errors import NotFoundError

        reference = _text(fields, "reference")
        index = fields.get("index")
        tokens = reference.split(".")
        if (
            not reference.startswith(f"{claim_check.SUBJECT_PREFIX}.")
            or any(not t or t in ("*", ">") for t in tokens)
            or not isinstance(index, int)
            or not 0 <= index < claim_check.MAX_VALUE_BYTES // 1024
        ):
            raise Refused(
                "INVALID_ARGUMENT", "a claim check reference and a chunk index"
            )
        await self._may_read(tokens[2:], request)
        try:
            stored = await js.get_msg(
                claim_check.STREAM, subject=f"{reference}.{index}", direct=True
            )
        except (NotFoundError, NoRespondersError):  # no stream yet, or gone
            raise Refused("NOT_FOUND", "the stored payload expired") from None
        return {"data": stored.data or b""}

    async def _may_read(self, scope: list[str], request: _Request) -> None:
        """A topic's claim checks to whoever may consume it; a job's triggers'
        to its own module."""
        from naas_abi_sdk import claim_check

        if request.trusted:
            return
        grants = request.grants
        assert grants is not None
        if len(scope) >= 3 and scope[0] == "t":
            for topic in grants.bus_consume:
                if claim_check.topic_scope(
                    topic
                ) == f"t.{scope[1]}" and await self.allowed(
                    request.caller, "bus:Consume", resource_name("bus", "topic", topic)
                ):
                    return
        elif len(scope) >= 4 and scope[0] == "j":
            account = parse_account(request.caller.name or "")
            project, module_hash = scope[1], scope[2]
            if (
                account is not None
                and account[0] == project
                and broker.module_hash(account[1]) == module_hash
                and grants.hosted_jobs
            ):
                return
        raise Refused(
            "PERMISSION_DENIED", "this claim check is not one the caller reads"
        )


class _Request:
    """A verified caller and its grants (None: ``engine`` or ``api``)."""

    def __init__(
        self,
        control: BrokerControl,
        caller: Principal,
        grants: broker.BrokerPermissions | None,
    ) -> None:
        self.control, self.caller, self.grants = control, caller, grants
        self.credentials: dict[str, str] = {}

    @property
    def trusted(self) -> bool:
        return self.grants is None

    async def require(self, action: str, resource: str, *, granted: Any) -> None:
        """Within the module's broker grants, and allowed by IAM on this very
        resource (a Deny on one job or topic counts)."""
        if self.trusted:
            return
        if not granted(self.grants) or not await self.control.allowed(
            self.caller, action, resource
        ):
            raise Refused("PERMISSION_DENIED", f"{action} on {resource} is not allowed")


def _job_resource(project: str, module_id: str, job: str) -> str:
    return resource_name("discovery", "job", [project, module_id, job], kind="path")


def _job_names(fields: dict) -> tuple[str, str, str]:
    return _text(fields, "project"), _text(fields, "module_id"), _text(fields, "job")


def _sender_headers(sent: Any, allowed: tuple[str, ...]) -> dict[str, str]:
    if sent is None:
        return {}
    if not isinstance(sent, dict):
        raise Refused("INVALID_ARGUMENT", "headers is an object")
    headers: dict[str, str] = {}
    for key, value in sent.items():
        if key not in allowed:
            continue
        if (
            not isinstance(value, str)
            or len(value) > 512
            or any(c in value for c in "\r\n")
        ):
            raise Refused("INVALID_ARGUMENT", f"header {key} is a short line")
        headers[key] = value
    return headers


def _text(fields: dict, key: str) -> str:
    value = fields.get(key)
    if not isinstance(value, str) or not value or len(value) > 255:
        raise Refused("INVALID_ARGUMENT", f"{key} is a nonempty string")
    return value
