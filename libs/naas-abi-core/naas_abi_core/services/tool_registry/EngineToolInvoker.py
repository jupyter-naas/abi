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
   a deadline, the secrets' resolution, ``registry.resolve`` and the call.

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
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, ToolException
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

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)

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
            "outcome": "ok" if code is None else "error",
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
        if (invocation.user_id or invocation.workspace_id) and not caller.may_name_user:
            # Only the engine's own processes authenticate users and workspaces.
            raise ToolInvokeError(
                "PERMISSION_DENIED", "This caller cannot act for a user or workspace"
            )
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
        seconds = (
            min(invocation.timeout_ms / 1000, self._max_timeout)
            if invocation.timeout_ms > 0
            else self._default_timeout
        )
        return await self._run(
            definition, context, arguments, literal, references, seconds
        )

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

    @staticmethod
    def _validate(definition: ToolDefinition, arguments: dict[str, Any]) -> None:
        try:
            Draft202012Validator.check_schema(definition.input_schema)
        except SchemaError:
            logger.warning(f"Tool '{definition.id}' declares an invalid input schema")
            raise ToolInvokeError(
                "TOOL_ERROR", "The tool's input schema is invalid"
            ) from None
        errors = sorted(
            Draft202012Validator(definition.input_schema).iter_errors(arguments),
            key=str,
        )
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
        self,
        definition: ToolDefinition,
        context: ToolContext,
        arguments: dict[str, Any],
        literal: dict[str, Any],
        references: dict[str, str],
        seconds: float,
    ) -> bytes:
        if self._in_flight >= self._max_concurrent:
            raise ToolInvokeError(
                "RESOURCE_EXHAUSTED",
                "The engine is running as many tool calls as it accepts: retry later",
                retryable=True,
            )
        if self._pool is None:
            self._pool = ThreadPoolExecutor(
                max_workers=self._max_concurrent, thread_name_prefix="nats-tool-invoke"
            )
        self._in_flight += 1
        loop = asyncio.get_running_loop()
        work = contextvars.copy_context()
        future = loop.run_in_executor(
            self._pool,
            work.run,
            self._execute,
            definition,
            context,
            arguments,
            literal,
            references,
        )

        def finished(done: asyncio.Future) -> None:
            # A call past its deadline holds its slot until the tool returns.
            self._in_flight -= 1
            if not done.cancelled():
                done.exception()

        future.add_done_callback(finished)
        try:
            return await asyncio.wait_for(asyncio.shield(future), seconds)
        except asyncio.TimeoutError:  # noqa: UP041 - not the builtin one on Python 3.10
            raise ToolInvokeError(
                "DEADLINE_EXCEEDED", f"Tool exceeded its {seconds:g}s deadline"
            ) from None

    def _execute(
        self,
        definition: ToolDefinition,
        context: ToolContext,
        arguments: dict[str, Any],
        literal: dict[str, Any],
        references: dict[str, str],
    ) -> bytes:
        """On a worker thread: resolve secrets, build the tool, call it."""
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
        try:
            result = tool.invoke(arguments)
        except ToolException as exc:
            raise ToolInvokeError(
                "TOOL_ERROR", scrub(str(exc), hidden)[:MAX_ERROR_CHARACTERS]
            ) from None
        except ValidationError as exc:
            first = exc.errors(include_input=False, include_url=False)[0]
            where = "/".join(str(part) for part in first.get("loc", ()))
            raise ToolInvokeError(
                "INVALID_ARGUMENT",
                scrub(f"{where or 'arguments'}: {first.get('msg', 'invalid')}", hidden)[
                    :200
                ],
            ) from None
        except Exception as exc:  # noqa: BLE001 - its message may hold a credential
            logger.warning(
                f"tool_registry invoke: '{definition.id}' failed: {type(exc).__name__}"
            )
            raise ToolInvokeError("TOOL_ERROR", "Tool execution failed") from None
        return self._encode(result, hidden)

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
