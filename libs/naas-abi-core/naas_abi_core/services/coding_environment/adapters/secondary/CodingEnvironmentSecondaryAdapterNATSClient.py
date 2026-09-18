"""NATS RPC client adapter for the coding_environment kernel domain.

Implements ``ICodingEnvironmentAdapter`` by calling out to a remote
``CodingEnvironmentPrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/coding_environment/v1/coding_environment.proto`` for
the wire contract and ``naas_abi_core/proto/README.md`` for why it lives
there.

``nats-py`` has no synchronous client, so -- like
``naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter`` and
``ObjectStorageSecondaryAdapterNATSClient`` -- this adapter bridges async
NATS onto the synchronous port with ONE persistent background thread
running its own asyncio event loop (started lazily on first use) and a
single NATS connection reused across calls. Every synchronous port method
submits its async request via
``asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=...)`` and
blocks until it completes or raises, retrying once on a stale connection --
same shape as ``NATSJetStreamAdapter.publish``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``CodingEnvironmentPrimaryAdapterNATS`` must read the
token from that exact header -- both sides read ``AUTH_HEADER`` from
``coding_environment_nats_contract``, a neutral module neither adapter owns,
so this file never has to import from the primary adapter's module (or vice
versa) just to agree on a header name.

``wait_until_ready``/``get_workspace_ui_url``/``get_runtime_binding``/
``get_harness_binding`` are explicitly out of scope for this v1 contract
(see the ``.proto`` file's header comment): there is no NATS subject for
any of them, and this client deliberately does NOT define these methods at
all -- matching how an adapter that doesn't support them already behaves
locally via ``getattr(..., None)`` in ``CodingEnvironmentService``.
``wait_until_ready`` in particular needs no RPC of its own: it is a pure
client-side polling loop built from repeated ``get_status`` calls, which
already works unmodified against this adapter.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import RLock, Thread
from typing import Self, TypeVar

import nats
from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import DEFAULT_TTL, issue_service_token
from naas_abi_core.proto.coding_environment.v1 import coding_environment_pb2
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.coding_environment.adapters.coding_environment_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    AccessDeniedError,
    AgentNeverConnectedError,
    ICodingEnvironmentAdapter,
    ProvisionFailedError,
    ProvisionTimeoutError,
    QuotaExceededError,
    TemplateNotFoundError,
    WorkspaceAccess,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
    WorkspaceStatus,
    WorkspaceTemplate,
)
from nats.aio.client import Client as NATSClient

_DEFAULT_TIMEOUT_SECONDS = 10.0
# Reissue the token this long before it actually expires, so a call that's
# in flight while the token is borderline doesn't get rejected mid-request.
_TOKEN_RENEWAL_MARGIN = timedelta(minutes=5)

_ResponseT = TypeVar("_ResponseT", bound=Message)


def _pb_to_template(pb: coding_environment_pb2.WorkspaceTemplate) -> WorkspaceTemplate:
    return WorkspaceTemplate(
        id=pb.id, name=pb.name, active_version_id=pb.active_version_id
    )


def _pb_to_status(pb: coding_environment_pb2.WorkspaceStatus) -> WorkspaceStatus:
    return WorkspaceStatus(
        id=pb.id, name=pb.name, phase=pb.phase, agent_ready=pb.agent_ready
    )


def _pb_to_access(pb: coding_environment_pb2.WorkspaceAccess) -> WorkspaceAccess:
    return WorkspaceAccess(
        url=pb.url,
        token=pb.token if pb.HasField("token") else None,
        expires_at=pb.expires_at if pb.HasField("expires_at") else None,
    )


def _params_to_pb(params: dict[str, str] | None) -> dict[str, str]:
    """Encode an optional params dict for the wire.

    proto3 map fields have no field-presence tracking (unlike ``optional``
    scalars), so there is no way to send "None" distinctly from "{}" --
    both collapse to an absent/empty map. ``ICodingEnvironmentAdapter``
    treats "no params" and "empty params" identically, so this is a lossless
    encoding for every caller that matters.
    """
    return dict(params) if params else {}


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``CodingEnvironmentPrimaryAdapterNATS``
    encodes errors -- the generic adapter contract test asserts on the real
    exception types, not on the wire code. ``status`` round-trips via
    ``CallError.status`` when the originating exception set one.
    """
    status = error.status if error.HasField("status") else None
    if error.code == "PROVISION_FAILED":
        raise ProvisionFailedError(error.message, status=status)
    if error.code == "PROVISION_TIMEOUT":
        raise ProvisionTimeoutError(error.message, status=status)
    if error.code == "AGENT_NEVER_CONNECTED":
        raise AgentNeverConnectedError(error.message, status=status)
    if error.code == "TEMPLATE_NOT_FOUND":
        raise TemplateNotFoundError(error.message, status=status)
    if error.code == "WORKSPACE_NOT_FOUND":
        raise WorkspaceNotFoundError(error.message, status=status)
    if error.code == "WORKSPACE_NAME_CONFLICT":
        raise WorkspaceNameConflictError(error.message, status=status)
    if error.code == "QUOTA_EXCEEDED":
        raise QuotaExceededError(error.message, status=status)
    if error.code == "ACCESS_DENIED":
        raise AccessDeniedError(error.message, status=status)
    raise RuntimeError(
        f"coding_environment NATS RPC failed ({error.code}): {error.message}"
    )


class CodingEnvironmentSecondaryAdapterNATSClient(ICodingEnvironmentAdapter):
    """Calls a remote ``CodingEnvironmentPrimaryAdapterNATS`` over NATS RPC."""

    def __init__(
        self,
        nats_url: str,
        jwt_secret: str,
        service_identity: str,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._nats_url = nats_url
        self._jwt_secret = jwt_secret
        self._service_identity = service_identity
        self._timeout_seconds = timeout_seconds

        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: Thread | None = None
        self._nc: NATSClient | None = None
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        # Guards connect/reconnect + token bookkeeping on the persistent
        # loop, mirroring NATSJetStreamAdapter.__publish_lock.
        self._call_lock = RLock()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self) -> None:
        with self._call_lock:
            self._close_connection()
            self._stop_loop()

    # ------------------------------------------------------------------
    # Persistent background event loop, same shape as NATSJetStreamAdapter.
    # ------------------------------------------------------------------

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None and self._loop.is_running():
            return self._loop

        ready = ThreadingEvent()
        holder: dict[str, asyncio.AbstractEventLoop] = {}

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            holder["loop"] = loop
            ready.set()
            loop.run_forever()
            loop.close()

        thread = Thread(
            target=_run,
            daemon=True,
            name="coding-environment-nats-client-loop",
        )
        thread.start()
        ready.wait()
        self._loop = holder["loop"]
        self._loop_thread = thread
        return self._loop

    def _run_coro(self, coro, timeout: float | None = None):
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout or self._timeout_seconds)

    def _stop_loop(self) -> None:
        loop = self._loop
        thread = self._loop_thread
        self._loop = None
        self._loop_thread = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5.0)

    async def _ensure_connection_async(self) -> NATSClient:
        if self._nc is not None and self._nc.is_connected:
            return self._nc
        nc = await nats.connect(self._nats_url)
        self._nc = nc
        return nc

    def _close_connection(self) -> None:
        nc = self._nc
        self._nc = None
        if nc is not None and self._loop is not None and self._loop.is_running():
            try:
                self._run_coro(nc.close(), timeout=5.0)
            except Exception:  # noqa: BLE001
                # Best-effort close of a connection we're discarding anyway
                # (already stale, or being replaced by a fresh reconnect).
                logger.opt(exception=True).debug(
                    "CodingEnvironmentSecondaryAdapterNATSClient: error closing stale connection"
                )

    # ------------------------------------------------------------------
    # Auth: issue once, reissue only when close to expiry.
    # ------------------------------------------------------------------

    def _current_token(self) -> str:
        now = datetime.now(UTC)
        if (
            self._token is None
            or self._token_expires_at is None
            or now >= self._token_expires_at - _TOKEN_RENEWAL_MARGIN
        ):
            self._token = issue_service_token(self._service_identity, self._jwt_secret)
            self._token_expires_at = now + DEFAULT_TTL
        return self._token

    # ------------------------------------------------------------------
    # RPC plumbing.
    # ------------------------------------------------------------------

    def _context(self) -> common_pb2.CallContext:
        return common_pb2.CallContext(
            trace_id=str(uuid.uuid4()),
            timeout_ms=int(self._timeout_seconds * 1000),
        )

    def _call(
        self, subject: str, request: Message, response_cls: type[_ResponseT]
    ) -> _ResponseT:
        payload = request.SerializeToString()
        with self._call_lock:
            headers = {AUTH_HEADER: self._current_token()}
            try:
                msg = self._run_coro(self._do_request_async(subject, payload, headers))
            except Exception:  # noqa: BLE001
                self._close_connection()
                try:
                    msg = self._run_coro(
                        self._do_request_async(subject, payload, headers)
                    )
                except Exception as exc:
                    self._close_connection()
                    raise ConnectionError(
                        f"coding_environment NATS RPC to {subject!r} failed"
                    ) from exc

        response = response_cls()
        response.ParseFromString(msg.data)
        return response

    async def _do_request_async(self, subject: str, payload: bytes, headers: dict[str, str]):
        nc = await self._ensure_connection_async()
        return await nc.request(
            subject, payload, timeout=self._timeout_seconds, headers=headers
        )

    # ------------------------------------------------------------------
    # ICodingEnvironmentAdapter.
    # ------------------------------------------------------------------

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        request = coding_environment_pb2.EnsureUserRequest(
            context=self._context(),
            external_id=external_id,
            email=email,
            username=username,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.ensure_user",
            request,
            coding_environment_pb2.EnsureUserResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.user_id

    def list_templates(self) -> list[WorkspaceTemplate]:
        request = coding_environment_pb2.ListTemplatesRequest(context=self._context())
        response = self._call(
            f"{SUBJECT_PREFIX}.list_templates",
            request,
            coding_environment_pb2.ListTemplatesResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_template(t) for t in response.templates.templates]

    def provision(
        self,
        *,
        user_id: str,
        template_id: str,
        name: str,
        params: dict[str, str] | None = None,
    ) -> WorkspaceStatus:
        request = coding_environment_pb2.ProvisionRequest(
            context=self._context(),
            user_id=user_id,
            template_id=template_id,
            name=name,
            params=_params_to_pb(params),
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.provision",
            request,
            coding_environment_pb2.ProvisionResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_status(response.status)

    def start(
        self, *, workspace_id: str, params: dict[str, str] | None = None
    ) -> WorkspaceStatus:
        request = coding_environment_pb2.StartRequest(
            context=self._context(),
            workspace_id=workspace_id,
            params=_params_to_pb(params),
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.start", request, coding_environment_pb2.StartResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_status(response.status)

    def stop(self, *, workspace_id: str) -> WorkspaceStatus:
        request = coding_environment_pb2.StopRequest(
            context=self._context(), workspace_id=workspace_id
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.stop", request, coding_environment_pb2.StopResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_status(response.status)

    def delete(self, *, workspace_id: str) -> None:
        request = coding_environment_pb2.DeleteRequest(
            context=self._context(), workspace_id=workspace_id
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.delete", request, coding_environment_pb2.DeleteResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def list_environments(self, *, user_id: str) -> list[WorkspaceStatus]:
        request = coding_environment_pb2.ListEnvironmentsRequest(
            context=self._context(), user_id=user_id
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.list_environments",
            request,
            coding_environment_pb2.ListEnvironmentsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_status(e) for e in response.environments.environments]

    def get_status(self, *, workspace_id: str) -> WorkspaceStatus:
        request = coding_environment_pb2.GetStatusRequest(
            context=self._context(), workspace_id=workspace_id
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_status",
            request,
            coding_environment_pb2.GetStatusResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_status(response.status)

    def get_logs(self, *, workspace_id: str) -> list[str]:
        request = coding_environment_pb2.GetLogsRequest(
            context=self._context(), workspace_id=workspace_id
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_logs", request, coding_environment_pb2.GetLogsResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return list(response.lines.lines)

    def get_access(
        self, *, workspace_id: str, user_id: str, app_slug: str
    ) -> WorkspaceAccess:
        request = coding_environment_pb2.GetAccessRequest(
            context=self._context(),
            workspace_id=workspace_id,
            user_id=user_id,
            app_slug=app_slug,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_access",
            request,
            coding_environment_pb2.GetAccessResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_access(response.access)
