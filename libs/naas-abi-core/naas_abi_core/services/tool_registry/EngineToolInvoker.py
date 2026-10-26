"""Runs a tool the engine holds, for a caller in another process.

The tool, its configuration and the secrets it reads stay in the engine: a caller
sends a tool reference, JSON arguments, plain configuration values and the *names*
of secrets, and gets JSON back (docs/adr/20261023_remote-callers-run-engine-tools.md).
What the caller may do is decided here from an ``InvokeCaller`` the transport built
out of the verified service identity, never from the request. A call goes through,
in this order:

1. size limits, and who may name an end user (only the engine's own processes);
2. the tool: a reference the caller cannot discover is not found; a tool a module
   serves is refused (the caller reaches the module itself); a tool that needs no
   scope runs only for a caller the operator granted it to; then the registry's
   access policy for ``EXECUTE``;
3. the arguments against the tool's input schema, the configuration against its
   definition (declared keys only, no credential written inline), and the secret
   references against the caller's allow list;
4. admission (a bounded number of calls at once, held until the tool returns, so a
   tool that overruns its deadline keeps its slot) and then, on a worker thread under
   a deadline, everything from 2 on: the registry lookup (its lock is held while it
   syncs), the schema checks, the secrets' resolution, ``registry.resolve`` and the
   call. Only the checks of 1 run on the shared event loop, which serves every
   other service of the connection.

A call may carry a ``call_id``: the caller that gives up (or whose deadline passes)
asks the engine to cancel it (``cancel``), as the same identity, and the tool is
stopped on this side: one with a coroutine is cancelled at its next ``await`` (its
``finally`` blocks run), a synchronous one is told through
``naas_abi_sdk.cancellation.current_cancellation()`` and cannot be interrupted (its
thread, and so its slot, last until it returns). The deadline stops the tool the same
way. The caller is answered ``CANCELLED``.

The result and any message of the tool are scrubbed of the values of the secrets the
call used (a defence in depth: a tool should not echo a credential, but one that does
must not hand it to another process). Only a ``ToolException``'s message, written
for the caller, is returned from a failing tool; any other failure is logged by type
and reported as ``TOOL_ERROR`` without detail.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import math
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool, ToolException
from naas_abi_sdk.cancellation import (
    ActiveCalls,
    CallIdInUse,
    ToolCancellation,
    ToolCancelled,
    bind_cancellation,
    valid_call_id,
)
from naas_abi_sdk.tools import (
    DEFAULT_DEADLINE_SECONDS,
    MAX_ARGUMENTS_BYTES,
    MAX_CONFIG_BYTES,
    MAX_DEADLINE_SECONDS,
    MAX_ERROR_CHARACTERS,
    MAX_RESULT_BYTES,
    MAX_SECRET_NAME_CHARS,
    MAX_SECRET_REFS,
    SECRET_NAME,
)
from pydantic import ValidationError

from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.agent_composer.AgentComposerPort import ISecretResolverPort
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    InvalidToolReferenceError,
    ToolAccessDeniedError,
    ToolAction,
    ToolConfigurationError,
    ToolContext,
    ToolDefinition,
    ToolNotFoundError,
    ToolRef,
    ToolRegistryError,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from naas_abi_core.utils.Logger import logger

# The limits of the call are the contract's, declared once in ``naas_abi_sdk.tools``.
DEFAULT_TIMEOUT_SECONDS = DEFAULT_DEADLINE_SECONDS
MAX_TIMEOUT_SECONDS = MAX_DEADLINE_SECONDS
DEFAULT_MAX_CONCURRENT = 16
# Shorter values are not worth hiding, and would mangle everything they match.
MIN_SCRUBBED_LENGTH = 4
REDACTED = "[redacted]"

# Validators kept ready (one per published input schema): checking a schema is
# not free, and a call should not pay for it again.
MAX_CACHED_VALIDATORS = 256
# How long a cancelled coroutine tool may take to unwind before the caller is answered.
CANCEL_GRACE_SECONDS = 5.0

_SECRET_NAME = re.compile(SECRET_NAME)
ACTIVITY_ACTOR_PREFIX = "service:"


class ToolInvokeError(Exception):
    """A refusal or failure with a stable code and a message safe to return."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class InvokeCaller:
    """What a verified identity may do. Built by the transport from configuration.

    ``secrets``: the engine secret names it may reference (``None``: any, for the
    engine's own processes). ``unscoped_tools``: patterns (``fnmatch``, on
    ``<namespace>/<name>``) of tools it may run although they need no scope
    (``None``: all). ``may_name_user``: it speaks for an end user (api, engine).
    """

    identity: str
    scopes: frozenset[str] = frozenset()
    secrets: frozenset[str] | None = frozenset()
    unscoped_tools: tuple[str, ...] | None = ()
    may_name_user: bool = False


@dataclass(frozen=True)
class ToolInvocation:
    """One call, decoded from the transport message."""

    tool: str
    version: str = ""
    arguments: bytes = b""
    config: bytes = b""
    secret_refs: Mapping[str, str] = field(default_factory=dict)
    user_id: str = ""
    workspace_id: str = ""
    timeout_ms: int = 0
    trace_id: str = ""
    call_id: str = ""


def _json_object(raw: bytes, what: str, limit: int) -> dict[str, Any]:
    if len(raw) > limit:
        raise ToolInvokeError(
            "PAYLOAD_TOO_LARGE", f"Tool {what} exceed {limit // 1024} KiB"
        )
    if not raw:
        return {}

    def refuse(constant: str) -> None:
        raise ValueError(constant)

    try:
        value = json.loads(raw, parse_constant=refuse)
    except (ValueError, RecursionError) as exc:
        raise ToolInvokeError("INVALID_ARGUMENT", f"Tool {what} are not JSON") from exc
    if not isinstance(value, dict):
        raise ToolInvokeError("INVALID_ARGUMENT", f"Tool {what} are a JSON object")
    return value


def scrub(value: Any, secrets: list[str]) -> Any:
    """``value`` as JSON data with every secret replaced by ``[redacted]``.

    Raises ``TypeError`` for what JSON cannot carry (bytes, objects, ...)."""
    hidden = sorted(
        {s for s in secrets if len(s) >= MIN_SCRUBBED_LENGTH}, key=len, reverse=True
    )

    def text(item: str) -> str:
        for secret in hidden:
            item = item.replace(secret, REDACTED)
        return item

    def walk(item: Any) -> Any:
        if item is None or isinstance(item, (bool, int)):
            return item
        if isinstance(item, float):
            if not math.isfinite(item):
                raise TypeError("Not a JSON number")
            return item
        if isinstance(item, str):
            return text(item)
        if isinstance(item, Mapping):
            result = {}
            for key, member in item.items():
                if not isinstance(key, str):
                    raise TypeError("A JSON object has string keys")
                result[text(key)] = walk(member)
            return result
        if isinstance(item, (list, tuple)):
            return [walk(member) for member in item]
        raise TypeError(f"{type(item).__name__} is not JSON")

    return walk(value)


class _Running:
    """The slot of one call: held until its task and its threads have all ended."""

    def __init__(self, release: Callable[[], None]) -> None:
        self._held = 1  # the task
        self._release = release

    def hold(self) -> None:
        self._held += 1

    def release(self, _done: Any = None) -> None:
        self._held -= 1
        if self._held == 0:
            self._release()


def _has_coroutine(tool: BaseTool) -> bool:
    """A tool the loop can run and cancel: one with a coroutine of its own."""
    if isinstance(tool, StructuredTool):
        return tool.coroutine is not None
    return type(tool)._arun is not BaseTool._arun


class EngineToolInvoker:
    def __init__(
        self,
        registry: ToolRegistryService,
        secrets: ISecretResolverPort | None = None,
        *,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        default_timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_timeout: float = MAX_TIMEOUT_SECONDS,
        record_activity: Callable[[ActivityEvent], None] | None = None,
    ) -> None:
        if max_concurrent < 1:
            raise ValueError("At least one call must run at once")
        self._registry = registry
        self._secrets = secrets
        self._max_concurrent = max_concurrent
        # A default above the cap would let a call without a deadline outlast the rest.
        self._default_timeout = min(default_timeout, max_timeout)
        self._max_timeout = max_timeout
        self._record_activity = record_activity
        self._in_flight = 0
        self._pool: ThreadPoolExecutor | None = None
        # tool id -> (the schema object it was built from, its validator). A
        # republished tool has a new schema object, so the entry is rebuilt.
        self._validators: OrderedDict[str, tuple[dict[str, Any], Any]] = OrderedDict()
        self._validators_lock = threading.Lock()
        # Calls with a call_id, by (identity, id): the loop's own, like everything here.
        self._active = ActiveCalls()

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)

    def cancel(self, identity: str, call_id: str) -> bool:
        """Stop the call ``call_id`` that ``identity`` started: ``True`` when it was
        running. Another identity's call, an unknown id and a finished call are all
        ``False`` (a cancel that comes before its call is kept briefly). Call it on
        the event loop."""
        if not valid_call_id(call_id):
            return False
        return self._active.cancel(identity, call_id)

    # ------------------------------------------------------------------ entry
    async def invoke(self, caller: InvokeCaller, invocation: ToolInvocation) -> bytes:
        """The tool's JSON result. Raises ``ToolInvokeError``; nothing else escapes."""
        started = time.monotonic()
        try:
            result = await self._invoke(caller, invocation)
        except ToolInvokeError as exc:
            await self._report(caller, invocation, started, exc.code)
            raise
        except Exception as exc:  # noqa: BLE001 - nothing of it leaves the engine
            logger.warning(f"tool_registry invoke failed: {type(exc).__name__}")
            await self._report(caller, invocation, started, "INTERNAL")
            raise ToolInvokeError("INTERNAL", "internal error") from None
        await self._report(caller, invocation, started, None)
        return result

    async def _report(
        self,
        caller: InvokeCaller,
        invocation: ToolInvocation,
        started: float,
        code: str | None,
    ) -> None:
        # Arguments, configuration, secret names and values are never recorded.
        millis = int((time.monotonic() - started) * 1000)
        tool = invocation.tool[:200]
        logger.info(
            f"tool_registry invoke {tool!r} by {caller.identity!r}: "
            f"{'ok' if code is None else code} in {millis}ms"
        )
        if self._record_activity is None:
            return
        attributes: dict[str, Any] = {
            "tool": tool,
            "outcome": (
                "ok"
                if code is None
                else "cancelled"
                if code == "CANCELLED"
                else "error"
            ),
            "duration_ms": millis,
        }
        if code is not None:
            attributes["code"] = code
        if invocation.user_id:
            attributes["user_id"] = invocation.user_id[:200]
        if invocation.workspace_id:
            attributes["workspace_id"] = invocation.workspace_id[:200]
        event = ActivityEvent(
            actor_id=f"{ACTIVITY_ACTOR_PREFIX}{caller.identity}",
            event_type="tool_registry.invoke",
            correlation_id=invocation.trace_id or None,
            attributes=attributes,
        )
        try:
            await asyncio.get_running_loop().run_in_executor(
                None, self._record_activity, event
            )
        except Exception as exc:  # noqa: BLE001 - recording never fails a call
            logger.warning(f"tool_registry invoke activity: {type(exc).__name__}")

    # ----------------------------------------------------------------- checks
    async def _invoke(self, caller: InvokeCaller, invocation: ToolInvocation) -> bytes:
        if len(invocation.secret_refs) > MAX_SECRET_REFS:
            raise ToolInvokeError(
                "INVALID_ARGUMENT", f"At most {MAX_SECRET_REFS} secret references"
            )
        if len(invocation.arguments) > MAX_ARGUMENTS_BYTES:
            raise ToolInvokeError(
                "PAYLOAD_TOO_LARGE",
                f"Tool arguments exceed {MAX_ARGUMENTS_BYTES // 1024} KiB",
            )
        if len(invocation.config) > MAX_CONFIG_BYTES:
            raise ToolInvokeError(
                "PAYLOAD_TOO_LARGE",
                f"Tool configuration exceeds {MAX_CONFIG_BYTES // 1024} KiB",
            )
        if invocation.call_id and not valid_call_id(invocation.call_id):
            raise ToolInvokeError(
                "INVALID_ARGUMENT", "call_id is 1..128 letters, digits, _ or -"
            )
        if (invocation.user_id or invocation.workspace_id) and not caller.may_name_user:
            # Only the engine's own processes authenticate users and workspaces.
            raise ToolInvokeError(
                "PERMISSION_DENIED", "This caller cannot act for a user or workspace"
            )
        seconds = (
            min(invocation.timeout_ms / 1000, self._max_timeout)
            if invocation.timeout_ms > 0
            else self._default_timeout
        )
        return await self._run(caller, invocation, seconds)

    def _prepare(
        self, caller: InvokeCaller, invocation: ToolInvocation
    ) -> tuple[
        ToolDefinition, ToolContext, dict[str, Any], dict[str, Any], dict[str, str]
    ]:
        """On a worker thread: what the call needs, or the refusal."""
        ref = self._reference(invocation)
        context = ToolContext(
            user_id=invocation.user_id or None,
            workspace_id=invocation.workspace_id or None,
            scopes=caller.scopes,
        )
        definition = self._definition(caller, ref, context)
        arguments = _json_object(invocation.arguments, "arguments", MAX_ARGUMENTS_BYTES)
        self._validate(definition, arguments)
        literal = self._configuration(definition, invocation)
        references = self._references(caller, definition, invocation)
        return definition, context, arguments, literal, references

    @staticmethod
    def _reference(invocation: ToolInvocation) -> ToolRef:
        try:
            ref = ToolRef.parse(invocation.tool) if invocation.tool else None
            if ref is None:
                raise InvalidToolReferenceError("A tool reference is required")
            if invocation.version:
                if ref.version not in (None, invocation.version):
                    raise InvalidToolReferenceError(
                        "The reference and the version name different versions"
                    )
                ref = ToolRef.parse(f"{ref.namespace}/{ref.name}@{invocation.version}")
        except InvalidToolReferenceError as exc:
            raise ToolInvokeError("INVALID_ARGUMENT", str(exc)[:300]) from exc
        return ref

    def _definition(
        self, caller: InvokeCaller, ref: ToolRef, context: ToolContext
    ) -> ToolDefinition:
        try:
            # A tool the caller may not discover is a tool that does not exist.
            definition = self._registry.get_local(ref, context).definition
        except ToolNotFoundError:
            raise ToolInvokeError("TOOL_NOT_FOUND", "No visible tool matches") from None
        if definition.remote:
            raise ToolInvokeError(
                "PERMISSION_DENIED",
                "This tool is served by a module: call the module itself",
            )
        if (
            not definition.required_scopes
            and caller.unscoped_tools is not None
            and not any(
                fnmatchcase(f"{definition.namespace}/{definition.name}", pattern)
                for pattern in caller.unscoped_tools
            )
        ):
            raise ToolInvokeError(
                "PERMISSION_DENIED",
                "This tool needs no scope and is not granted to this caller",
            )
        try:
            self._registry.check_access(definition.id, context, ToolAction.EXECUTE)
        except ToolAccessDeniedError:
            raise ToolInvokeError(
                "PERMISSION_DENIED", "Caller may not run this tool"
            ) from None
        except ToolNotFoundError:
            raise ToolInvokeError("TOOL_NOT_FOUND", "No visible tool matches") from None
        return definition

    def _validator(self, definition: ToolDefinition) -> Any:
        schema = definition.input_schema
        key = str(definition.id)
        with self._validators_lock:
            cached = self._validators.get(key)
            if cached is not None and cached[0] is schema:
                self._validators.move_to_end(key)
                return cached[1]
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError:
            logger.warning(f"Tool '{definition.id}' declares an invalid input schema")
            raise ToolInvokeError(
                "TOOL_ERROR", "The tool's input schema is invalid"
            ) from None
        validator = Draft202012Validator(schema)
        with self._validators_lock:
            self._validators[key] = (schema, validator)
            self._validators.move_to_end(key)
            while len(self._validators) > MAX_CACHED_VALIDATORS:
                self._validators.popitem(last=False)
        return validator

    def _validate(self, definition: ToolDefinition, arguments: dict[str, Any]) -> None:
        errors = sorted(self._validator(definition).iter_errors(arguments), key=str)
        if errors:
            where = "/".join(str(part) for part in errors[0].absolute_path)
            raise ToolInvokeError(
                "INVALID_ARGUMENT",
                f"{where or 'arguments'}: {errors[0].message}"[:200],
            )

    @staticmethod
    def _configuration(
        definition: ToolDefinition, invocation: ToolInvocation
    ) -> dict[str, Any]:
        config = _json_object(invocation.config, "configuration", MAX_CONFIG_BYTES)
        declared = {r.key: r for r in definition.requirements.config}
        unknown = sorted(set(config) - set(declared))
        if unknown:
            raise ToolInvokeError(
                "INVALID_ARGUMENT", f"Unknown configuration: {unknown}"[:200]
            )
        for key, value in config.items():
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise ToolInvokeError(
                    "INVALID_ARGUMENT", f"Configuration '{key}' is a plain value"
                )
            if declared[key].secret and value not in (None, ""):
                raise ToolInvokeError(
                    "PERMISSION_DENIED",
                    f"'{key}' is a credential: reference an engine secret by name "
                    "(secret_refs) instead of sending its value",
                )
        return config

    def _references(
        self,
        caller: InvokeCaller,
        definition: ToolDefinition,
        invocation: ToolInvocation,
    ) -> dict[str, str]:
        declared = {r.key: r for r in definition.requirements.config}
        references: dict[str, str] = {}
        for key, name in invocation.secret_refs.items():
            if key not in declared or not declared[key].secret:
                raise ToolInvokeError(
                    "INVALID_ARGUMENT",
                    f"'{key[:64]}' is not a credential of this tool: a secret "
                    "goes only to a configuration key the tool marks secret",
                )
            # (A value for a key marked secret was already refused in _configuration.)
            if (
                not name
                or len(name) > MAX_SECRET_NAME_CHARS
                or not _SECRET_NAME.fullmatch(name)
            ):
                raise ToolInvokeError(
                    "INVALID_ARGUMENT", "A secret reference is an engine secret's name"
                )
            if caller.secrets is not None and name not in caller.secrets:
                # Decided before any lookup: no secret's existence is revealed.
                raise ToolInvokeError(
                    "PERMISSION_DENIED", f"Caller may not use secret '{name}'"
                )
            references[key] = name
        return references

    # -------------------------------------------------------------- execution
    async def _run(
        self, caller: InvokeCaller, invocation: ToolInvocation, seconds: float
    ) -> bytes:
        if self._in_flight >= self._max_concurrent:
            raise ToolInvokeError(
                "RESOURCE_EXHAUSTED",
                "The engine is running as many tool calls as it accepts: retry later",
                retryable=True,
            )
        registration = None
        if invocation.call_id:
            try:
                registration = self._active.register(
                    caller.identity, invocation.call_id
                )
            except CallIdInUse:
                raise ToolInvokeError(
                    "INVALID_ARGUMENT", "A call with this call_id is already running"
                ) from None
        if self._pool is None:
            self._pool = ThreadPoolExecutor(
                max_workers=self._max_concurrent, thread_name_prefix="nats-tool-invoke"
            )
        self._in_flight += 1
        cancellation = ToolCancellation()
        running = _Running(self._release)
        # The call is a task of its own, so that its deadline, a cancel from its caller
        # and the caller going away can each stop it. It holds its slot until the task
        # and every thread it started have ended: a synchronous tool that ignores the
        # cancellation keeps running, and keeps its slot.
        task = asyncio.ensure_future(
            self._pipeline(caller, invocation, cancellation, running)
        )
        task.add_done_callback(lambda done: running.release(done))
        if registration is not None:
            registration.on_cancel(lambda: self._stop(task, cancellation))
        try:
            return await asyncio.wait_for(asyncio.shield(task), seconds)
        except asyncio.TimeoutError:  # noqa: UP041 - not the builtin one on Python 3.10
            self._stop(task, cancellation)
            await self._unwound(task)
            raise ToolInvokeError(
                "DEADLINE_EXCEEDED", f"Tool exceeded its {seconds:g}s deadline"
            ) from None
        except asyncio.CancelledError:
            # Its caller cancelled it (the task is cancelled), or this call is being
            # cancelled (the connection or the engine closes): stop the tool either way.
            self._stop(task, cancellation)
            if registration is not None and registration.cancelled:
                await self._unwound(task)
                raise ToolInvokeError("CANCELLED", "The call was cancelled") from None
            raise
        finally:
            if registration is not None:
                registration.release()

    def _release(self) -> None:
        self._in_flight -= 1

    @staticmethod
    def _stop(task: asyncio.Future[Any], cancellation: ToolCancellation) -> None:
        cancellation.cancel()
        task.cancel()

    @staticmethod
    async def _unwound(task: asyncio.Future[Any]) -> None:
        """Let a cancelled coroutine tool run its ``finally`` blocks before answering."""
        await asyncio.wait({task}, timeout=CANCEL_GRACE_SECONDS)
        if task.done() and not task.cancelled():
            task.exception()  # retrieved: never "exception was never retrieved"

    async def _pipeline(
        self,
        caller: InvokeCaller,
        invocation: ToolInvocation,
        cancellation: ToolCancellation,
        running: _Running,
    ) -> bytes:
        # The task's own context: a tool, on this loop or on a thread (which runs in a
        # copy of it), reads its cancellation with ``current_cancellation()``.
        bind_cancellation(cancellation)
        context = contextvars.copy_context()
        definition, tool, arguments, hidden = await self._in_thread(
            running, context, self._prepare_and_build, caller, invocation
        )
        if _has_coroutine(tool):
            try:
                result = await tool.ainvoke(arguments)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - translated, never returned raw
                raise self._failure(definition, exc, hidden) from None
            return await self._in_thread(running, context, self._encode, result, hidden)
        return await self._in_thread(
            running, context, self._call_tool, definition, tool, arguments, hidden
        )

    async def _in_thread(
        self, running: _Running, context: contextvars.Context, fn: Any, *args: Any
    ) -> Any:
        assert self._pool is not None
        loop = asyncio.get_running_loop()
        running.hold()
        future = self._pool.submit(context.run, fn, *args)

        def finished(done: Any) -> None:
            if not done.cancelled():
                done.exception()  # retrieved: a stopped call never reads it
            try:
                loop.call_soon_threadsafe(running.release)
            except RuntimeError:  # the loop closed while the thread ran on
                pass

        future.add_done_callback(finished)
        return await asyncio.wrap_future(future)

    def _prepare_and_build(
        self, caller: InvokeCaller, invocation: ToolInvocation
    ) -> tuple[ToolDefinition, Any, dict[str, Any], list[str]]:
        """On a worker thread: the checks, the secrets' resolution and the tool."""
        definition, context, arguments, literal, references = self._prepare(
            caller, invocation
        )
        tool, hidden = self._build(definition, context, literal, references)
        return definition, tool, arguments, hidden

    def _build(
        self,
        definition: ToolDefinition,
        context: ToolContext,
        literal: dict[str, Any],
        references: dict[str, str],
    ) -> tuple[Any, list[str]]:
        hidden: list[str] = []
        config = dict(literal)
        for key, name in references.items():
            value = self._secrets.resolve(name) if self._secrets is not None else None
            if value is None:
                raise ToolInvokeError("INVALID_ARGUMENT", f"Secret '{name}' is not set")
            config[key] = value
            hidden.append(value)
        try:
            hidden.extend(self._registry.credential_values(definition.id, config))
            tool = self._registry.resolve(
                definition.id, context, config, ToolAction.EXECUTE
            )
        except ToolConfigurationError as exc:
            raise ToolInvokeError(
                "INVALID_ARGUMENT", f"Missing configuration: {list(exc.missing)}"[:200]
            ) from None
        except ToolAccessDeniedError:
            raise ToolInvokeError(
                "PERMISSION_DENIED", "Caller may not run this tool"
            ) from None
        except ToolNotFoundError:
            raise ToolInvokeError("TOOL_NOT_FOUND", "No visible tool matches") from None
        except ToolRegistryError as exc:
            # A binding's message may hold the configuration it was built with.
            logger.warning(
                f"tool_registry invoke: '{definition.id}' could not be built: "
                f"{type(exc).__name__}"
            )
            raise ToolInvokeError("TOOL_ERROR", "The tool could not be built") from None
        if not isinstance(tool, BaseTool):
            raise ToolInvokeError("TOOL_ERROR", "The tool cannot be run remotely")
        return tool, hidden

    def _call_tool(
        self,
        definition: ToolDefinition,
        tool: BaseTool,
        arguments: dict[str, Any],
        hidden: list[str],
    ) -> bytes:
        """On a worker thread: run a synchronous tool."""
        try:
            result = tool.invoke(arguments)
        except Exception as exc:  # noqa: BLE001 - translated, never returned raw
            raise self._failure(definition, exc, hidden) from None
        return self._encode(result, hidden)

    @staticmethod
    def _failure(
        definition: ToolDefinition, exc: Exception, hidden: list[str]
    ) -> ToolInvokeError:
        """What a tool's failure is to its caller: only a ``ToolException``'s message
        (written for the caller) and the arguments' validation message, scrubbed."""
        if isinstance(exc, ToolCancelled):
            return ToolInvokeError("CANCELLED", "The call was cancelled")
        if isinstance(exc, ToolException):
            return ToolInvokeError(
                "TOOL_ERROR", scrub(str(exc), hidden)[:MAX_ERROR_CHARACTERS]
            )
        if isinstance(exc, ValidationError):
            first = exc.errors(include_input=False, include_url=False)[0]
            where = "/".join(str(part) for part in first.get("loc", ()))
            return ToolInvokeError(
                "INVALID_ARGUMENT",
                scrub(f"{where or 'arguments'}: {first.get('msg', 'invalid')}", hidden)[
                    :200
                ],
            )
        # Its message may hold a credential: log the type only.
        logger.warning(
            f"tool_registry invoke: '{definition.id}' failed: {type(exc).__name__}"
        )
        return ToolInvokeError("TOOL_ERROR", "Tool execution failed")

    @staticmethod
    def _encode(result: Any, hidden: list[str]) -> bytes:
        if isinstance(result, ToolMessage):
            result = result.content
        try:
            raw = json.dumps(scrub(result, hidden), allow_nan=False).encode()
        except (TypeError, ValueError, RecursionError):
            raise ToolInvokeError("TOOL_ERROR", "Tool result is not JSON") from None
        if len(raw) > MAX_RESULT_BYTES:
            raise ToolInvokeError(
                "PAYLOAD_TOO_LARGE",
                f"Tool result exceeds {MAX_RESULT_BYTES // 1024} KiB",
            )
        return raw
